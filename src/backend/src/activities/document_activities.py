"""
Temporal workflow activities for document operations including storage, retrieval, search,
update and deletion. Implements fault-tolerant document processing with comprehensive
error handling, monitoring, and security features.

Version:
- temporalio==1.0.0
- opentelemetry-api==1.20.0
"""

import logging
from typing import Dict, Optional, List, Any
from temporalio import activity
from opentelemetry import trace

from ..services.document import DocumentService
from ..api.models.document import Document, DocumentCreate, DocumentResponse
from ..core.errors import StorageError, ErrorCode
from ..core.telemetry import create_tracer
from ..config.logging import get_logger

# Initialize logging and tracing
LOGGER = get_logger(__name__)
TRACER = create_tracer('document_activities')

# Activity retry configuration
RETRY_POLICY = {
    'initial_interval': 1,
    'backoff_coefficient': 2,
    'maximum_attempts': 3,
    'non_retryable_error_types': ['ValidationError', 'SecurityError']
}

# Activity timeouts (in seconds)
ACTIVITY_TIMEOUTS = {
    'schedule_to_close': 30,
    'start_to_close': 25,
    'schedule_to_start': 5,
    'heartbeat': 2
}

@activity.defn(name='store_document_activity')
@activity.retry_policy(RETRY_POLICY)
@activity.timeout(ACTIVITY_TIMEOUTS)
async def store_document_activity(
    content: str,
    format: str,
    metadata: Optional[Dict] = None
) -> Document:
    """
    Store document with content and metadata with comprehensive error handling.

    Args:
        content: Document content
        format: Document format (text, markdown, json)
        metadata: Optional document metadata

    Returns:
        Document: Stored document instance

    Raises:
        StorageError: If document storage fails
    """
    with TRACER.start_as_current_span("store_document_activity") as span:
        try:
            # Create document model with validation
            doc_create = DocumentCreate(
                content=content,
                format=format,
                metadata=metadata or {}
            )

            # Get document service instance
            document_service = DocumentService()

            # Store document with monitoring
            span.set_attribute("document.format", format)
            span.set_attribute("document.content_length", len(content))

            document_id = await document_service.store_document(
                content=doc_create.content,
                metadata=doc_create.metadata
            )

            LOGGER.info(
                "Document stored successfully",
                extra={
                    "document_id": document_id,
                    "format": format,
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return document_id

        except Exception as e:
            LOGGER.error(
                f"Document storage failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise StorageError(
                "Failed to store document",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

@activity.defn(name='retrieve_document_activity')
@activity.retry_policy(RETRY_POLICY)
@activity.timeout(ACTIVITY_TIMEOUTS)
async def retrieve_document_activity(document_id: str) -> DocumentResponse:
    """
    Retrieve document by ID with error handling and monitoring.

    Args:
        document_id: Document identifier

    Returns:
        DocumentResponse: Retrieved document with metadata

    Raises:
        StorageError: If document retrieval fails
    """
    with TRACER.start_as_current_span("retrieve_document_activity") as span:
        try:
            span.set_attribute("document.id", document_id)

            # Get document service instance
            document_service = DocumentService()

            # Retrieve document
            document = await document_service.retrieve_document(document_id)

            if not document:
                raise StorageError(
                    f"Document not found: {document_id}",
                    ErrorCode.DOCUMENT_NOT_FOUND,
                    {"document_id": document_id}
                )

            # Convert to response model
            response = DocumentResponse.from_orm(document)

            LOGGER.info(
                "Document retrieved successfully",
                extra={
                    "document_id": document_id,
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return response

        except StorageError:
            raise
        except Exception as e:
            LOGGER.error(
                f"Document retrieval failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise StorageError(
                "Failed to retrieve document",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

@activity.defn(name='search_documents_activity')
@activity.retry_policy(RETRY_POLICY)
@activity.timeout(ACTIVITY_TIMEOUTS)
async def search_documents_activity(
    query: str,
    strategy: str = "hybrid",
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 10
) -> List[DocumentResponse]:
    """
    Search documents using specified strategy with monitoring.

    Args:
        query: Search query string
        strategy: Search strategy (vector, llm, hybrid, rag+kg)
        filters: Optional metadata filters
        limit: Maximum number of results

    Returns:
        List[DocumentResponse]: Matching documents with relevance scores

    Raises:
        StorageError: If search operation fails
    """
    with TRACER.start_as_current_span("search_documents_activity") as span:
        try:
            span.set_attribute("search.query", query)
            span.set_attribute("search.strategy", strategy)
            span.set_attribute("search.limit", limit)

            # Get document service instance
            document_service = DocumentService()

            # Execute search
            results = await document_service.search_documents(
                query=query,
                strategy=strategy,
                filters=filters,
                limit=limit
            )

            # Convert to response models
            responses = [DocumentResponse.from_orm(doc) for doc, _ in results]

            LOGGER.info(
                "Document search completed",
                extra={
                    "query": query,
                    "strategy": strategy,
                    "result_count": len(responses),
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return responses

        except Exception as e:
            LOGGER.error(
                f"Document search failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise StorageError(
                "Failed to search documents",
                ErrorCode.STORAGE_ERROR,
                {"query": query, "error": str(e)}
            )

@activity.defn(name='update_document_activity')
@activity.retry_policy(RETRY_POLICY)
@activity.timeout(ACTIVITY_TIMEOUTS)
async def update_document_activity(
    document_id: str,
    content: Optional[str] = None,
    metadata: Optional[Dict] = None
) -> DocumentResponse:
    """
    Update document content and/or metadata with validation.

    Args:
        document_id: Document identifier
        content: Optional new content
        metadata: Optional new metadata

    Returns:
        DocumentResponse: Updated document instance

    Raises:
        StorageError: If document update fails
    """
    with TRACER.start_as_current_span("update_document_activity") as span:
        try:
            span.set_attribute("document.id", document_id)

            # Get document service instance
            document_service = DocumentService()

            # Update document
            if content is not None:
                await document_service.update_document_content(
                    document_id=document_id,
                    content=content
                )

            if metadata is not None:
                await document_service.update_document_metadata(
                    document_id=document_id,
                    metadata=metadata
                )

            # Retrieve updated document
            updated_doc = await document_service.retrieve_document(document_id)
            response = DocumentResponse.from_orm(updated_doc)

            LOGGER.info(
                "Document updated successfully",
                extra={
                    "document_id": document_id,
                    "trace_id": span.get_span_context().trace_id
                }
            )

            return response

        except Exception as e:
            LOGGER.error(
                f"Document update failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise StorageError(
                "Failed to update document",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

@activity.defn(name='delete_document_activity')
@activity.retry_policy(RETRY_POLICY)
@activity.timeout(ACTIVITY_TIMEOUTS)
async def delete_document_activity(document_id: str) -> bool:
    """
    Delete document with comprehensive cleanup.

    Args:
        document_id: Document identifier

    Returns:
        bool: True if document was deleted

    Raises:
        StorageError: If document deletion fails
    """
    with TRACER.start_as_current_span("delete_document_activity") as span:
        try:
            span.set_attribute("document.id", document_id)

            # Get document service instance
            document_service = DocumentService()

            # Delete document
            deleted = await document_service.delete_document(document_id)

            if deleted:
                LOGGER.info(
                    "Document deleted successfully",
                    extra={
                        "document_id": document_id,
                        "trace_id": span.get_span_context().trace_id
                    }
                )
            else:
                LOGGER.warning(
                    "Document not found for deletion",
                    extra={
                        "document_id": document_id,
                        "trace_id": span.get_span_context().trace_id
                    }
                )

            return deleted

        except Exception as e:
            LOGGER.error(
                f"Document deletion failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise StorageError(
                "Failed to delete document",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )