"""
Repository implementation for Document entity handling database operations.
Provides comprehensive document management with token-aware chunking and index optimization.

Version:
- SQLAlchemy==2.0+
- SQLAlchemy-Utils==0.41.1
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .base import BaseRepository
from db.models.document import Document
from db.models.document_chunk import DocumentChunk
from db.models.document_index import DocumentIndex
from core.errors import StorageError, ErrorCode

# Configure logging
logger = logging.getLogger(__name__)

class DocumentRepository(BaseRepository[Document]):
    """
    Repository for managing Document entities with support for chunks and indexes.
    Implements token-aware chunking and optimized retrieval strategies.
    """

    def __init__(self) -> None:
        """Initialize document repository with session management."""
        super().__init__(Document)
        self._session: Optional[Session] = None
        self._max_chunk_size = {
            'gpt-3.5': 4000,  # 4K tokens for GPT-3.5
            'gpt-4': 8000     # 8K tokens for GPT-4
        }

    def get_with_chunks(self, document_id: str) -> Optional[Document]:
        """
        Retrieve document with its chunks using eager loading.

        Args:
            document_id: Unique identifier of the document

        Returns:
            Document with chunks or None if not found

        Raises:
            StorageError: If database operation fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            # Build query with relationships
            query = (
                select(Document)
                .outerjoin(Document.chunks)
                .outerjoin(Document.index)
                .filter(Document.id == document_id)
            )

            # Execute query
            result = self._session.execute(query).scalar_one_or_none()

            if result:
                # Record access in index
                if result.index:
                    result.index.record_access()
                    self._session.commit()

            return result

        except SQLAlchemyError as e:
            logger.error(f"Database error in get_with_chunks: {str(e)}")
            raise StorageError(
                "Failed to retrieve document with chunks",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

    def create_with_chunks(self, document: Document, chunks: List[DocumentChunk]) -> Document:
        """
        Create document with chunks and index in a single transaction.

        Args:
            document: Document instance to create
            chunks: List of document chunks to associate

        Returns:
            Created document with chunks

        Raises:
            StorageError: If creation fails or validation errors occur
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            # Validate document
            if not isinstance(document, Document):
                raise ValueError("Invalid document type")

            # Validate chunks
            for chunk in chunks:
                if chunk.token_count > self._max_chunk_size['gpt-4']:
                    raise ValueError(f"Chunk size exceeds maximum: {chunk.token_count}")

            # Start transaction
            self._session.begin()

            # Create document
            self._session.add(document)
            self._session.flush()

            # Create chunks
            for chunk in chunks:
                chunk.document_id = document.id
                self._session.add(chunk)

            # Create index
            index = DocumentIndex(
                document_id=document.id,
                metadata={
                    "format": document.format,
                    "chunk_count": len(chunks),
                    "total_tokens": document.token_count,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
            )
            self._session.add(index)

            # Commit transaction
            self._session.commit()

            return document

        except Exception as e:
            self._session.rollback()
            logger.error(f"Error in create_with_chunks: {str(e)}")
            raise StorageError(
                "Failed to create document with chunks",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def update_chunks(self, document_id: str, chunks: List[DocumentChunk]) -> bool:
        """
        Update document chunks with token validation.

        Args:
            document_id: Document identifier
            chunks: New chunks to replace existing ones

        Returns:
            True if updated successfully

        Raises:
            StorageError: If update fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            # Start transaction
            self._session.begin()

            # Delete existing chunks
            self._session.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).delete()

            # Create new chunks
            total_tokens = 0
            for chunk in chunks:
                if chunk.token_count > self._max_chunk_size['gpt-4']:
                    raise ValueError(f"Chunk size exceeds maximum: {chunk.token_count}")
                chunk.document_id = document_id
                self._session.add(chunk)
                total_tokens += chunk.token_count

            # Update document metadata
            document = self._session.get(Document, document_id)
            if document:
                document.token_count = total_tokens
                document.updated_at = datetime.now(timezone.utc)

                # Update index metadata
                if document.index:
                    document.index.update_metadata({
                        "chunk_count": len(chunks),
                        "total_tokens": total_tokens,
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })

            # Commit transaction
            self._session.commit()
            return True

        except Exception as e:
            self._session.rollback()
            logger.error(f"Error in update_chunks: {str(e)}")
            raise StorageError(
                "Failed to update document chunks",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

    def search_by_metadata(self, metadata_filters: Dict[str, Any]) -> List[Document]:
        """
        Search documents using metadata filters with index optimization.

        Args:
            metadata_filters: Dictionary of metadata key-value pairs to filter by

        Returns:
            List of matching documents

        Raises:
            StorageError: If search operation fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            # Build base query
            query = select(Document).join(Document.index)

            # Apply metadata filters
            filter_conditions = []
            for key, value in metadata_filters.items():
                filter_conditions.append(
                    DocumentIndex.metadata[key].astext == str(value)
                )

            if filter_conditions:
                query = query.filter(or_(*filter_conditions))

            # Execute query
            results = self._session.execute(query).scalars().all()

            # Update access patterns
            for doc in results:
                if doc.index:
                    doc.index.record_access()

            self._session.commit()
            return results

        except SQLAlchemyError as e:
            logger.error(f"Database error in search_by_metadata: {str(e)}")
            raise StorageError(
                "Failed to search documents",
                ErrorCode.STORAGE_ERROR,
                {"filters": metadata_filters, "error": str(e)}
            )

    def get_document_chunks(self, document_id: str) -> List[DocumentChunk]:
        """
        Retrieve ordered chunks for a document.

        Args:
            document_id: Document identifier

        Returns:
            Ordered list of document chunks

        Raises:
            StorageError: If retrieval fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            chunks = (
                self._session.query(DocumentChunk)
                .filter(DocumentChunk.document_id == document_id)
                .order_by(DocumentChunk.chunk_number)
                .all()
            )

            return chunks

        except SQLAlchemyError as e:
            logger.error(f"Database error in get_document_chunks: {str(e)}")
            raise StorageError(
                "Failed to retrieve document chunks",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

    def update_chunk_embedding(self, chunk_id: str, embedding: bytes) -> bool:
        """
        Update embedding data for a document chunk.

        Args:
            chunk_id: Chunk identifier
            embedding: Vector embedding data

        Returns:
            True if updated successfully

        Raises:
            StorageError: If update fails
        """
        try:
            if self._session is None:
                raise StorageError("No active session")

            chunk = self._session.get(DocumentChunk, chunk_id)
            if not chunk:
                return False

            chunk.update_embedding(embedding)
            self._session.commit()
            return True

        except SQLAlchemyError as e:
            logger.error(f"Database error in update_chunk_embedding: {str(e)}")
            raise StorageError(
                "Failed to update chunk embedding",
                ErrorCode.STORAGE_ERROR,
                {"chunk_id": chunk_id, "error": str(e)}
            )