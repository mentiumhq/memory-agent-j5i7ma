"""
FastAPI endpoint handlers for document operations with enterprise-grade features including
comprehensive telemetry, rate limiting, circuit breakers, and enhanced security controls.

Version:
- fastapi==0.100.0+
- temporalio==1.0.0
- opentelemetry-api==1.20.0
"""

import logging
from typing import Dict, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from opentelemetry import trace
from prometheus_client import Counter, Histogram
from circuitbreaker import circuit
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..models.request import (
    StoreDocumentRequest,
    GetDocumentRequest,
    SearchDocumentRequest
)
from ...workflows.document import (
    store_document_workflow,
    retrieve_document_workflow,
    search_documents_workflow,
    update_document_workflow,
    delete_document_workflow
)
from ...core.errors import StorageError, ErrorCode
from ...core.telemetry import create_tracer
from ...config.logging import get_logger

# Initialize logging and tracing
LOGGER = get_logger(__name__)
TRACER = create_tracer('document_endpoints')

# Initialize metrics
document_operations = Counter(
    'document_operations_total',
    'Total document operations',
    ['operation']
)
operation_duration = Histogram(
    'document_operation_duration_seconds',
    'Document operation duration'
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize router
router = APIRouter(prefix="/v1/documents", tags=["documents"])

# Circuit breaker configuration
FAILURE_THRESHOLD = 5
RECOVERY_TIMEOUT = 60

@router.post("/store", status_code=status.HTTP_201_CREATED)
@limiter.limit("50/minute")
@circuit(failure_threshold=FAILURE_THRESHOLD, recovery_timeout=RECOVERY_TIMEOUT)
async def store_document(
    request: StoreDocumentRequest,
    fastapi_request: Request,
    temporal_client=Depends()
) -> Dict:
    """
    Store a new document with content and metadata.
    Implements rate limiting, circuit breaker, and comprehensive telemetry.

    Args:
        request: Validated document store request
        fastapi_request: FastAPI request instance
        temporal_client: Temporal client dependency

    Returns:
        Dict containing stored document ID and metadata

    Raises:
        HTTPException: If document storage fails
    """
    with TRACER.start_as_current_span("store_document") as span:
        try:
            # Add request context to span
            span.set_attribute("content_length", len(request.content))
            span.set_attribute("format", request.format)
            
            # Execute store workflow
            document = await store_document_workflow(
                temporal_client,
                content=request.content,
                format=request.format,
                metadata=request.metadata
            )
            
            # Record metrics
            document_operations.labels(operation="store").inc()
            
            LOGGER.info(
                "Document stored successfully",
                extra={
                    "document_id": str(document.id),
                    "format": request.format,
                    "trace_id": span.get_span_context().trace_id
                }
            )
            
            return {
                "document_id": str(document.id),
                "status": "stored",
                "metadata": document.metadata
            }
            
        except StorageError as e:
            LOGGER.error(
                f"Document storage failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

@router.get("/retrieve")
@limiter.limit("100/minute")
@circuit(failure_threshold=FAILURE_THRESHOLD, recovery_timeout=RECOVERY_TIMEOUT)
async def get_document(
    request: GetDocumentRequest,
    fastapi_request: Request,
    temporal_client=Depends()
) -> Dict:
    """
    Retrieve document by ID with caching and monitoring.

    Args:
        request: Validated document retrieval request
        fastapi_request: FastAPI request instance
        temporal_client: Temporal client dependency

    Returns:
        Dict containing document data and metadata

    Raises:
        HTTPException: If document retrieval fails
    """
    with TRACER.start_as_current_span("get_document") as span:
        try:
            # Add request context to span
            span.set_attribute("document_id", str(request.document_id))
            
            # Execute retrieve workflow
            document = await retrieve_document_workflow(
                temporal_client,
                document_id=str(request.document_id)
            )
            
            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Document not found: {request.document_id}"
                )
            
            # Record metrics
            document_operations.labels(operation="retrieve").inc()
            
            LOGGER.info(
                "Document retrieved successfully",
                extra={
                    "document_id": str(request.document_id),
                    "trace_id": span.get_span_context().trace_id
                }
            )
            
            return {
                "document_id": str(document.id),
                "content": document.content,
                "format": document.format,
                "metadata": document.metadata,
                "token_count": document.token_count
            }
            
        except StorageError as e:
            LOGGER.error(
                f"Document retrieval failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )

@router.post("/search")
@limiter.limit("50/minute")
@circuit(failure_threshold=FAILURE_THRESHOLD, recovery_timeout=RECOVERY_TIMEOUT)
async def search_documents(
    request: SearchDocumentRequest,
    fastapi_request: Request,
    temporal_client=Depends()
) -> List[Dict]:
    """
    Search documents using specified strategy with performance optimization.

    Args:
        request: Validated document search request
        fastapi_request: FastAPI request instance
        temporal_client: Temporal client dependency

    Returns:
        List of matching documents with relevance scores

    Raises:
        HTTPException: If document search fails
    """
    with TRACER.start_as_current_span("search_documents") as span:
        try:
            # Add request context to span
            span.set_attribute("query", request.query)
            span.set_attribute("strategy", request.strategy)
            
            # Execute search workflow
            documents = await search_documents_workflow(
                temporal_client,
                query=request.query,
                strategy=request.strategy,
                filters=request.filters,
                limit=request.limit
            )
            
            # Record metrics
            document_operations.labels(operation="search").inc()
            
            LOGGER.info(
                "Document search completed",
                extra={
                    "query": request.query,
                    "strategy": request.strategy,
                    "result_count": len(documents),
                    "trace_id": span.get_span_context().trace_id
                }
            )
            
            return [
                {
                    "document_id": str(doc.id),
                    "content": doc.content,
                    "format": doc.format,
                    "metadata": doc.metadata,
                    "relevance_score": score
                }
                for doc, score in documents
            ]
            
        except StorageError as e:
            LOGGER.error(
                f"Document search failed: {str(e)}",
                exc_info=True,
                extra={"trace_id": span.get_span_context().trace_id}
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e)
            )