"""
Temporal workflow definitions for document operations implementing fault-tolerant processing
with comprehensive retry policies, multi-strategy retrieval, and integrated monitoring.

Version:
- temporalio==1.0.0
- opentelemetry-api==1.20.0
"""

import logging
from typing import Dict, Optional, List
from temporalio import workflow
from opentelemetry import trace

from ..activities.document_activities import (
    store_document_activity,
    retrieve_document_activity,
    search_documents_activity,
    update_document_activity,
    delete_document_activity
)
from ..api.models.document import Document

# Initialize logging
logger = logging.getLogger(__name__)

# Workflow retry configuration
WORKFLOW_RETRY_POLICY = {
    "initial_interval": 1,  # 1 second
    "backoff_coefficient": 2,
    "maximum_attempts": 5,
    "maximum_interval": 60  # 60 seconds
}

# Retrieval strategy configuration
RETRIEVAL_STRATEGIES = {
    "VECTOR": "vector",
    "LLM": "llm",
    "HYBRID": "hybrid",
    "RAG_KG": "rag_kg"
}

# Performance targets
PERFORMANCE_TARGETS = {
    "VECTOR_SEARCH_MS": 500,
    "LLM_SEARCH_MS": 3000,
    "CONCURRENT_REQUESTS": 50
}

@workflow.defn(name='store_document_workflow')
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
@workflow.with_tracing
async def store_document_workflow(
    content: str,
    format: str,
    metadata: Optional[Dict] = None
) -> Document:
    """
    Workflow for storing a new document with content and metadata.
    Implements fault tolerance and automatic retries.

    Args:
        content: Document content
        format: Document format (text, markdown, json)
        metadata: Optional document metadata

    Returns:
        Document: Stored document instance with persistence confirmation

    Raises:
        Exception: If document storage fails after retries
    """
    with trace.get_tracer(__name__).start_as_current_span("store_document_workflow") as span:
        try:
            # Add workflow context to span
            span.set_attribute("document.format", format)
            span.set_attribute("document.content_length", len(content))

            # Execute store activity with retry policy
            document = await workflow.execute_activity(
                store_document_activity,
                args=[content, format, metadata],
                start_to_close_timeout=30,
                retry_policy=WORKFLOW_RETRY_POLICY
            )

            logger.info(
                "Document stored successfully",
                extra={
                    "document_id": str(document.id),
                    "format": format,
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return document

        except Exception as e:
            logger.error(
                f"Document storage workflow failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise

@workflow.defn(name='retrieve_document_workflow')
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
@workflow.with_tracing
async def retrieve_document_workflow(
    document_id: str,
    strategy: str = RETRIEVAL_STRATEGIES["HYBRID"],
    load_content: bool = True
) -> Document:
    """
    Workflow for retrieving a document by ID using configurable retrieval strategies.
    Implements automatic fallback mechanisms and performance monitoring.

    Args:
        document_id: Document identifier
        strategy: Retrieval strategy to use
        load_content: Whether to load full document content

    Returns:
        Document: Retrieved document instance with requested content

    Raises:
        Exception: If document retrieval fails after retries
    """
    with trace.get_tracer(__name__).start_as_current_span("retrieve_document_workflow") as span:
        try:
            # Add workflow context to span
            span.set_attribute("document.id", document_id)
            span.set_attribute("retrieval.strategy", strategy)

            # Execute retrieve activity with retry policy
            document = await workflow.execute_activity(
                retrieve_document_activity,
                args=[document_id, strategy, load_content],
                start_to_close_timeout=30,
                retry_policy=WORKFLOW_RETRY_POLICY
            )

            logger.info(
                "Document retrieved successfully",
                extra={
                    "document_id": document_id,
                    "strategy": strategy,
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return document

        except Exception as e:
            logger.error(
                f"Document retrieval workflow failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise

@workflow.defn(name='search_documents_workflow')
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
@workflow.with_tracing
async def search_documents_workflow(
    query: str,
    strategy: str = RETRIEVAL_STRATEGIES["HYBRID"],
    filters: Optional[Dict] = None
) -> List[Document]:
    """
    Workflow for searching documents using specified strategy with performance optimization.
    Implements multi-strategy search with automatic fallback and monitoring.

    Args:
        query: Search query string
        strategy: Search strategy to use
        filters: Optional metadata filters

    Returns:
        List[Document]: List of matching documents with relevance scores

    Raises:
        Exception: If document search fails after retries
    """
    with trace.get_tracer(__name__).start_as_current_span("search_documents_workflow") as span:
        try:
            # Add workflow context to span
            span.set_attribute("search.query", query)
            span.set_attribute("search.strategy", strategy)

            # Execute search activity with retry policy
            documents = await workflow.execute_activity(
                search_documents_activity,
                args=[query, strategy, filters],
                start_to_close_timeout=30,
                retry_policy=WORKFLOW_RETRY_POLICY
            )

            logger.info(
                "Document search completed",
                extra={
                    "query": query,
                    "strategy": strategy,
                    "result_count": len(documents),
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return documents

        except Exception as e:
            logger.error(
                f"Document search workflow failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise

@workflow.defn(name='update_document_workflow')
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
@workflow.with_tracing
async def update_document_workflow(
    document_id: str,
    content: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> Document:
    """
    Workflow for updating document content and/or metadata with consistency guarantees.
    Implements atomic updates with rollback capability.

    Args:
        document_id: Document identifier
        content: Optional new content
        metadata: Optional new metadata

    Returns:
        Document: Updated document instance

    Raises:
        Exception: If document update fails after retries
    """
    with trace.get_tracer(__name__).start_as_current_span("update_document_workflow") as span:
        try:
            # Add workflow context to span
            span.set_attribute("document.id", document_id)
            if content:
                span.set_attribute("update.content_length", len(content))

            # Execute update activity with retry policy
            document = await workflow.execute_activity(
                update_document_activity,
                args=[document_id, content, metadata],
                start_to_close_timeout=30,
                retry_policy=WORKFLOW_RETRY_POLICY
            )

            logger.info(
                "Document updated successfully",
                extra={
                    "document_id": document_id,
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return document

        except Exception as e:
            logger.error(
                f"Document update workflow failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise

@workflow.defn(name='delete_document_workflow')
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
@workflow.with_tracing
async def delete_document_workflow(document_id: str) -> bool:
    """
    Workflow for deleting a document with comprehensive cleanup.
    Implements cascading deletion of associated resources.

    Args:
        document_id: Document identifier

    Returns:
        bool: True if document was deleted

    Raises:
        Exception: If document deletion fails after retries
    """
    with trace.get_tracer(__name__).start_as_current_span("delete_document_workflow") as span:
        try:
            # Add workflow context to span
            span.set_attribute("document.id", document_id)

            # Execute delete activity with retry policy
            deleted = await workflow.execute_activity(
                delete_document_activity,
                args=[document_id],
                start_to_close_timeout=30,
                retry_policy=WORKFLOW_RETRY_POLICY
            )

            logger.info(
                "Document deletion completed",
                extra={
                    "document_id": document_id,
                    "deleted": deleted,
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return deleted

        except Exception as e:
            logger.error(
                f"Document deletion workflow failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise