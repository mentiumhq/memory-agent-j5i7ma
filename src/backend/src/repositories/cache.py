"""
Thread-safe repository implementation for document chunk caching with LRU and TTL support.
Provides an abstraction layer between storage service and caching mechanism.

Version:
- asyncio==3.11+
- typing==3.11+
"""

import asyncio
from typing import Optional, Dict, Any
import logging

from .base import BaseRepository
from core.cache import Cache
from db.models.document_chunk import DocumentChunk
from core.errors import StorageError, ErrorCode

# Configure logging
logger = logging.getLogger(__name__)

# Cache configuration constants
DEFAULT_CACHE_SIZE = 1000  # Maximum number of entries
DEFAULT_TTL_SECONDS = 3600  # Default TTL of 1 hour

class CacheRepository:
    """
    Repository implementation for document chunk caching using LRU cache with TTL 
    and comprehensive monitoring capabilities.
    """

    def __init__(
        self,
        cache_size: int = DEFAULT_CACHE_SIZE,
        ttl_seconds: float = DEFAULT_TTL_SECONDS
    ) -> None:
        """
        Initialize cache repository with size and TTL configuration.

        Args:
            cache_size: Maximum number of entries in cache
            ttl_seconds: Default TTL for cache entries in seconds
        """
        # Initialize thread-safe LRU cache
        self._cache = Cache(
            max_size=cache_size,
            ttl_seconds=ttl_seconds,
            enable_monitoring=True
        )

        # Initialize statistics tracking
        self._stats: Dict[str, Any] = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'memory_usage': 0
        }

        # Initialize async lock for thread safety
        self._lock = asyncio.Lock()

    async def get_chunk(self, chunk_id: str) -> Optional[Dict]:
        """
        Retrieve document chunk from cache by ID with thread safety.

        Args:
            chunk_id: Unique identifier of chunk to retrieve

        Returns:
            Optional[Dict]: Cached chunk data or None if not found/expired

        Raises:
            StorageError: If cache access fails
        """
        try:
            async with self._lock:
                # Attempt to retrieve from cache
                cached_data = await self._cache.get(chunk_id)
                
                if cached_data is None:
                    self._stats['misses'] += 1
                    return None

                self._stats['hits'] += 1
                return cached_data

        except Exception as e:
            logger.error(f"Cache retrieval failed: {str(e)}")
            raise StorageError(
                "Failed to retrieve chunk from cache",
                ErrorCode.STORAGE_ERROR,
                {"chunk_id": chunk_id, "error": str(e)}
            )

    async def cache_chunk(self, chunk: DocumentChunk) -> None:
        """
        Store document chunk in cache with thread safety.

        Args:
            chunk: DocumentChunk instance to cache

        Raises:
            StorageError: If cache storage fails
        """
        try:
            async with self._lock:
                # Convert chunk to dictionary format
                chunk_data = chunk.to_dict()
                
                # Store in cache using chunk ID as key
                await self._cache.set(str(chunk.id), chunk_data)
                
                # Update memory usage statistics
                cache_stats = self._cache.get_statistics()
                if cache_stats:
                    self._stats['memory_usage'] = cache_stats.get('memory_usage', 0)

        except Exception as e:
            logger.error(f"Cache storage failed: {str(e)}")
            raise StorageError(
                "Failed to store chunk in cache",
                ErrorCode.STORAGE_ERROR,
                {"chunk_id": str(chunk.id), "error": str(e)}
            )

    async def invalidate_chunk(self, chunk_id: str) -> bool:
        """
        Remove chunk from cache with thread safety.

        Args:
            chunk_id: Unique identifier of chunk to remove

        Returns:
            bool: True if chunk was in cache and removed, False if not found

        Raises:
            StorageError: If cache invalidation fails
        """
        try:
            async with self._lock:
                # Attempt to delete from cache
                was_deleted = await self._cache.delete(chunk_id)
                
                if was_deleted:
                    self._stats['evictions'] += 1
                    
                return was_deleted

        except Exception as e:
            logger.error(f"Cache invalidation failed: {str(e)}")
            raise StorageError(
                "Failed to invalidate chunk from cache",
                ErrorCode.STORAGE_ERROR,
                {"chunk_id": chunk_id, "error": str(e)}
            )

    async def cleanup(self) -> int:
        """
        Remove expired entries from cache and handle memory pressure.

        Returns:
            int: Number of entries removed during cleanup

        Raises:
            StorageError: If cleanup operation fails
        """
        try:
            async with self._lock:
                # Trigger cache cleanup
                removed_count = await self._cache.cleanup_expired()
                
                # Update statistics
                cache_stats = self._cache.get_statistics()
                if cache_stats:
                    self._stats['memory_usage'] = cache_stats.get('memory_usage', 0)
                    
                return removed_count

        except Exception as e:
            logger.error(f"Cache cleanup failed: {str(e)}")
            raise StorageError(
                "Failed to cleanup cache",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    async def get_stats(self) -> Dict[str, Any]:
        """
        Retrieve cache statistics and monitoring data.

        Returns:
            Dict[str, Any]: Cache statistics including hits, misses, memory usage

        Raises:
            StorageError: If statistics retrieval fails
        """
        try:
            async with self._lock:
                # Get cache-level statistics
                cache_stats = self._cache.get_statistics()
                
                if cache_stats:
                    # Merge cache stats with repository stats
                    stats = {
                        **self._stats,
                        'cache_hits': cache_stats.get('hits', 0),
                        'cache_misses': cache_stats.get('misses', 0),
                        'cache_evictions': cache_stats.get('evictions', 0),
                        'cache_expirations': cache_stats.get('expirations', 0),
                        'memory_usage': cache_stats.get('memory_usage', 0)
                    }
                    return stats
                
                return dict(self._stats)

        except Exception as e:
            logger.error(f"Statistics retrieval failed: {str(e)}")
            raise StorageError(
                "Failed to retrieve cache statistics",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )