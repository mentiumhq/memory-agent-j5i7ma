"""
Unit tests for SQLAlchemy ORM models including Document, DocumentChunk, and DocumentIndex.
Tests model behavior, relationships, data integrity, token management, and access patterns.

Version: pytest 7.4+
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4

from src.db.models.document import Document
from src.db.models.document_chunk import DocumentChunk
from src.db.models.document_index import DocumentIndex


class TestDocument:
    """Test suite for Document model functionality and relationships."""

    def test_document_creation(self):
        """Test document instance creation with valid data."""
        # Arrange
        content = "s3://bucket/document.md"
        format = "markdown"
        metadata = {"author": "test", "tags": ["test", "document"]}
        token_count = 100

        # Act
        doc = Document(
            content=content,
            format=format,
            metadata=metadata,
            token_count=token_count
        )

        # Assert
        assert str(doc.id) is not None
        assert doc.content == content
        assert doc.format == format
        assert doc.metadata == metadata
        assert doc.token_count == token_count
        assert isinstance(doc.created_at, datetime)
        assert isinstance(doc.updated_at, datetime)
        assert doc.chunks == []
        assert doc.index is None

    def test_document_creation_validation(self):
        """Test document creation with invalid data."""
        # Test invalid content reference
        with pytest.raises(ValueError, match="Content must be an S3 reference"):
            Document(content="invalid", format="markdown")

        # Test empty format
        with pytest.raises(ValueError, match="Format must be specified"):
            Document(content="s3://bucket/doc.md", format="")

        # Test negative token count
        with pytest.raises(ValueError, match="Token count must be non-negative"):
            Document(
                content="s3://bucket/doc.md",
                format="markdown",
                token_count=-1
            )

    def test_document_update(self):
        """Test document content and metadata updates."""
        # Arrange
        doc = Document(
            content="s3://bucket/original.md",
            format="markdown",
            metadata={"version": 1},
            token_count=100
        )
        original_updated = doc.updated_at

        # Act - Update content
        new_content = "s3://bucket/updated.md"
        doc.update_content(new_content, token_count=150)

        # Assert content update
        assert doc.content == new_content
        assert doc.token_count == 150
        assert doc.updated_at > original_updated

        # Act - Update metadata
        new_metadata = {"version": 2, "status": "updated"}
        doc.update_metadata(new_metadata)

        # Assert metadata update
        assert doc.metadata == {"version": 2, "status": "updated"}
        assert doc.updated_at > original_updated

    def test_document_relationships(self):
        """Test document relationships with chunks and index."""
        # Arrange
        doc = Document(
            content="s3://bucket/doc.md",
            format="markdown",
            token_count=100
        )

        # Act - Create chunks
        chunk1 = DocumentChunk(
            document_id=doc.id,
            content="Part 1",
            chunk_number=0,
            token_count=50
        )
        chunk2 = DocumentChunk(
            document_id=doc.id,
            content="Part 2",
            chunk_number=1,
            token_count=50
        )
        doc.chunks.extend([chunk1, chunk2])

        # Act - Create index
        index = DocumentIndex(
            document_id=doc.id,
            metadata={"indexed": True}
        )
        doc.index = index

        # Assert relationships
        assert len(doc.chunks) == 2
        assert doc.chunks[0].content == "Part 1"
        assert doc.chunks[1].content == "Part 2"
        assert doc.index.metadata == {"indexed": True}
        assert doc.index.document_id == doc.id

    def test_document_token_management(self):
        """Test document token counting and limits."""
        # Arrange
        doc = Document(
            content="s3://bucket/doc.md",
            format="markdown",
            token_count=0
        )

        # Act - Add chunks with different token counts
        chunks = [
            DocumentChunk(
                document_id=doc.id,
                content=f"Part {i}",
                chunk_number=i,
                token_count=1000
            )
            for i in range(4)
        ]
        doc.chunks.extend(chunks)

        # Assert total token count
        total_tokens = sum(chunk.token_count for chunk in doc.chunks)
        doc.token_count = total_tokens
        assert doc.token_count == 4000


class TestDocumentChunk:
    """Test suite for DocumentChunk model functionality."""

    def test_chunk_creation(self):
        """Test chunk instance creation with valid data."""
        # Arrange
        document_id = uuid4()
        content = "Test chunk content"
        chunk_number = 0
        token_count = 100

        # Act
        chunk = DocumentChunk(
            document_id=document_id,
            content=content,
            chunk_number=chunk_number,
            token_count=token_count
        )

        # Assert
        assert str(chunk.id) is not None
        assert chunk.document_id == document_id
        assert chunk.content == content
        assert chunk.chunk_number == chunk_number
        assert chunk.token_count == token_count
        assert chunk.embedding is None

    def test_chunk_creation_validation(self):
        """Test chunk creation with invalid data."""
        document_id = uuid4()

        # Test negative chunk number
        with pytest.raises(ValueError, match="Chunk number must be non-negative"):
            DocumentChunk(
                document_id=document_id,
                content="test",
                chunk_number=-1,
                token_count=100
            )

        # Test token count exceeding limit
        with pytest.raises(ValueError, match="Token count exceeds maximum limit"):
            DocumentChunk(
                document_id=document_id,
                content="test",
                chunk_number=0,
                token_count=9000  # Exceeds GPT-4 limit
            )

    def test_chunk_embedding(self):
        """Test chunk embedding vector operations."""
        # Arrange
        chunk = DocumentChunk(
            document_id=uuid4(),
            content="test",
            chunk_number=0,
            token_count=100
        )

        # Act - Update with valid embedding
        valid_embedding = bytes([1, 2, 3, 4])
        chunk.update_embedding(valid_embedding)

        # Assert
        assert chunk.embedding == valid_embedding
        assert chunk.to_dict()["embedding"] == valid_embedding.hex()

        # Test invalid embedding type
        with pytest.raises(ValueError, match="Embedding must be bytes"):
            chunk.update_embedding([1, 2, 3, 4])  # Not bytes


class TestDocumentIndex:
    """Test suite for DocumentIndex model functionality."""

    def test_index_creation(self):
        """Test index instance creation with valid data."""
        # Arrange
        document_id = uuid4()
        metadata = {"indexed": True, "version": 1}

        # Act
        index = DocumentIndex(document_id=document_id, metadata=metadata)

        # Assert
        assert str(index.id) is not None
        assert index.document_id == document_id
        assert index.metadata == metadata
        assert index.access_count == 0
        assert isinstance(index.last_accessed, datetime)

    def test_index_access_tracking(self):
        """Test index access pattern tracking."""
        # Arrange
        index = DocumentIndex(
            document_id=uuid4(),
            metadata={"indexed": True}
        )
        original_access = index.last_accessed

        # Act - Record multiple accesses
        for _ in range(5):
            index.record_access()

        # Assert
        assert index.access_count == 5
        assert index.last_accessed > original_access

    def test_index_metadata_management(self):
        """Test index metadata operations."""
        # Arrange
        index = DocumentIndex(
            document_id=uuid4(),
            metadata={"_protected": True, "version": 1}
        )

        # Act - Update metadata
        index.update_metadata({"version": 2, "status": "updated"})

        # Assert - Protected fields preserved
        assert index.metadata["_protected"] is True
        assert index.metadata["version"] == 2
        assert index.metadata["status"] == "updated"

        # Test invalid metadata
        with pytest.raises(ValueError, match="Metadata must be a dictionary"):
            index.update_metadata("invalid")