"""
Temporal workflow activities for document storage operations.
Implements atomic, fault-tolerant, and secure document operations with comprehensive
monitoring and error handling.

Version:
- temporalio==1.0.0
- opentelemetry-api==1.20.0
"""

import logging
from typing import Dict, Any, Optional, Tuple
from datetime import timedelta
from uuid import uuid4

from temporalio import activity
from temporalio.common import RetryPolicy
from temporalio.activity import ActivityInterface
from opentelemetry.trace import Status, StatusCode
from pydantic import ValidationError

from services.storage import StorageService
from core.errors import StorageError, ErrorCode
from core.telemetry import create_tracer
from config.logging import get_logger

# Initialize logging and tracing
LOGGER = get_logger(__name__)
TRACER = create_tracer('storage_activities')

# Configure retry policy for storage activities
STORAGE_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    non_retryable_error_types=[ValidationError]
)

@activity.defn(name='store_document', retry_policy=STORAGE_RETRY_POLICY)
async def store_document_activity(content: bytes, metadata: Dict[str, Any]) -> str:
    """
    Temporal activity for securely storing a document with encryption and validation.

    Args:
        content: Document content as bytes
        metadata: Document metadata dictionary

    Returns:
        str: Stored document ID

    Raises:
        StorageError: If storage operation fails
        ValidationError: If document validation fails
    """
    with TRACER.start_as_current_span("store_document_activity") as span:
        try:
            # Add trace context to metadata
            metadata['trace_id'] = str(span.get_span_context().trace_id)
            metadata['correlation_id'] = str(uuid4())

            # Validate document size
            if len(content) > metadata.get('max_size', 10_000_000):  # 10MB default
                raise StorageError(
                    "Document exceeds maximum size limit",
                    ErrorCode.VALIDATION_ERROR,
                    {"size": len(content)}
                )

            # Get storage service from activity context
            storage_service = activity.info().heartbeat_details.get('storage_service')
            if not storage_service:
                storage_service = StorageService()

            # Store document with monitoring
            span.set_attribute("document.size", len(content))
            document_id = await storage_service.store_document(content, metadata)

            # Set success status and return
            span.set_status(Status(StatusCode.OK))
            LOGGER.info(
                "Document stored successfully",
                extra={
                    "document_id": document_id,
                    "size": len(content),
                    "correlation_id": metadata['correlation_id']
                }
            )
            return document_id

        except ValidationError as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error(
                "Document validation failed",
                extra={"error": str(e), "metadata": metadata}
            )
            raise

        except StorageError as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error(
                "Storage operation failed",
                extra={"error": str(e), "error_code": e.error_code.value}
            )
            raise

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error("Unexpected error in store_document_activity", exc_info=True)
            raise StorageError(
                "Failed to store document",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

@activity.defn(name='retrieve_document', retry_policy=STORAGE_RETRY_POLICY)
async def retrieve_document_activity(document_id: str) -> Tuple[bytes, Dict[str, Any]]:
    """
    Temporal activity for securely retrieving and decrypting a document.

    Args:
        document_id: Unique document identifier

    Returns:
        Tuple containing document content and metadata

    Raises:
        StorageError: If retrieval operation fails
        ValidationError: If document validation fails
    """
    with TRACER.start_as_current_span("retrieve_document_activity") as span:
        try:
            # Add trace attributes
            span.set_attribute("document.id", document_id)
            correlation_id = str(uuid4())

            # Get storage service from activity context
            storage_service = activity.info().heartbeat_details.get('storage_service')
            if not storage_service:
                storage_service = StorageService()

            # Retrieve document with monitoring
            content, metadata = await storage_service.retrieve_document(document_id)

            # Add correlation and trace data to metadata
            metadata['correlation_id'] = correlation_id
            metadata['trace_id'] = str(span.get_span_context().trace_id)

            # Set success status and return
            span.set_status(Status(StatusCode.OK))
            LOGGER.info(
                "Document retrieved successfully",
                extra={
                    "document_id": document_id,
                    "size": len(content),
                    "correlation_id": correlation_id
                }
            )
            return content, metadata

        except StorageError as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error(
                "Document retrieval failed",
                extra={
                    "document_id": document_id,
                    "error": str(e),
                    "error_code": e.error_code.value
                }
            )
            raise

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error("Unexpected error in retrieve_document_activity", exc_info=True)
            raise StorageError(
                "Failed to retrieve document",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

@activity.defn(name='delete_document', retry_policy=STORAGE_RETRY_POLICY)
async def delete_document_activity(document_id: str) -> bool:
    """
    Temporal activity for securely deleting a document.

    Args:
        document_id: Unique document identifier

    Returns:
        bool: True if document was deleted successfully

    Raises:
        StorageError: If deletion operation fails
    """
    with TRACER.start_as_current_span("delete_document_activity") as span:
        try:
            # Add trace attributes
            span.set_attribute("document.id", document_id)
            correlation_id = str(uuid4())

            # Get storage service from activity context
            storage_service = activity.info().heartbeat_details.get('storage_service')
            if not storage_service:
                storage_service = StorageService()

            # Delete document with monitoring
            success = await storage_service.delete_document(document_id)

            # Set success status and return
            span.set_status(Status(StatusCode.OK))
            LOGGER.info(
                "Document deleted successfully",
                extra={
                    "document_id": document_id,
                    "correlation_id": correlation_id
                }
            )
            return success

        except StorageError as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error(
                "Document deletion failed",
                extra={
                    "document_id": document_id,
                    "error": str(e),
                    "error_code": e.error_code.value
                }
            )
            raise

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error("Unexpected error in delete_document_activity", exc_info=True)
            raise StorageError(
                "Failed to delete document",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

@activity.defn(name='update_document', retry_policy=STORAGE_RETRY_POLICY)
async def update_document_activity(
    document_id: str,
    content: bytes,
    metadata: Dict[str, Any]
) -> str:
    """
    Temporal activity for securely updating an existing document.

    Args:
        document_id: Unique document identifier
        content: Updated document content
        metadata: Updated document metadata

    Returns:
        str: Updated document ID

    Raises:
        StorageError: If update operation fails
        ValidationError: If document validation fails
    """
    with TRACER.start_as_current_span("update_document_activity") as span:
        try:
            # Add trace context to metadata
            metadata['trace_id'] = str(span.get_span_context().trace_id)
            metadata['correlation_id'] = str(uuid4())
            span.set_attribute("document.id", document_id)
            span.set_attribute("document.size", len(content))

            # Validate document size
            if len(content) > metadata.get('max_size', 10_000_000):  # 10MB default
                raise StorageError(
                    "Document exceeds maximum size limit",
                    ErrorCode.VALIDATION_ERROR,
                    {"size": len(content)}
                )

            # Get storage service from activity context
            storage_service = activity.info().heartbeat_details.get('storage_service')
            if not storage_service:
                storage_service = StorageService()

            # Update document with monitoring
            updated_id = await storage_service.update_document(
                document_id=document_id,
                content=content,
                metadata=metadata
            )

            # Set success status and return
            span.set_status(Status(StatusCode.OK))
            LOGGER.info(
                "Document updated successfully",
                extra={
                    "document_id": updated_id,
                    "size": len(content),
                    "correlation_id": metadata['correlation_id']
                }
            )
            return updated_id

        except ValidationError as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error(
                "Document validation failed",
                extra={"error": str(e), "metadata": metadata}
            )
            raise

        except StorageError as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error(
                "Document update failed",
                extra={
                    "document_id": document_id,
                    "error": str(e),
                    "error_code": e.error_code.value
                }
            )
            raise

        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            LOGGER.error("Unexpected error in update_document_activity", exc_info=True)
            raise StorageError(
                "Failed to update document",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )