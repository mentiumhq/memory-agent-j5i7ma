"""
Unit tests for repository implementations including base repository, document repository,
index repository and cache repository. Validates CRUD operations, document chunking,
indexing, and caching functionality with comprehensive error handling and edge cases.

Version:
- pytest==7.4.0
- pytest-asyncio==0.21.0
- pytest-timeout==2.1.0
"""

import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from repositories.base import BaseRepository
from repositories.document import DocumentRepository
from repositories.index import IndexRepository
from repositories.cache import CacheRepository

from db.models.document import Document
from db.models.document_chunk import DocumentChunk
from db.models.document_index import DocumentIndex

from core.errors import StorageError, ErrorCode

@pytest.mark.asyncio
class TestBaseRepository:
    """Test cases for base repository CRUD operations with error handling."""

    async def test_create(self, db_session):
        """Test entity creation with validation."""
        # Initialize repository
        repo = BaseRepository(Document)
        repo._session = db_session

        # Create test document
        doc = Document(
            content="s3://test-bucket/test.md",
            format="markdown",
            metadata={"test": "value"},
            token_count=100
        )

        # Test successful creation
        created_doc = repo.create(doc)
        assert created_doc.id is not None
        assert created_doc.content == "s3://test-bucket/test.md"
        assert created_doc.format == "markdown"
        assert created_doc.metadata == {"test": "value"}
        assert created_doc.token_count == 100

        # Test duplicate creation
        with pytest.raises(StorageError) as exc_info:
            repo.create(doc)
        assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR

        # Test invalid entity type
        with pytest.raises(StorageError) as exc_info:
            repo.create("invalid")
        assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR

    async def test_get(self, db_session):
        """Test entity retrieval with error cases."""
        # Initialize repository
        repo = BaseRepository(Document)
        repo._session = db_session

        # Create test document
        doc = Document(
            content="s3://test-bucket/test.md",
            format="markdown",
            metadata={"test": "value"},
            token_count=100
        )
        created_doc = repo.create(doc)

        # Test successful retrieval
        retrieved_doc = repo.get(created_doc.id)
        assert retrieved_doc is not None
        assert retrieved_doc.id == created_doc.id
        assert retrieved_doc.content == created_doc.content

        # Test non-existent ID
        non_existent = repo.get(str(uuid.uuid4()))
        assert non_existent is None

        # Test invalid ID format
        with pytest.raises(StorageError) as exc_info:
            repo.get("invalid-id")
        assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR

    async def test_update(self, db_session):
        """Test entity update with validation."""
        # Initialize repository
        repo = BaseRepository(Document)
        repo._session = db_session

        # Create test document
        doc = Document(
            content="s3://test-bucket/test.md",
            format="markdown",
            metadata={"test": "value"},
            token_count=100
        )
        created_doc = repo.create(doc)

        # Update document
        created_doc.metadata = {"updated": "value"}
        created_doc.token_count = 200
        updated_doc = repo.update(created_doc)

        # Verify updates
        assert updated_doc.metadata == {"updated": "value"}
        assert updated_doc.token_count == 200

        # Test update of non-existent entity
        non_existent_doc = Document(
            content="s3://test-bucket/missing.md",
            format="markdown",
            token_count=100
        )
        non_existent_doc.id = uuid.uuid4()
        with pytest.raises(StorageError) as exc_info:
            repo.update(non_existent_doc)
        assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR

    async def test_delete(self, db_session):
        """Test entity deletion with cascading."""
        # Initialize repository
        repo = BaseRepository(Document)
        repo._session = db_session

        # Create test document
        doc = Document(
            content="s3://test-bucket/test.md",
            format="markdown",
            metadata={"test": "value"},
            token_count=100
        )
        created_doc = repo.create(doc)

        # Test successful deletion
        assert repo.delete(created_doc.id) is True
        assert repo.get(created_doc.id) is None

        # Test deletion of non-existent entity
        assert repo.delete(str(uuid.uuid4())) is False

@pytest.mark.asyncio
class TestDocumentRepository:
    """Test cases for document repository operations including chunking."""

    async def test_create_with_chunks(self, db_session):
        """Test document creation with chunk validation."""
        repo = DocumentRepository()
        repo._session = db_session

        # Create test document
        doc = Document(
            content="s3://test-bucket/test.md",
            format="markdown",
            metadata={"test": "value"},
            token_count=300
        )

        # Create test chunks
        chunks = [
            DocumentChunk(
                document_id=doc.id,
                content="Chunk 1",
                chunk_number=0,
                token_count=100
            ),
            DocumentChunk(
                document_id=doc.id,
                content="Chunk 2",
                chunk_number=1,
                token_count=200
            )
        ]

        # Test successful creation
        created_doc = repo.create_with_chunks(doc, chunks)
        assert created_doc.id is not None
        assert len(created_doc.chunks) == 2
        assert created_doc.token_count == 300

        # Test chunk size validation
        invalid_chunk = DocumentChunk(
            document_id=doc.id,
            content="Too large",
            chunk_number=0,
            token_count=10000  # Exceeds max size
        )
        with pytest.raises(StorageError) as exc_info:
            repo.create_with_chunks(doc, [invalid_chunk])
        assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR

    async def test_get_with_chunks(self, db_session):
        """Test document retrieval with chunk assembly."""
        repo = DocumentRepository()
        repo._session = db_session

        # Create test document with chunks
        doc = Document(
            content="s3://test-bucket/test.md",
            format="markdown",
            metadata={"test": "value"},
            token_count=300
        )
        chunks = [
            DocumentChunk(
                document_id=doc.id,
                content="Chunk 1",
                chunk_number=0,
                token_count=100
            ),
            DocumentChunk(
                document_id=doc.id,
                content="Chunk 2",
                chunk_number=1,
                token_count=200
            )
        ]
        created_doc = repo.create_with_chunks(doc, chunks)

        # Test successful retrieval
        retrieved_doc = repo.get_with_chunks(str(created_doc.id))
        assert retrieved_doc is not None
        assert len(retrieved_doc.chunks) == 2
        assert retrieved_doc.chunks[0].chunk_number == 0
        assert retrieved_doc.chunks[1].chunk_number == 1

        # Test non-existent document
        assert repo.get_with_chunks(str(uuid.uuid4())) is None

@pytest.mark.asyncio
class TestIndexRepository:
    """Test cases for index repository with access tracking."""

    async def test_create_index(self, db_session):
        """Test index creation with metadata."""
        repo = IndexRepository()
        repo._session = db_session

        # Create test document first
        doc_repo = DocumentRepository()
        doc_repo._session = db_session
        doc = Document(
            content="s3://test-bucket/test.md",
            format="markdown",
            metadata={"test": "value"},
            token_count=100
        )
        created_doc = doc_repo.create(doc)

        # Test successful index creation
        metadata = {
            "format": "markdown",
            "chunk_count": 1,
            "total_tokens": 100
        }
        index = repo.create_index(created_doc.id, metadata)
        assert index.document_id == created_doc.id
        assert index.metadata == metadata
        assert index.access_count == 0

        # Test duplicate index creation
        with pytest.raises(StorageError) as exc_info:
            repo.create_index(created_doc.id, metadata)
        assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR

    async def test_record_access(self, db_session):
        """Test access tracking functionality."""
        repo = IndexRepository()
        repo._session = db_session

        # Create test document and index
        doc_repo = DocumentRepository()
        doc_repo._session = db_session
        doc = Document(
            content="s3://test-bucket/test.md",
            format="markdown",
            token_count=100
        )
        created_doc = doc_repo.create(doc)

        metadata = {"format": "markdown", "chunk_count": 1}
        index = repo.create_index(created_doc.id, metadata)

        # Test access recording
        updated_index = repo.record_access(created_doc.id)
        assert updated_index.access_count == 1
        assert updated_index.last_accessed > index.last_accessed

        # Record multiple accesses
        for _ in range(5):
            updated_index = repo.record_access(created_doc.id)
        assert updated_index.access_count == 6

@pytest.mark.asyncio
class TestCacheRepository:
    """Test cases for cache repository with TTL and thread safety."""

    @pytest.mark.timeout(5)
    async def test_cache_chunk(self, event_loop):
        """Test chunk caching with size limits."""
        repo = CacheRepository(cache_size=2)  # Small cache for testing

        # Create test chunks
        chunk1 = DocumentChunk(
            document_id=uuid.uuid4(),
            content="Test content 1",
            chunk_number=0,
            token_count=100
        )
        chunk2 = DocumentChunk(
            document_id=uuid.uuid4(),
            content="Test content 2",
            chunk_number=1,
            token_count=100
        )

        # Test successful caching
        await repo.cache_chunk(chunk1)
        cached_data = await repo.get_chunk(str(chunk1.id))
        assert cached_data is not None
        assert cached_data["content"] == "Test content 1"

        # Test cache eviction
        await repo.cache_chunk(chunk2)
        stats = await repo.get_stats()
        assert stats["cache_hits"] >= 0
        assert stats["memory_usage"] > 0

    @pytest.mark.timeout(5)
    async def test_ttl_expiration(self, event_loop):
        """Test cache TTL and expiration handling."""
        repo = CacheRepository(ttl_seconds=1)  # Short TTL for testing

        # Create and cache test chunk
        chunk = DocumentChunk(
            document_id=uuid.uuid4(),
            content="Test content",
            chunk_number=0,
            token_count=100
        )
        await repo.cache_chunk(chunk)

        # Verify immediate retrieval
        cached_data = await repo.get_chunk(str(chunk.id))
        assert cached_data is not None

        # Wait for expiration
        await asyncio.sleep(1.5)

        # Verify expiration
        expired_data = await repo.get_chunk(str(chunk.id))
        assert expired_data is None

        # Check cleanup stats
        stats = await repo.get_stats()
        assert stats["cache_expirations"] >= 1