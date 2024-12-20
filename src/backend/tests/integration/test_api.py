"""
Integration tests for the Memory Agent API endpoints.
Validates document operations, error handling, performance requirements,
and security controls with comprehensive test coverage.

Version: 1.0.0
"""

import pytest
import pytest_asyncio
import uuid
import time
import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime, timezone

from ...src.api.models.request import (
    StoreDocumentRequest,
    SearchDocumentRequest,
    RetrievalStrategy
)
from ...core.errors import ErrorCode, MemoryAgentError
from ...core.utils import generate_uuid, get_current_timestamp

# Test configuration constants
TEST_TIMEOUT = 5.0  # seconds
RATE_LIMIT_REQUESTS = 100
PERFORMANCE_THRESHOLD_MS = 500

# Test document templates
TEST_DOCUMENTS = {
    "markdown": {
        "content": "# Test Document\nThis is a markdown test.",
        "format": "markdown",
        "metadata": {"type": "test", "format": "markdown"}
    },
    "text": {
        "content": "Plain text test document.",
        "format": "text",
        "metadata": {"type": "test", "format": "text"}
    },
    "json": {
        "content": json.dumps({"test": "data"}),
        "format": "json",
        "metadata": {"type": "test", "format": "json"}
    }
}

class TestDocumentAPI:
    """Integration test suite for Memory Agent API endpoints."""

    @pytest.fixture(autouse=True)
    async def setup(self, test_client, temporal_client):
        """Set up test environment with clean state."""
        self.client = test_client
        self.temporal = temporal_client
        self.stored_documents = {}
        self.performance_metrics = {
            "store": [],
            "retrieve": [],
            "search": []
        }
        yield
        await self.cleanup()

    async def cleanup(self):
        """Clean up test data and export metrics."""
        for doc_id in self.stored_documents:
            try:
                await self.client.delete(f"/v1/documents/{doc_id}")
            except Exception:
                pass
        self.stored_documents.clear()

    @pytest.mark.asyncio
    async def test_store_document_success(self, test_client, temporal_client):
        """Test successful document storage with different formats."""
        for doc_type, template in TEST_DOCUMENTS.items():
            # Prepare request
            request = StoreDocumentRequest(
                content=template["content"],
                format=template["format"],
                metadata=template["metadata"]
            )

            # Measure performance
            start_time = time.time()
            response = await test_client.post(
                "/v1/documents/store",
                json=request.dict()
            )
            duration_ms = (time.time() - start_time) * 1000

            # Validate response
            assert response.status_code == 200
            assert duration_ms < PERFORMANCE_THRESHOLD_MS

            data = response.json()
            assert "document_id" in data
            assert "version_id" in data

            # Verify document storage
            doc_id = data["document_id"]
            self.stored_documents[doc_id] = data["version_id"]

            # Verify Temporal workflow execution
            workflow = await temporal_client.get_workflow(f"store_document_{doc_id}")
            workflow_state = await workflow.describe()
            assert workflow_state.status.name == "COMPLETED"

            # Validate security headers
            assert "X-Content-Type-Options" in response.headers
            assert "X-Frame-Options" in response.headers
            assert "X-XSS-Protection" in response.headers

    @pytest.mark.asyncio
    async def test_retrieve_document(self, test_client, temporal_client):
        """Test document retrieval with version control."""
        # First store a test document
        doc_request = StoreDocumentRequest(**TEST_DOCUMENTS["markdown"])
        store_response = await test_client.post(
            "/v1/documents/store",
            json=doc_request.dict()
        )
        assert store_response.status_code == 200
        doc_data = store_response.json()
        doc_id = doc_data["document_id"]

        # Test retrieval
        start_time = time.time()
        response = await test_client.get(f"/v1/documents/{doc_id}")
        duration_ms = (time.time() - start_time) * 1000

        # Validate response
        assert response.status_code == 200
        assert duration_ms < PERFORMANCE_THRESHOLD_MS

        data = response.json()
        assert data["content"] == TEST_DOCUMENTS["markdown"]["content"]
        assert data["format"] == TEST_DOCUMENTS["markdown"]["format"]
        assert data["metadata"] == TEST_DOCUMENTS["markdown"]["metadata"]

        # Test cache hit
        cache_response = await test_client.get(f"/v1/documents/{doc_id}")
        assert "X-Cache-Hit" in cache_response.headers

    @pytest.mark.asyncio
    async def test_search_documents(self, test_client, temporal_client):
        """Test document search with all retrieval strategies."""
        # Store multiple test documents
        doc_ids = []
        for template in TEST_DOCUMENTS.values():
            response = await test_client.post(
                "/v1/documents/store",
                json=StoreDocumentRequest(**template).dict()
            )
            assert response.status_code == 200
            doc_ids.append(response.json()["document_id"])

        # Test each search strategy
        for strategy in RetrievalStrategy:
            request = SearchDocumentRequest(
                query="test document",
                strategy=strategy,
                filters={"type": "test"},
                limit=10
            )

            start_time = time.time()
            response = await test_client.post(
                "/v1/documents/search",
                json=request.dict()
            )
            duration_ms = (time.time() - start_time) * 1000

            # Validate response
            assert response.status_code == 200
            assert duration_ms < PERFORMANCE_THRESHOLD_MS * 2  # Allow higher latency for search

            data = response.json()
            assert "documents" in data
            assert len(data["documents"]) <= request.limit
            assert all(doc["id"] in doc_ids for doc in data["documents"])

            # Validate strategy-specific results
            if strategy == RetrievalStrategy.VECTOR:
                assert "similarity_scores" in data
            elif strategy == RetrievalStrategy.LLM:
                assert "reasoning" in data
            elif strategy == RetrievalStrategy.HYBRID:
                assert "combined_scores" in data
            elif strategy == RetrievalStrategy.RAG_KG:
                assert "graph_context" in data

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, test_client):
        """Test API behavior under concurrent load."""
        async def make_request():
            return await test_client.post(
                "/v1/documents/store",
                json=StoreDocumentRequest(**TEST_DOCUMENTS["text"]).dict()
            )

        # Execute concurrent requests
        tasks = [make_request() for _ in range(RATE_LIMIT_REQUESTS)]
        start_time = time.time()
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        total_time = time.time() - start_time

        # Analyze results
        success_count = sum(1 for r in responses if not isinstance(r, Exception))
        error_count = len(responses) - success_count

        # Validate rate limiting and performance
        assert success_count > 0
        assert total_time < TEST_TIMEOUT
        assert error_count <= RATE_LIMIT_REQUESTS * 0.1  # Allow 10% error rate

    @pytest.mark.asyncio
    async def test_error_scenarios(self, test_client):
        """Test comprehensive error handling scenarios."""
        # Test invalid document format
        invalid_format = StoreDocumentRequest(
            content="Test content",
            format="invalid",
            metadata={}
        )
        response = await test_client.post(
            "/v1/documents/store",
            json=invalid_format.dict()
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == ErrorCode.VALIDATION_ERROR.value

        # Test missing required fields
        response = await test_client.post(
            "/v1/documents/store",
            json={"content": "Test"}  # Missing format
        )
        assert response.status_code == 422

        # Test non-existent document
        response = await test_client.get(f"/v1/documents/{generate_uuid()}")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == ErrorCode.DOCUMENT_NOT_FOUND.value

        # Test invalid search strategy
        response = await test_client.post(
            "/v1/documents/search",
            json={"query": "test", "strategy": "invalid"}
        )
        assert response.status_code == 422

        # Test invalid authentication
        response = await test_client.post(
            "/v1/documents/store",
            json=TEST_DOCUMENTS["text"],
            headers={"Authorization": "Invalid"}
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == ErrorCode.AUTHENTICATION_ERROR.value

        # Test rate limiting
        async def flood_requests():
            tasks = []
            for _ in range(RATE_LIMIT_REQUESTS * 2):
                tasks.append(test_client.get("/v1/documents/health"))
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            return responses

        responses = await flood_requests()
        rate_limited = any(
            getattr(r, "status_code", 0) == 429
            for r in responses
            if not isinstance(r, Exception)
        )
        assert rate_limited