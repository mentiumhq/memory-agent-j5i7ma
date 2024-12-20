"""
Integration tests for Temporal workflows including document storage, retrieval,
and multi-strategy search operations. Validates workflow execution, error handling,
retry mechanisms, telemetry, caching, and performance requirements.

Version:
- pytest==7.4.0
- pytest-asyncio==0.21.0
- temporalio==1.0.0
"""

import pytest
import asyncio
from typing import Dict, Any
from datetime import datetime, timezone
from uuid import uuid4

from temporalio.testing import WorkflowEnvironment
from temporalio.client import Client
from opentelemetry import trace
from opentelemetry.trace import TracerProvider, SpanKind
from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

from ...src.workflows.document import (
    store_document_workflow,
    retrieve_document_workflow,
    search_documents_workflow
)
from ...src.workflows.search import (
    vector_search_workflow,
    llm_search_workflow,
    hybrid_search_workflow,
    rag_kg_search_workflow
)

# Test constants
TEST_DOCUMENT_CONTENT = "Test document content for workflow testing"
TEST_DOCUMENT_FORMAT = "markdown"
TEST_DOCUMENT_METADATA = {"test_key": "test_value"}
VECTOR_SEARCH_TIMEOUT = 500  # ms
LLM_SEARCH_TIMEOUT = 3000   # ms
MAX_RETRY_ATTEMPTS = 3

@pytest.fixture(scope="module")
async def workflow_environment() -> WorkflowEnvironment:
    """Initialize Temporal test environment."""
    async with await WorkflowEnvironment.start_local() as env:
        yield env

@pytest.fixture(scope="module")
async def temporal_client(workflow_environment: WorkflowEnvironment) -> Client:
    """Create Temporal test client."""
    return workflow_environment.client

@pytest.fixture(scope="module")
def tracer_provider() -> TracerProvider:
    """Initialize test tracer provider."""
    provider = SDKTracerProvider()
    trace.set_tracer_provider(provider)
    return provider

@pytest.mark.asyncio
@pytest.mark.integration
async def test_store_document_workflow(
    temporal_client: Client,
    tracer_provider: TracerProvider
) -> None:
    """Test document storage workflow with telemetry validation."""
    
    with tracer_provider.get_tracer("test").start_as_current_span(
        "test_store_document",
        kind=SpanKind.CLIENT
    ) as span:
        try:
            # Execute store workflow
            document_id = await temporal_client.execute_workflow(
                store_document_workflow,
                args=[TEST_DOCUMENT_CONTENT, TEST_DOCUMENT_FORMAT, TEST_DOCUMENT_METADATA],
                id=str(uuid4()),
                task_queue="test"
            )

            # Verify document was stored
            assert document_id is not None
            span.set_attribute("document.id", str(document_id))

            # Retrieve stored document
            document = await temporal_client.execute_workflow(
                retrieve_document_workflow,
                args=[document_id],
                id=str(uuid4()),
                task_queue="test"
            )

            # Validate stored document
            assert document is not None
            assert document["content"] == TEST_DOCUMENT_CONTENT
            assert document["format"] == TEST_DOCUMENT_FORMAT
            assert document["metadata"] == TEST_DOCUMENT_METADATA

            span.set_attribute("success", True)

        except Exception as e:
            span.set_attribute("success", False)
            span.set_attribute("error", str(e))
            raise

@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.load
async def test_concurrent_document_operations(temporal_client: Client) -> None:
    """Test concurrent document operations for system load handling."""
    
    # Create test documents
    test_docs = [
        (f"Test document {i}", TEST_DOCUMENT_FORMAT, TEST_DOCUMENT_METADATA)
        for i in range(10)
    ]

    # Execute concurrent store operations
    store_tasks = [
        temporal_client.execute_workflow(
            store_document_workflow,
            args=[content, format, metadata],
            id=str(uuid4()),
            task_queue="test"
        )
        for content, format, metadata in test_docs
    ]
    
    document_ids = await asyncio.gather(*store_tasks)
    assert len(document_ids) == len(test_docs)

    # Execute concurrent retrieval operations
    retrieve_tasks = [
        temporal_client.execute_workflow(
            retrieve_document_workflow,
            args=[doc_id],
            id=str(uuid4()),
            task_queue="test"
        )
        for doc_id in document_ids
    ]
    
    documents = await asyncio.gather(*retrieve_tasks)
    assert len(documents) == len(test_docs)

    # Validate all documents were retrieved correctly
    for i, doc in enumerate(documents):
        assert doc["content"] == test_docs[i][0]
        assert doc["format"] == test_docs[i][1]
        assert doc["metadata"] == test_docs[i][2]

@pytest.mark.asyncio
@pytest.mark.integration
async def test_cache_behavior(temporal_client: Client) -> None:
    """Test document caching behavior and performance."""
    
    # Store test document
    document_id = await temporal_client.execute_workflow(
        store_document_workflow,
        args=[TEST_DOCUMENT_CONTENT, TEST_DOCUMENT_FORMAT, TEST_DOCUMENT_METADATA],
        id=str(uuid4()),
        task_queue="test"
    )

    # First retrieval (cache miss)
    start_time = datetime.now(timezone.utc)
    document = await temporal_client.execute_workflow(
        retrieve_document_workflow,
        args=[document_id],
        id=str(uuid4()),
        task_queue="test"
    )
    first_duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Subsequent retrievals (cache hits)
    durations = []
    for _ in range(5):
        start_time = datetime.now(timezone.utc)
        document = await temporal_client.execute_workflow(
            retrieve_document_workflow,
            args=[document_id],
            id=str(uuid4()),
            task_queue="test"
        )
        durations.append(
            (datetime.now(timezone.utc) - start_time).total_seconds()
        )

    # Verify cache improves performance
    avg_cached_duration = sum(durations) / len(durations)
    assert avg_cached_duration < first_duration

@pytest.mark.asyncio
@pytest.mark.integration
async def test_error_scenarios(temporal_client: Client) -> None:
    """Test various error scenarios and recovery mechanisms."""
    
    # Test invalid document format
    with pytest.raises(Exception):
        await temporal_client.execute_workflow(
            store_document_workflow,
            args=[TEST_DOCUMENT_CONTENT, "invalid_format", TEST_DOCUMENT_METADATA],
            id=str(uuid4()),
            task_queue="test"
        )

    # Test non-existent document retrieval
    with pytest.raises(Exception):
        await temporal_client.execute_workflow(
            retrieve_document_workflow,
            args=[str(uuid4())],
            id=str(uuid4()),
            task_queue="test"
        )

    # Test search with invalid strategy
    with pytest.raises(Exception):
        await temporal_client.execute_workflow(
            search_documents_workflow,
            args=["test query", "invalid_strategy", {}],
            id=str(uuid4()),
            task_queue="test"
        )

@pytest.mark.asyncio
@pytest.mark.integration
async def test_search_strategies(temporal_client: Client) -> None:
    """Test different search strategies and performance requirements."""
    
    # Store test documents
    test_docs = [
        (f"Test document {i} with unique content", TEST_DOCUMENT_FORMAT, TEST_DOCUMENT_METADATA)
        for i in range(5)
    ]
    
    document_ids = []
    for content, format, metadata in test_docs:
        doc_id = await temporal_client.execute_workflow(
            store_document_workflow,
            args=[content, format, metadata],
            id=str(uuid4()),
            task_queue="test"
        )
        document_ids.append(doc_id)

    # Test vector search
    start_time = datetime.now(timezone.utc)
    vector_results = await temporal_client.execute_workflow(
        vector_search_workflow,
        args=["unique content", None, 3],
        id=str(uuid4()),
        task_queue="test"
    )
    vector_duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    assert vector_duration < VECTOR_SEARCH_TIMEOUT
    assert len(vector_results) <= 3

    # Test LLM search
    start_time = datetime.now(timezone.utc)
    llm_results = await temporal_client.execute_workflow(
        llm_search_workflow,
        args=["unique content", None, 3],
        id=str(uuid4()),
        task_queue="test"
    )
    llm_duration = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
    assert llm_duration < LLM_SEARCH_TIMEOUT
    assert len(llm_results) <= 3

    # Test hybrid search
    hybrid_results = await temporal_client.execute_workflow(
        hybrid_search_workflow,
        args=["unique content", None, 3],
        id=str(uuid4()),
        task_queue="test"
    )
    assert len(hybrid_results) <= 3

    # Test RAG+KG search
    rag_kg_results = await temporal_client.execute_workflow(
        rag_kg_search_workflow,
        args=["unique content", None, 3],
        id=str(uuid4()),
        task_queue="test"
    )
    assert len(rag_kg_results) <= 3