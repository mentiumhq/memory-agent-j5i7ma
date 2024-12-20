"""
Service layer implementation for document caching operations with memory pressure management.
Provides high-level caching functionality with support for document chunks, metadata,
automatic cache invalidation, and comprehensive monitoring capabilities.

Version:
- asyncio==3.11+
- typing==3.11+
"""

import asyncio
import time
from typing import Optional, Dict, List, Any

from repositories.cache import CacheRepository
from db.models.document_chunk import DocumentChunk
from core.errors import StorageError, ErrorCode

# Cache configuration constants
DEFAULT_CACHE_SIZE = 1000  # Maximum number of entries
DEFAULT_TTL_SECONDS = 3600  # Default TTL of 1 hour
MEMORY_PRESSURE_THRESHOLD = 0.85  # 85% memory threshold
CLEANUP_INTERVAL_SECONDS = 300  # Cleanup every 5 minutes

class CacheService:
    """
    Service layer for managing document caching operations with LRU and TTL support,
    memory pressure management, and comprehensive monitoring capabilities.
    """

    def __init__(
        self,
        cache_size: int = DEFAULT_CACHE_SIZE,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        memory_threshold: float = MEMORY_PRESSURE_THRESHOLD
    ) -> None:
        """
        Initialize cache service with repository and memory management.

        Args:
            cache_size: Maximum number of entries in cache
            ttl_seconds: Default TTL for cache entries
            memory_threshold: Memory pressure threshold percentage
        """
        # Initialize cache repository
        self._repository = CacheRepository(
            cache_size=cache_size,
            ttl_seconds=ttl_seconds
        )
        
        # Initialize async lock for thread safety
        self._lock = asyncio.Lock()
        
        # Set memory pressure threshold
        self._memory_threshold = memory_threshold
        
        # Start background cleanup task
        asyncio.create_task(self._cleanup_loop())

    async def get_document_chunk(self, chunk_id: str) -> Optional[Dict]:
        """
        Retrieve document chunk from cache with monitoring.

        Args:
            chunk_id: Unique identifier of chunk to retrieve

        Returns:
            Optional[Dict]: Cached chunk data or None if not found

        Raises:
            StorageError: If cache retrieval fails
        """
        start_time = time.time()
        try:
            async with self._lock:
                # Validate chunk ID
                if not chunk_id:
                    raise StorageError(
                        "Invalid chunk ID",
                        ErrorCode.VALIDATION_ERROR
                    )
                
                # Attempt to retrieve from cache
                cached_data = await self._repository.get_chunk(chunk_id)
                
                # Update monitoring metrics
                stats = await self._repository.get_stats()
                duration = time.time() - start_time
                
                return cached_data

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                "Failed to retrieve chunk from cache",
                ErrorCode.STORAGE_ERROR,
                {"chunk_id": chunk_id, "error": str(e)}
            )

    async def cache_document_chunk(self, chunk: DocumentChunk) -> bool:
        """
        Store document chunk in cache with memory pressure check.

        Args:
            chunk: DocumentChunk instance to cache

        Returns:
            bool: True if cached, False if skipped due to memory pressure

        Raises:
            StorageError: If cache storage fails
        """
        try:
            async with self._lock:
                # Validate chunk object
                if not isinstance(chunk, DocumentChunk):
                    raise StorageError(
                        "Invalid chunk object",
                        ErrorCode.VALIDATION_ERROR
                    )
                
                # Check memory pressure
                stats = await self._repository.get_stats()
                if stats and stats.get('memory_usage', 0) > self._memory_threshold:
                    # Skip caching under memory pressure
                    return False
                
                # Store chunk in cache
                await self._repository.cache_chunk(chunk)
                return True

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                "Failed to cache document chunk",
                ErrorCode.STORAGE_ERROR,
                {"chunk_id": str(chunk.id), "error": str(e)}
            )

    async def invalidate_document_chunk(self, chunk_id: str) -> bool:
        """
        Remove document chunk from cache with monitoring.

        Args:
            chunk_id: Unique identifier of chunk to remove

        Returns:
            bool: True if invalidated, False if not found

        Raises:
            StorageError: If cache invalidation fails
        """
        try:
            async with self._lock:
                # Validate chunk ID
                if not chunk_id:
                    raise StorageError(
                        "Invalid chunk ID",
                        ErrorCode.VALIDATION_ERROR
                    )
                
                # Remove chunk from cache
                return await self._repository.invalidate_chunk(chunk_id)

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                "Failed to invalidate chunk from cache",
                ErrorCode.STORAGE_ERROR,
                {"chunk_id": chunk_id, "error": str(e)}
            )

    async def invalidate_document_chunks(self, document_id: str) -> int:
        """
        Remove all chunks for a document from cache.

        Args:
            document_id: Document ID whose chunks should be invalidated

        Returns:
            int: Number of chunks invalidated

        Raises:
            StorageError: If cache invalidation fails
        """
        try:
            async with self._lock:
                # Validate document ID
                if not document_id:
                    raise StorageError(
                        "Invalid document ID",
                        ErrorCode.VALIDATION_ERROR
                    )
                
                # Track invalidated chunks
                invalidated_count = 0
                
                # Get cache stats to find document chunks
                stats = await self._repository.get_stats()
                if not stats:
                    return 0
                
                # Invalidate each chunk for document
                for key in list(stats.get('cache_keys', [])):
                    if key.startswith(f"{document_id}:"):
                        if await self._repository.invalidate_chunk(key):
                            invalidated_count += 1
                
                return invalidated_count

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                "Failed to invalidate document chunks",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries and manage memory pressure.

        Returns:
            int: Number of entries removed

        Raises:
            StorageError: If cleanup fails
        """
        try:
            async with self._lock:
                # Get current memory usage
                stats = await self._repository.get_stats()
                memory_usage = stats.get('memory_usage', 0) if stats else 0
                
                # Remove expired entries
                removed_count = await self._repository.cleanup()
                
                # If memory pressure is high, remove additional entries
                if memory_usage > self._memory_threshold:
                    # Force additional cleanup
                    additional_removed = await self._repository.cleanup()
                    removed_count += additional_removed
                
                return removed_count

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                "Failed to cleanup cache",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Retrieve cache performance statistics.

        Returns:
            Dict[str, Any]: Cache statistics including memory usage

        Raises:
            StorageError: If statistics retrieval fails
        """
        try:
            async with self._lock:
                stats = await self._repository.get_stats()
                if not stats:
                    return {}
                
                # Calculate cache efficiency
                hits = stats.get('hits', 0)
                misses = stats.get('misses', 0)
                total_requests = hits + misses
                hit_ratio = hits / total_requests if total_requests > 0 else 0
                
                return {
                    'hits': hits,
                    'misses': misses,
                    'hit_ratio': hit_ratio,
                    'memory_usage': stats.get('memory_usage', 0),
                    'memory_threshold': self._memory_threshold,
                    'evictions': stats.get('evictions', 0),
                    'expirations': stats.get('expirations', 0)
                }

        except StorageError:
            raise
        except Exception as e:
            raise StorageError(
                "Failed to retrieve cache statistics",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    async def _cleanup_loop(self) -> None:
        """Background task for periodic cleanup of expired entries."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                await self.cleanup_expired()
            except Exception:
                # Log error but don't crash cleanup loop
                continue