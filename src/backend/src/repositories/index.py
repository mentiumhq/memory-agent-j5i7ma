"""
Repository implementation for document index operations.
Handles CRUD operations for document indexes with metadata management,
access tracking, and cache optimization through access pattern analysis.

Version:
- SQLAlchemy==2.0+
- SQLAlchemy-Utils==0.41.1
"""

import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from uuid import UUID

from .base import BaseRepository
from db.models.document_index import DocumentIndex
from core.errors import StorageError, ErrorCode

# Configure logging
logger = logging.getLogger(__name__)

class IndexRepository(BaseRepository[DocumentIndex]):
    """
    Repository class for managing document indexes with comprehensive access pattern tracking
    and caching optimization capabilities.
    """

    def __init__(self) -> None:
        """Initialize index repository with DocumentIndex model."""
        super().__init__(DocumentIndex)
        self._model_class = DocumentIndex

    def get_by_document_id(self, document_id: UUID) -> Optional[DocumentIndex]:
        """
        Retrieve index by document ID with access tracking.

        Args:
            document_id: UUID of the document to retrieve index for

        Returns:
            DocumentIndex if found, None otherwise

        Raises:
            StorageError: If database operation fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            index = (
                self._session.query(self._model_class)
                .filter(self._model_class.document_id == document_id)
                .first()
            )

            if index:
                # Record access if found
                index.record_access()
                self._session.commit()

            return index

        except Exception as e:
            logger.error(f"Error retrieving index for document {document_id}: {str(e)}")
            raise StorageError(
                "Failed to retrieve document index",
                ErrorCode.STORAGE_ERROR,
                {"document_id": str(document_id), "error": str(e)}
            )

    def create_index(self, document_id: UUID, metadata: Dict[str, Any]) -> DocumentIndex:
        """
        Create new document index with metadata validation.

        Args:
            document_id: UUID of the document to create index for
            metadata: Index metadata dictionary

        Returns:
            Created DocumentIndex instance

        Raises:
            StorageError: If creation fails or validation errors occur
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            # Validate metadata is a dictionary
            if not isinstance(metadata, dict):
                raise ValueError("Metadata must be a dictionary")

            # Create new index instance
            index = DocumentIndex(
                document_id=document_id,
                metadata=metadata
            )

            # Use base class create method
            created_index = self.create(index)

            logger.info(f"Created index for document {document_id}")
            return created_index

        except ValueError as e:
            logger.error(f"Validation error creating index: {str(e)}")
            raise StorageError(
                str(e),
                ErrorCode.VALIDATION_ERROR,
                {"document_id": str(document_id)}
            )
        except Exception as e:
            logger.error(f"Error creating index: {str(e)}")
            raise StorageError(
                "Failed to create document index",
                ErrorCode.STORAGE_ERROR,
                {"document_id": str(document_id), "error": str(e)}
            )

    def update_metadata(self, document_id: UUID, metadata: Dict[str, Any]) -> Optional[DocumentIndex]:
        """
        Update index metadata with validation.

        Args:
            document_id: UUID of the document to update index for
            metadata: New metadata dictionary

        Returns:
            Updated DocumentIndex if found, None otherwise

        Raises:
            StorageError: If update fails or validation errors occur
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            # Get existing index
            index = self.get_by_document_id(document_id)
            if not index:
                return None

            # Update metadata
            index.update_metadata(metadata)

            # Use base class update method
            updated_index = self.update(index)

            logger.info(f"Updated metadata for document {document_id}")
            return updated_index

        except ValueError as e:
            logger.error(f"Validation error updating metadata: {str(e)}")
            raise StorageError(
                str(e),
                ErrorCode.VALIDATION_ERROR,
                {"document_id": str(document_id)}
            )
        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}")
            raise StorageError(
                "Failed to update document index metadata",
                ErrorCode.STORAGE_ERROR,
                {"document_id": str(document_id), "error": str(e)}
            )

    def record_access(self, document_id: UUID) -> Optional[DocumentIndex]:
        """
        Record document access with timestamp update.

        Args:
            document_id: UUID of the document to record access for

        Returns:
            Updated DocumentIndex if found, None otherwise

        Raises:
            StorageError: If access recording fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            # Get existing index
            index = self.get_by_document_id(document_id)
            if not index:
                return None

            # Record access
            index.record_access()

            # Use base class update method
            updated_index = self.update(index)

            logger.debug(f"Recorded access for document {document_id}")
            return updated_index

        except Exception as e:
            logger.error(f"Error recording access: {str(e)}")
            raise StorageError(
                "Failed to record document access",
                ErrorCode.STORAGE_ERROR,
                {"document_id": str(document_id), "error": str(e)}
            )

    def get_most_accessed(self, limit: int = 10, since_timestamp: Optional[datetime] = None) -> List[DocumentIndex]:
        """
        Get most frequently accessed document indexes for cache optimization.

        Args:
            limit: Maximum number of results to return
            since_timestamp: Optional timestamp to filter access records

        Returns:
            List of DocumentIndex instances ordered by access count

        Raises:
            StorageError: If query fails
            ValueError: If limit is invalid
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            # Validate limit
            if limit <= 0:
                raise ValueError("Limit must be positive")

            # Build base query
            query = self._session.query(self._model_class)

            # Apply timestamp filter if provided
            if since_timestamp:
                query = query.filter(self._model_class.last_accessed >= since_timestamp)

            # Order by access count and get results
            results = (
                query.order_by(self._model_class.access_count.desc())
                .limit(limit)
                .all()
            )

            return results

        except ValueError as e:
            logger.error(f"Validation error in get_most_accessed: {str(e)}")
            raise StorageError(
                str(e),
                ErrorCode.VALIDATION_ERROR,
                {"limit": limit}
            )
        except Exception as e:
            logger.error(f"Error retrieving most accessed indexes: {str(e)}")
            raise StorageError(
                "Failed to retrieve most accessed indexes",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )