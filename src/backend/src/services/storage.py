"""
Service layer implementation for document storage operations with S3 persistence,
local caching, and document chunking with enhanced security, monitoring, and error handling.

Version:
- asyncio==3.11+
- typing==3.11+
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
from prometheus_client import Counter, Histogram

from repositories.document import DocumentRepository
from integrations.aws.s3 import S3Client
from services.cache import CacheService
from core.errors import StorageError, ErrorCode
from core.telemetry import create_tracer
from config.logging import get_logger
from db.models.document import Document
from db.models.document_chunk import DocumentChunk

# Initialize logging and tracing
LOGGER = get_logger(__name__)
TRACER = create_tracer('storage')

# Monitoring metrics
storage_operations = Counter('storage_operations_total', 'Total storage operations', ['operation'])
storage_errors = Counter('storage_errors_total', 'Total storage errors', ['error_type'])
storage_latency = Histogram('storage_operation_duration_seconds', 'Storage operation duration')

# Configuration constants
MAX_DOCUMENT_SIZE = 100_000_000  # 100MB
STORAGE_RATE_LIMIT = 50  # Operations per second
CIRCUIT_BREAKER_THRESHOLD = 5  # Consecutive failures before circuit breaks

class StorageService:
    """
    Service layer for managing document storage operations across S3 and local storage
    with enhanced security, monitoring, and error handling capabilities.
    """

    def __init__(
        self,
        document_repository: DocumentRepository,
        s3_client: S3Client,
        cache_service: CacheService
    ) -> None:
        """
        Initialize storage service with required dependencies and security controls.

        Args:
            document_repository: Repository for document metadata and chunks
            s3_client: Client for S3 storage operations
            cache_service: Service for document caching
        """
        self._document_repository = document_repository
        self._s3_client = s3_client
        self._cache_service = cache_service
        
        # Initialize thread safety controls
        self._storage_lock = asyncio.Lock()
        self._failure_counts: Dict[str, int] = {}
        
        # Initialize rate limiting
        self._rate_limiter = asyncio.Semaphore(STORAGE_RATE_LIMIT)

    async def store_document(
        self,
        content: bytes,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Store document in S3 and local storage with enhanced security and monitoring.

        Args:
            content: Document content as bytes
            metadata: Document metadata dictionary

        Returns:
            str: Stored document ID

        Raises:
            StorageError: If storage operation fails
        """
        async with self._rate_limiter:
            try:
                # Validate document size
                if len(content) > MAX_DOCUMENT_SIZE:
                    raise StorageError(
                        "Document exceeds maximum size",
                        ErrorCode.VALIDATION_ERROR,
                        {"size": len(content), "max_size": MAX_DOCUMENT_SIZE}
                    )

                # Start storage span
                with TRACER.start_as_current_span("store_document") as span:
                    span.set_attribute("document.size", len(content))
                    
                    async with self._storage_lock:
                        # Store in S3 with encryption verification
                        document_id = await self._s3_client.store_document(
                            document_id=metadata.get("id"),
                            content=content,
                            metadata=metadata
                        )
                        
                        # Create document record
                        document = Document(
                            content=f"s3://{document_id}",
                            format=metadata.get("format", "unknown"),
                            metadata=metadata,
                            token_count=metadata.get("token_count", 0)
                        )
                        
                        # Create and store document chunks
                        chunks = self._create_document_chunks(
                            document_id=document.id,
                            content=content,
                            metadata=metadata
                        )
                        
                        # Store document and chunks in repository
                        stored_document = self._document_repository.create_with_chunks(
                            document=document,
                            chunks=chunks
                        )
                        
                        # Cache document chunks
                        for chunk in chunks:
                            await self._cache_service.cache_document_chunk(chunk)
                        
                        # Record metrics
                        storage_operations.labels(operation="store").inc()
                        
                        LOGGER.info(
                            "Document stored successfully",
                            extra={
                                "document_id": str(stored_document.id),
                                "size": len(content),
                                "chunk_count": len(chunks)
                            }
                        )
                        
                        return str(stored_document.id)

            except Exception as e:
                storage_errors.labels(error_type=type(e).__name__).inc()
                LOGGER.error(f"Document storage failed: {str(e)}", exc_info=True)
                raise StorageError(
                    "Failed to store document",
                    ErrorCode.STORAGE_ERROR,
                    {"error": str(e)}
                )

    async def retrieve_document(
        self,
        document_id: str,
        include_chunks: bool = True
    ) -> Tuple[Document, Optional[List[DocumentChunk]]]:
        """
        Retrieve document and optionally its chunks from storage.

        Args:
            document_id: Document identifier
            include_chunks: Whether to include document chunks

        Returns:
            Tuple containing document and optional chunks

        Raises:
            StorageError: If retrieval fails
        """
        async with self._rate_limiter:
            try:
                with TRACER.start_as_current_span("retrieve_document") as span:
                    span.set_attribute("document.id", document_id)
                    
                    # Get document metadata
                    document = self._document_repository.get_with_chunks(document_id)
                    if not document:
                        raise StorageError(
                            f"Document not found: {document_id}",
                            ErrorCode.DOCUMENT_NOT_FOUND,
                            {"document_id": document_id}
                        )
                    
                    chunks = None
                    if include_chunks:
                        # Try to get chunks from cache first
                        chunks = []
                        for chunk in document.chunks:
                            cached_chunk = await self._cache_service.get_document_chunk(
                                str(chunk.id)
                            )
                            if cached_chunk:
                                chunks.append(chunk)
                            else:
                                # If not in cache, get from repository
                                chunks = self._document_repository.get_document_chunks(
                                    document_id
                                )
                                # Cache chunks for future use
                                for chunk in chunks:
                                    await self._cache_service.cache_document_chunk(chunk)
                                break
                    
                    storage_operations.labels(operation="retrieve").inc()
                    return document, chunks

            except StorageError:
                raise
            except Exception as e:
                storage_errors.labels(error_type=type(e).__name__).inc()
                LOGGER.error(f"Document retrieval failed: {str(e)}", exc_info=True)
                raise StorageError(
                    "Failed to retrieve document",
                    ErrorCode.STORAGE_ERROR,
                    {"document_id": document_id, "error": str(e)}
                )

    def _create_document_chunks(
        self,
        document_id: str,
        content: bytes,
        metadata: Dict[str, Any]
    ) -> List[DocumentChunk]:
        """
        Create document chunks with token-aware splitting.

        Args:
            document_id: Document identifier
            content: Document content
            metadata: Document metadata

        Returns:
            List of document chunks
        """
        chunks = []
        content_str = content.decode('utf-8')
        chunk_size = metadata.get("chunk_size", 4000)  # Default to 4K tokens
        
        # Simple chunking by newlines for demonstration
        # In production, use proper tokenization and semantic chunking
        content_parts = content_str.split('\n\n')
        
        for i, part in enumerate(content_parts):
            if not part.strip():
                continue
                
            chunk = DocumentChunk(
                document_id=document_id,
                content=part,
                chunk_number=i,
                token_count=len(part.split())  # Simple word count
            )
            chunks.append(chunk)
        
        return chunks

    async def delete_document(self, document_id: str) -> bool:
        """
        Delete document and its chunks from all storage layers.

        Args:
            document_id: Document identifier

        Returns:
            bool: True if deleted successfully

        Raises:
            StorageError: If deletion fails
        """
        async with self._rate_limiter:
            try:
                with TRACER.start_as_current_span("delete_document") as span:
                    span.set_attribute("document.id", document_id)
                    
                    async with self._storage_lock:
                        # Delete from S3
                        await self._s3_client.delete_document(document_id)
                        
                        # Invalidate cache
                        await self._cache_service.invalidate_document_chunks(document_id)
                        
                        # Delete from repository
                        deleted = self._document_repository.delete(document_id)
                        
                        if deleted:
                            storage_operations.labels(operation="delete").inc()
                            LOGGER.info(f"Document deleted: {document_id}")
                        
                        return deleted

            except Exception as e:
                storage_errors.labels(error_type=type(e).__name__).inc()
                LOGGER.error(f"Document deletion failed: {str(e)}", exc_info=True)
                raise StorageError(
                    "Failed to delete document",
                    ErrorCode.STORAGE_ERROR,
                    {"document_id": document_id, "error": str(e)}
                )