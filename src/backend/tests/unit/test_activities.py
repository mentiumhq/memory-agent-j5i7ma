"""
Comprehensive unit tests for Temporal workflow activities including document, cache,
and LLM activities. Validates core functionality, error handling, retry mechanisms,
and monitoring integration.

Version:
- pytest==7.4.0
- pytest-asyncio==0.21.0
- pytest-timeout==2.1.0
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import uuid
from datetime import datetime, timezone

from src.activities.document_activities import (
    store_document_activity,
    retrieve_document_activity,
    search_documents_activity
)
from src.activities.cache_activities import (
    get_document_chunk_activity,
    cache_document_chunk_activity
)
from src.activities.llm_activities import (
    reason_documents,
    select_documents
)
from src.core.errors import StorageError, ErrorCode
from src.db.models.document import Document
from src.db.models.document_chunk import DocumentChunk

# Test constants
TEST_DOCUMENT_CONTENT = "Test document content"
TEST_DOCUMENT_FORMAT = "markdown"
TEST_DOCUMENT_ID = "test-doc-123"
TEST_CHUNK_ID = "test-chunk-123"
TEST_TOKEN_LIMIT = 4096
TEST_CACHE_TTL = 3600
TEST_RETRY_LIMIT = 3

@pytest.mark.asyncio
class TestDocumentActivities:
    """Test suite for document-related Temporal activities."""

    def setup_method(self):
        """Setup test environment before each test."""
        # Mock document service
        self.mock_document_service = MagicMock()
        self.mock_document_service.store_document = AsyncMock()
        self.mock_document_service.retrieve_document = AsyncMock()
        self.mock_document_service.search_documents = AsyncMock()

        # Mock metrics collector
        self.mock_metrics = MagicMock()
        self.mock_metrics.record_operation = AsyncMock()

        # Mock cache service
        self.mock_cache_service = MagicMock()
        self.mock_cache_service.get_document_chunk = AsyncMock()
        self.mock_cache_service.cache_document_chunk = AsyncMock()

        # Mock LLM service
        self.mock_llm_service = MagicMock()
        self.mock_llm_service.async_reason_documents = AsyncMock()
        self.mock_llm_service.async_select_documents = AsyncMock()

        # Test document data
        self.test_document = Document(
            content=TEST_DOCUMENT_CONTENT,
            format=TEST_DOCUMENT_FORMAT,
            metadata={},
            token_count=100
        )
        self.test_chunk = DocumentChunk(
            document_id=uuid.UUID(TEST_DOCUMENT_ID),
            content=TEST_DOCUMENT_CONTENT,
            chunk_number=0,
            token_count=100
        )

    @pytest.mark.unit
    async def test_store_document_success(self):
        """Test successful document storage activity."""
        # Setup
        self.mock_document_service.store_document.return_value = TEST_DOCUMENT_ID

        # Execute
        with patch('src.activities.document_activities.DocumentService', 
                  return_value=self.mock_document_service):
            result = await store_document_activity(
                content=TEST_DOCUMENT_CONTENT,
                format=TEST_DOCUMENT_FORMAT,
                metadata={}
            )

        # Verify
        assert result == TEST_DOCUMENT_ID
        self.mock_document_service.store_document.assert_called_once()
        self.mock_metrics.record_operation.assert_called_once()

    @pytest.mark.unit
    async def test_store_document_retry_mechanism(self):
        """Test retry mechanism for document storage activity."""
        # Setup
        self.mock_document_service.store_document.side_effect = [
            StorageError("Temporary error", ErrorCode.STORAGE_ERROR),
            StorageError("Temporary error", ErrorCode.STORAGE_ERROR),
            TEST_DOCUMENT_ID
        ]

        # Execute
        with patch('src.activities.document_activities.DocumentService',
                  return_value=self.mock_document_service):
            result = await store_document_activity(
                content=TEST_DOCUMENT_CONTENT,
                format=TEST_DOCUMENT_FORMAT,
                metadata={}
            )

        # Verify
        assert result == TEST_DOCUMENT_ID
        assert self.mock_document_service.store_document.call_count == 3

    @pytest.mark.unit
    async def test_retrieve_document_success(self):
        """Test successful document retrieval activity."""
        # Setup
        self.mock_document_service.retrieve_document.return_value = self.test_document

        # Execute
        with patch('src.activities.document_activities.DocumentService',
                  return_value=self.mock_document_service):
            result = await retrieve_document_activity(TEST_DOCUMENT_ID)

        # Verify
        assert result.content == TEST_DOCUMENT_CONTENT
        assert result.format == TEST_DOCUMENT_FORMAT
        self.mock_document_service.retrieve_document.assert_called_once_with(TEST_DOCUMENT_ID)

    @pytest.mark.unit
    async def test_search_documents_success(self):
        """Test successful document search activity."""
        # Setup
        test_query = "test query"
        test_results = [(self.test_document, 0.95)]
        self.mock_document_service.search_documents.return_value = test_results

        # Execute
        with patch('src.activities.document_activities.DocumentService',
                  return_value=self.mock_document_service):
            results = await search_documents_activity(
                query=test_query,
                strategy="hybrid",
                filters={},
                limit=10
            )

        # Verify
        assert len(results) == 1
        assert results[0].content == TEST_DOCUMENT_CONTENT

    @pytest.mark.unit
    async def test_cache_document_chunk_success(self):
        """Test successful document chunk caching activity."""
        # Setup
        self.mock_cache_service.cache_document_chunk.return_value = True

        # Execute
        with patch('src.activities.cache_activities.CacheService',
                  return_value=self.mock_cache_service):
            result = await cache_document_chunk_activity(self.test_chunk)

        # Verify
        assert result is True
        self.mock_cache_service.cache_document_chunk.assert_called_once_with(self.test_chunk)

    @pytest.mark.unit
    async def test_get_document_chunk_success(self):
        """Test successful document chunk retrieval activity."""
        # Setup
        cached_data = {"content": TEST_DOCUMENT_CONTENT}
        self.mock_cache_service.get_document_chunk.return_value = cached_data

        # Execute
        with patch('src.activities.cache_activities.CacheService',
                  return_value=self.mock_cache_service):
            result = await get_document_chunk_activity(TEST_CHUNK_ID)

        # Verify
        assert result == cached_data
        self.mock_cache_service.get_document_chunk.assert_called_once_with(TEST_CHUNK_ID)

    @pytest.mark.unit
    async def test_reason_documents_success(self):
        """Test successful document reasoning activity."""
        # Setup
        test_query = "test query"
        test_documents = [TEST_DOCUMENT_CONTENT]
        expected_result = {
            "reasoning": "Test reasoning",
            "confidence": 0.95
        }
        self.mock_llm_service.async_reason_documents.return_value = expected_result

        # Execute
        with patch('src.activities.llm_activities.LLMService',
                  return_value=self.mock_llm_service):
            result = await reason_documents(
                query=test_query,
                documents=test_documents
            )

        # Verify
        assert result == expected_result
        self.mock_llm_service.async_reason_documents.assert_called_once()

    @pytest.mark.unit
    async def test_select_documents_success(self):
        """Test successful document selection activity."""
        # Setup
        test_query = "test query"
        test_candidates = [TEST_DOCUMENT_CONTENT]
        expected_result = [TEST_DOCUMENT_CONTENT]
        self.mock_llm_service.async_select_documents.return_value = expected_result

        # Execute
        with patch('src.activities.llm_activities.LLMService',
                  return_value=self.mock_llm_service):
            result = await select_documents(
                query=test_query,
                candidates=test_candidates
            )

        # Verify
        assert result == expected_result
        self.mock_llm_service.async_select_documents.assert_called_once()

    @pytest.mark.unit
    async def test_error_handling(self):
        """Test error handling across activities."""
        # Setup
        error_message = "Test error"
        self.mock_document_service.store_document.side_effect = StorageError(
            error_message,
            ErrorCode.STORAGE_ERROR
        )

        # Execute and verify
        with pytest.raises(StorageError) as exc_info:
            with patch('src.activities.document_activities.DocumentService',
                      return_value=self.mock_document_service):
                await store_document_activity(
                    content=TEST_DOCUMENT_CONTENT,
                    format=TEST_DOCUMENT_FORMAT,
                    metadata={}
                )

        assert str(exc_info.value) == error_message
        assert exc_info.value.error_code == ErrorCode.STORAGE_ERROR

    @pytest.mark.unit
    async def test_validation(self):
        """Test input validation across activities."""
        # Test empty content
        with pytest.raises(StorageError) as exc_info:
            await store_document_activity(
                content="",
                format=TEST_DOCUMENT_FORMAT,
                metadata={}
            )
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR

        # Test invalid format
        with pytest.raises(StorageError) as exc_info:
            await store_document_activity(
                content=TEST_DOCUMENT_CONTENT,
                format="invalid_format",
                metadata={}
            )
        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR

    @pytest.mark.unit
    async def test_monitoring_integration(self):
        """Test monitoring integration across activities."""
        # Setup
        self.mock_document_service.store_document.return_value = TEST_DOCUMENT_ID

        # Execute
        with patch('src.activities.document_activities.DocumentService',
                  return_value=self.mock_document_service):
            await store_document_activity(
                content=TEST_DOCUMENT_CONTENT,
                format=TEST_DOCUMENT_FORMAT,
                metadata={}
            )

        # Verify metrics were recorded
        self.mock_metrics.record_operation.assert_called_once()