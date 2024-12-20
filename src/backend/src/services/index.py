"""
Service layer implementation for document indexing operations.
Provides high-level business logic for managing document indexes with async support,
enhanced validation, and telemetry capabilities.

Version:
- SQLAlchemy==2.0+
- opentelemetry-api==1.0+
- prometheus-client==0.17+
"""

import logging
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone
from prometheus_client import Counter, Histogram

from repositories.index import IndexRepository
from core.errors import StorageError, ErrorCode

# Configure logging
logger = logging.getLogger(__name__)

# Monitoring metrics
index_operation_counter = Counter(
    'index_operations_total',
    'Total number of index operations',
    ['operation_type']
)
index_operation_duration = Histogram(
    'index_operation_duration_seconds',
    'Duration of index operations',
    ['operation_type']
)
index_error_counter = Counter(
    'index_errors_total',
    'Total number of index operation errors',
    ['error_type']
)

class IndexService:
    """
    Service class for managing document indexes with comprehensive error handling,
    validation, and telemetry support.
    """

    def __init__(self) -> None:
        """Initialize index service with repository and monitoring setup."""
        self._repository = IndexRepository()
        self._validation_enabled = True
        self._max_metadata_size = 1024 * 1024  # 1MB limit for metadata

    @asynccontextmanager
    async def get_document_index(self, document_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve document index with comprehensive error handling and telemetry.

        Args:
            document_id: UUID of the document to retrieve index for

        Returns:
            Optional[Dict[str, Any]]: Document index data or None if not found

        Raises:
            StorageError: If retrieval fails
        """
        start_time = datetime.now(timezone.utc)
        try:
            # Record operation attempt
            index_operation_counter.labels(operation_type='get').inc()

            # Validate document_id
            if not isinstance(document_id, UUID):
                raise ValueError("Invalid document ID format")

            # Get index from repository
            with self._repository as repo:
                index = repo.get_by_document_id(document_id)

                if index:
                    # Convert to dictionary for response
                    result = index.to_dict()
                    yield result
                else:
                    yield None

        except ValueError as e:
            index_error_counter.labels(error_type='validation').inc()
            logger.error(f"Validation error in get_document_index: {str(e)}")
            raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

        except Exception as e:
            index_error_counter.labels(error_type='storage').inc()
            logger.error(f"Error retrieving document index: {str(e)}")
            raise StorageError(
                "Failed to retrieve document index",
                ErrorCode.STORAGE_ERROR,
                {"document_id": str(document_id)}
            )

        finally:
            # Record operation duration
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            index_operation_duration.labels(operation_type='get').observe(duration)

    @asynccontextmanager
    async def create_document_index(
        self,
        document_id: UUID,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create new document index with validation and telemetry.

        Args:
            document_id: UUID of the document to create index for
            metadata: Index metadata dictionary

        Returns:
            Dict[str, Any]: Created index data

        Raises:
            StorageError: If creation fails or validation errors occur
        """
        start_time = datetime.now(timezone.utc)
        try:
            # Record operation attempt
            index_operation_counter.labels(operation_type='create').inc()

            # Validate inputs
            if not isinstance(document_id, UUID):
                raise ValueError("Invalid document ID format")
            if not isinstance(metadata, dict):
                raise ValueError("Metadata must be a dictionary")
            if len(str(metadata)) > self._max_metadata_size:
                raise ValueError("Metadata size exceeds limit")

            # Create index using repository
            with self._repository as repo:
                index = repo.create_index(document_id, metadata)
                result = index.to_dict()
                yield result

        except ValueError as e:
            index_error_counter.labels(error_type='validation').inc()
            logger.error(f"Validation error in create_document_index: {str(e)}")
            raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

        except Exception as e:
            index_error_counter.labels(error_type='storage').inc()
            logger.error(f"Error creating document index: {str(e)}")
            raise StorageError(
                "Failed to create document index",
                ErrorCode.STORAGE_ERROR,
                {"document_id": str(document_id)}
            )

        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            index_operation_duration.labels(operation_type='create').observe(duration)

    @asynccontextmanager
    async def update_index_metadata(
        self,
        document_id: UUID,
        metadata: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update index metadata with validation and telemetry.

        Args:
            document_id: UUID of the document to update index for
            metadata: New metadata dictionary

        Returns:
            Optional[Dict[str, Any]]: Updated index data or None if not found

        Raises:
            StorageError: If update fails or validation errors occur
        """
        start_time = datetime.now(timezone.utc)
        try:
            # Record operation attempt
            index_operation_counter.labels(operation_type='update').inc()

            # Validate inputs
            if not isinstance(document_id, UUID):
                raise ValueError("Invalid document ID format")
            if not isinstance(metadata, dict):
                raise ValueError("Metadata must be a dictionary")
            if len(str(metadata)) > self._max_metadata_size:
                raise ValueError("Metadata size exceeds limit")

            # Update index using repository
            with self._repository as repo:
                index = repo.update_metadata(document_id, metadata)
                if index:
                    result = index.to_dict()
                    yield result
                else:
                    yield None

        except ValueError as e:
            index_error_counter.labels(error_type='validation').inc()
            logger.error(f"Validation error in update_index_metadata: {str(e)}")
            raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

        except Exception as e:
            index_error_counter.labels(error_type='storage').inc()
            logger.error(f"Error updating index metadata: {str(e)}")
            raise StorageError(
                "Failed to update index metadata",
                ErrorCode.STORAGE_ERROR,
                {"document_id": str(document_id)}
            )

        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            index_operation_duration.labels(operation_type='update').observe(duration)

    @asynccontextmanager
    async def record_document_access(self, document_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Record document access with timestamp validation and telemetry.

        Args:
            document_id: UUID of the document to record access for

        Returns:
            Optional[Dict[str, Any]]: Updated index data or None if not found

        Raises:
            StorageError: If access recording fails
        """
        start_time = datetime.now(timezone.utc)
        try:
            # Record operation attempt
            index_operation_counter.labels(operation_type='access').inc()

            # Validate document_id
            if not isinstance(document_id, UUID):
                raise ValueError("Invalid document ID format")

            # Record access using repository
            with self._repository as repo:
                index = repo.record_access(document_id)
                if index:
                    result = index.to_dict()
                    yield result
                else:
                    yield None

        except ValueError as e:
            index_error_counter.labels(error_type='validation').inc()
            logger.error(f"Validation error in record_document_access: {str(e)}")
            raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

        except Exception as e:
            index_error_counter.labels(error_type='storage').inc()
            logger.error(f"Error recording document access: {str(e)}")
            raise StorageError(
                "Failed to record document access",
                ErrorCode.STORAGE_ERROR,
                {"document_id": str(document_id)}
            )

        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            index_operation_duration.labels(operation_type='access').observe(duration)

    @asynccontextmanager
    async def get_frequently_accessed(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most frequently accessed documents with analytics and telemetry.

        Args:
            limit: Maximum number of results to return

        Returns:
            List[Dict[str, Any]]: List of index data with access patterns

        Raises:
            StorageError: If retrieval fails
        """
        start_time = datetime.now(timezone.utc)
        try:
            # Record operation attempt
            index_operation_counter.labels(operation_type='frequent').inc()

            # Validate limit
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError("Limit must be a positive integer")

            # Get frequently accessed documents
            with self._repository as repo:
                indexes = repo.get_most_accessed(limit=limit)
                result = [index.to_dict() for index in indexes]
                yield result

        except ValueError as e:
            index_error_counter.labels(error_type='validation').inc()
            logger.error(f"Validation error in get_frequently_accessed: {str(e)}")
            raise StorageError(str(e), ErrorCode.VALIDATION_ERROR)

        except Exception as e:
            index_error_counter.labels(error_type='storage').inc()
            logger.error(f"Error retrieving frequently accessed documents: {str(e)}")
            raise StorageError(
                "Failed to retrieve frequently accessed documents",
                ErrorCode.STORAGE_ERROR,
                {"limit": limit}
            )

        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            index_operation_duration.labels(operation_type='frequent').observe(duration)