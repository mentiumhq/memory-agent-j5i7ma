"""
Temporal workflow activities for document index management operations.
Implements comprehensive index management with metadata tracking, access pattern analysis,
and intelligent caching optimization.

Version:
- temporalio==1.x
- opentelemetry-api==1.0+
- prometheus-client==0.17+
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from uuid import UUID

from temporalio import activity
from temporalio.common import RetryPolicy

from services.index import IndexService
from core.errors import StorageError, ErrorCode

# Configure logging
logger = logging.getLogger(__name__)

# Initialize index service with caching configuration
index_service = IndexService()

@activity.defn(name='get_document_index', retry_policy=RetryPolicy(
    initial_interval=1,
    maximum_interval=10,
    maximum_attempts=3,
    non_retryable_error_types=["ValueError"]
))
async def get_document_index_activity(document_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Temporal activity to retrieve document index by ID with comprehensive validation.

    Args:
        document_id: UUID of the document to retrieve index for

    Returns:
        Optional[Dict[str, Any]]: Document index data with metadata and access patterns

    Raises:
        StorageError: If retrieval fails or validation errors occur
    """
    try:
        logger.debug(f"Retrieving document index for ID: {document_id}")

        # Validate document_id
        if not isinstance(document_id, UUID):
            raise ValueError("Invalid document ID format")

        # Get index using service
        async with index_service.get_document_index(document_id) as index_data:
            if index_data:
                # Record access for optimization
                async with index_service.record_document_access(document_id) as _:
                    pass

            return index_data

    except ValueError as e:
        logger.error(f"Validation error in get_document_index: {str(e)}")
        raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

    except StorageError as e:
        logger.error(f"Storage error in get_document_index: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error in get_document_index: {str(e)}")
        raise StorageError(
            "Failed to retrieve document index",
            ErrorCode.STORAGE_ERROR,
            {"document_id": str(document_id)}
        )

@activity.defn(name='create_document_index', retry_policy=RetryPolicy(
    initial_interval=1,
    maximum_interval=10,
    maximum_attempts=3,
    non_retryable_error_types=["ValueError"]
))
async def create_document_index_activity(
    document_id: UUID,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Temporal activity to create new document index with metadata validation.

    Args:
        document_id: UUID of the document to create index for
        metadata: Index metadata dictionary

    Returns:
        Dict[str, Any]: Created document index data

    Raises:
        StorageError: If creation fails or validation errors occur
    """
    try:
        logger.debug(f"Creating document index for ID: {document_id}")

        # Validate inputs
        if not isinstance(document_id, UUID):
            raise ValueError("Invalid document ID format")
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        # Add creation timestamp to metadata
        metadata["_created_at"] = datetime.now(timezone.utc).isoformat()

        # Create index using service
        async with index_service.create_document_index(document_id, metadata) as index_data:
            return index_data

    except ValueError as e:
        logger.error(f"Validation error in create_document_index: {str(e)}")
        raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

    except StorageError as e:
        logger.error(f"Storage error in create_document_index: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error in create_document_index: {str(e)}")
        raise StorageError(
            "Failed to create document index",
            ErrorCode.STORAGE_ERROR,
            {"document_id": str(document_id)}
        )

@activity.defn(name='update_index_metadata', retry_policy=RetryPolicy(
    initial_interval=1,
    maximum_interval=10,
    maximum_attempts=3,
    non_retryable_error_types=["ValueError"]
))
async def update_index_metadata_activity(
    document_id: UUID,
    metadata: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Temporal activity to update document index metadata with change tracking.

    Args:
        document_id: UUID of the document to update index for
        metadata: New metadata dictionary

    Returns:
        Optional[Dict[str, Any]]: Updated index data or None if not found

    Raises:
        StorageError: If update fails or validation errors occur
    """
    try:
        logger.debug(f"Updating metadata for document index ID: {document_id}")

        # Validate inputs
        if not isinstance(document_id, UUID):
            raise ValueError("Invalid document ID format")
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        # Add update timestamp to metadata
        metadata["_updated_at"] = datetime.now(timezone.utc).isoformat()

        # Update index using service
        async with index_service.update_index_metadata(document_id, metadata) as index_data:
            return index_data

    except ValueError as e:
        logger.error(f"Validation error in update_index_metadata: {str(e)}")
        raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

    except StorageError as e:
        logger.error(f"Storage error in update_index_metadata: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error in update_index_metadata: {str(e)}")
        raise StorageError(
            "Failed to update index metadata",
            ErrorCode.STORAGE_ERROR,
            {"document_id": str(document_id)}
        )

@activity.defn(name='record_document_access', retry_policy=RetryPolicy(
    initial_interval=1,
    maximum_interval=10,
    maximum_attempts=3,
    non_retryable_error_types=["ValueError"]
))
async def record_document_access_activity(document_id: UUID) -> Optional[Dict[str, Any]]:
    """
    Temporal activity to record and analyze document access patterns.

    Args:
        document_id: UUID of the document to record access for

    Returns:
        Optional[Dict[str, Any]]: Updated access metrics and patterns

    Raises:
        StorageError: If access recording fails
    """
    try:
        logger.debug(f"Recording access for document ID: {document_id}")

        # Validate document_id
        if not isinstance(document_id, UUID):
            raise ValueError("Invalid document ID format")

        # Record access using service
        async with index_service.record_document_access(document_id) as access_data:
            return access_data

    except ValueError as e:
        logger.error(f"Validation error in record_document_access: {str(e)}")
        raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

    except StorageError as e:
        logger.error(f"Storage error in record_document_access: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error in record_document_access: {str(e)}")
        raise StorageError(
            "Failed to record document access",
            ErrorCode.STORAGE_ERROR,
            {"document_id": str(document_id)}
        )

@activity.defn(name='get_frequently_accessed', retry_policy=RetryPolicy(
    initial_interval=1,
    maximum_interval=10,
    maximum_attempts=3,
    non_retryable_error_types=["ValueError"]
))
async def get_frequently_accessed_activity(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Temporal activity to retrieve and analyze frequently accessed documents.

    Args:
        limit: Maximum number of results to return (default: 10)

    Returns:
        List[Dict[str, Any]]: Sorted list of frequently accessed documents with analytics

    Raises:
        StorageError: If retrieval fails or validation errors occur
    """
    try:
        logger.debug(f"Retrieving frequently accessed documents with limit: {limit}")

        # Validate limit
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("Limit must be a positive integer")

        # Get frequently accessed documents using service
        async with index_service.get_frequently_accessed(limit) as documents:
            return documents

    except ValueError as e:
        logger.error(f"Validation error in get_frequently_accessed: {str(e)}")
        raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

    except StorageError as e:
        logger.error(f"Storage error in get_frequently_accessed: {str(e)}")
        raise

    except Exception as e:
        logger.error(f"Unexpected error in get_frequently_accessed: {str(e)}")
        raise StorageError(
            "Failed to retrieve frequently accessed documents",
            ErrorCode.STORAGE_ERROR,
            {"limit": limit}
        )