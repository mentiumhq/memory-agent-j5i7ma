"""
Comprehensive unit test suite for core service layer components including document,
storage, and embedding services. Tests cover all major operations, error scenarios,
performance validation, and resource management.

Version:
- pytest==7.4+
- pytest-asyncio==0.21+
- numpy==1.24+
"""

import pytest
import asyncio
import numpy as np
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from typing import Dict, List, Any

from src.services.document import DocumentService
from src.services.storage import StorageService
from src.services.embedding import EmbeddingService
from src.repositories.document import DocumentRepository
from src.core.errors import StorageError, ErrorCode
from src.db.models.document import Document
from src.db.models.document_chunk import DocumentChunk

# Test constants
TEST_DOCUMENT_ID = "123e4567-e89b-12d3-a456-426614174000"
TEST_CONTENT = "Test document content for unit testing"
TEST_METADATA = {"format": "text", "source": "test"}
TEST_EMBEDDING = np.random.rand(1536).astype(np.float32)  # Ada-002 dimension

@pytest.fixture
def mock_storage_service():
    """Fixture for mocked StorageService."""
    service = AsyncMock(spec=StorageService)
    service.store_document.return_value = TEST_DOCUMENT_ID
    service.retrieve_document.return_value = (TEST_CONTENT.encode(), TEST_METADATA)
    return service

@pytest.fixture
def mock_embedding_service():
    """Fixture for mocked EmbeddingService."""
    service = AsyncMock(spec=EmbeddingService)
    service.async_generate_embedding.return_value = TEST_EMBEDDING
    service.async_batch_generate_embeddings.return_value = [TEST_EMBEDDING]
    service.calculate_similarity.return_value = 0.85
    return service

@pytest.fixture
def mock_document_repo():
    """Fixture for mocked DocumentRepository."""
    repo = Mock(spec=DocumentRepository)
    repo.create_with_chunks.return_value = Document(
        content=f"s3://{TEST_DOCUMENT_ID}",
        format="text",
        metadata=TEST_METADATA,
        token_count=len(TEST_CONTENT.split())
    )
    return repo

@pytest.mark.asyncio
class TestDocumentService:
    """Test suite for DocumentService operations."""

    async def test_store_document_gpt35(
        self,
        mock_storage_service,
        mock_embedding_service,
        mock_document_repo
    ):
        """Test document storage with GPT-3.5 token limits."""
        # Initialize service
        service = DocumentService(
            storage_service=mock_storage_service,
            embedding_service=mock_embedding_service,
            document_repo=mock_document_repo
        )

        # Test data
        content = " ".join(["word"] * 4000)  # Simulate 4K tokens
        metadata = {"model": "gpt-3.5", "format": "text"}

        # Store document
        start_time = datetime.now(timezone.utc)
        document_id = await service.store_document(content, metadata)
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()

        # Verify storage
        assert document_id == TEST_DOCUMENT_ID
        assert duration < 2.0  # Performance validation
        mock_storage_service.store_document.assert_called_once()
        mock_embedding_service.async_batch_generate_embeddings.assert_called_once()

    async def test_store_document_gpt4(
        self,
        mock_storage_service,
        mock_embedding_service,
        mock_document_repo
    ):
        """Test document storage with GPT-4 token limits."""
        service = DocumentService(
            storage_service=mock_storage_service,
            embedding_service=mock_embedding_service,
            document_repo=mock_document_repo
        )

        # Test data for GPT-4 (8K tokens)
        content = " ".join(["word"] * 8000)
        metadata = {"model": "gpt-4", "format": "text"}

        # Store document
        document_id = await service.store_document(content, metadata)

        # Verify chunking and storage
        assert document_id == TEST_DOCUMENT_ID
        mock_document_repo.create_with_chunks.assert_called_once()

    async def test_search_documents_vector(
        self,
        mock_storage_service,
        mock_embedding_service,
        mock_document_repo
    ):
        """Test vector-based document search."""
        service = DocumentService(
            storage_service=mock_storage_service,
            embedding_service=mock_embedding_service,
            document_repo=mock_document_repo
        )

        # Test vector search
        query = "test query"
        results = await service.search_documents(
            query=query,
            strategy="vector",
            limit=5
        )

        # Verify search operation
        assert isinstance(results, list)
        mock_embedding_service.async_generate_embedding.assert_called_once_with(query)

    async def test_search_documents_hybrid(
        self,
        mock_storage_service,
        mock_embedding_service,
        mock_document_repo
    ):
        """Test hybrid search strategy."""
        service = DocumentService(
            storage_service=mock_storage_service,
            embedding_service=mock_embedding_service,
            document_repo=mock_document_repo
        )

        # Test hybrid search
        results = await service.search_documents(
            query="test query",
            strategy="hybrid",
            filters={"format": "text"},
            limit=5
        )

        # Verify hybrid search
        assert isinstance(results, list)
        mock_embedding_service.calculate_similarity.assert_called()

    async def test_search_error_handling(
        self,
        mock_storage_service,
        mock_embedding_service,
        mock_document_repo
    ):
        """Test search error handling and recovery."""
        service = DocumentService(
            storage_service=mock_storage_service,
            embedding_service=mock_embedding_service,
            document_repo=mock_document_repo
        )

        # Simulate embedding service failure
        mock_embedding_service.async_generate_embedding.side_effect = Exception("API Error")

        # Verify error handling
        with pytest.raises(StorageError) as exc_info:
            await service.search_documents("test query")
        assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR

@pytest.mark.asyncio
class TestStorageService:
    """Test suite for StorageService operations."""

    async def test_store_document_with_chunks(self, mock_document_repo):
        """Test multi-tier document storage with chunks."""
        # Mock S3 client
        mock_s3 = AsyncMock()
        mock_s3.store_document.return_value = TEST_DOCUMENT_ID

        # Initialize service
        service = StorageService(
            document_repository=mock_document_repo,
            s3_client=mock_s3,
            cache_service=AsyncMock()
        )

        # Test storage
        content = b"Test content"
        metadata = {"format": "text"}
        document_id = await service.store_document(content, metadata)

        # Verify storage operations
        assert document_id == TEST_DOCUMENT_ID
        mock_s3.store_document.assert_called_once()
        mock_document_repo.create_with_chunks.assert_called_once()

    async def test_retrieve_document_with_cache(self, mock_document_repo):
        """Test document retrieval with caching."""
        # Mock cache service
        mock_cache = AsyncMock()
        mock_cache.get_document_chunk.return_value = {"content": "cached chunk"}

        # Mock S3 client
        mock_s3 = AsyncMock()
        mock_s3.retrieve_document.return_value = (b"content", {})

        # Initialize service
        service = StorageService(
            document_repository=mock_document_repo,
            s3_client=mock_s3,
            cache_service=mock_cache
        )

        # Test retrieval
        document, chunks = await service.retrieve_document(TEST_DOCUMENT_ID)

        # Verify cache usage
        assert document is not None
        mock_cache.get_document_chunk.assert_called()

@pytest.mark.asyncio
class TestEmbeddingService:
    """Test suite for EmbeddingService operations."""

    def setup_method(self):
        """Set up test environment."""
        self.mock_settings = Mock()
        self.mock_settings.OPENAI_API_KEY = "test-key"

    async def test_generate_embedding(self):
        """Test single text embedding generation."""
        service = EmbeddingService(self.mock_settings)

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.data = [Mock(embedding=TEST_EMBEDDING.tolist())]

        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value.embeddings.create = AsyncMock(
                return_value=mock_response
            )

            # Generate embedding
            result = await service.async_generate_embedding("test text")

            # Verify embedding
            assert isinstance(result, np.ndarray)
            assert result.shape == (1536,)
            assert np.allclose(np.linalg.norm(result), 1.0)

    async def test_batch_generate_embeddings(self):
        """Test batch embedding generation."""
        service = EmbeddingService(self.mock_settings)

        # Mock OpenAI response
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=TEST_EMBEDDING.tolist()),
            Mock(embedding=TEST_EMBEDDING.tolist())
        ]

        with patch('openai.AsyncOpenAI') as mock_client:
            mock_client.return_value.embeddings.create = AsyncMock(
                return_value=mock_response
            )

            # Generate batch embeddings
            texts = ["text1", "text2"]
            results = await service.async_batch_generate_embeddings(texts)

            # Verify batch results
            assert len(results) == 2
            assert all(isinstance(r, np.ndarray) for r in results)
            assert all(r.shape == (1536,) for r in results)

    def test_calculate_similarity(self):
        """Test embedding similarity calculations."""
        service = EmbeddingService(self.mock_settings)

        # Create test vectors
        v1 = np.random.rand(1536).astype(np.float32)
        v2 = np.random.rand(1536).astype(np.float32)
        v1 = v1 / np.linalg.norm(v1)
        v2 = v2 / np.linalg.norm(v2)

        # Calculate similarity
        similarity = service.calculate_similarity(v1, v2)

        # Verify similarity score
        assert 0 <= similarity <= 1
        assert isinstance(similarity, float)

        # Test with identical vectors
        assert service.calculate_similarity(v1, v1) == 1.0

        # Test with orthogonal vectors
        v3 = np.zeros_like(v1)
        v3[0] = 1.0
        v4 = np.zeros_like(v1)
        v4[1] = 1.0
        assert service.calculate_similarity(v3, v4) == 0.0