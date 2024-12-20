"""
Thread-safe, async-capable LRU cache implementation with TTL support.

This module provides a high-performance caching solution with the following features:
- Thread-safe operations using locks
- Async/await support for all operations
- TTL-based expiration with automatic cleanup
- Memory usage monitoring and management
- Comprehensive statistics tracking
- Weak references for memory efficiency

Version: 1.0.0
"""

from typing import Dict, Optional, Any, Tuple, List, Set
import asyncio
import threading
import time
import weakref
from .errors import StorageError, ErrorCode
from .utils import get_current_timestamp

# Cache configuration constants
DEFAULT_CACHE_SIZE = 1000  # Maximum number of entries
DEFAULT_TTL_SECONDS = 3600  # Default TTL of 1 hour
CLEANUP_INTERVAL = 300  # Cleanup every 5 minutes
MAX_MEMORY_PERCENT = 75  # Maximum memory threshold percentage

class CacheEntry:
    """
    Container for cached items with metadata including expiration time,
    access tracking, and memory usage statistics.
    """
    
    def __init__(self, value: Any, ttl_seconds: float) -> None:
        """
        Initialize cache entry with value and TTL.

        Args:
            value: The value to cache
            ttl_seconds: Time-to-live in seconds
        """
        # Store value using weak reference if possible
        try:
            self.value = weakref.proxy(value) if hasattr(value, '__weakref__') else value
        except TypeError:
            self.value = value
            
        # Set expiration and access metadata
        current_time = time.time()
        self.expiration = current_time + ttl_seconds
        self.last_accessed = current_time
        self.access_count = 1
        
        # Estimate memory size (rough approximation)
        try:
            self.memory_size = value.__sizeof__() if hasattr(value, '__sizeof__') else len(str(value))
        except:
            self.memory_size = 1024  # Default 1KB if size cannot be determined

    def is_expired(self) -> bool:
        """
        Check if the cache entry has expired.

        Returns:
            bool: True if expired, False otherwise
        """
        return time.time() > self.expiration

    def update_access_time(self) -> None:
        """Update last accessed time and increment access count."""
        self.last_accessed = time.time()
        self.access_count += 1


class Cache:
    """
    Thread-safe, async-capable LRU cache implementation with TTL support
    and comprehensive monitoring capabilities.
    """
    
    def __init__(
        self,
        max_size: int = DEFAULT_CACHE_SIZE,
        ttl_seconds: float = DEFAULT_TTL_SECONDS,
        enable_monitoring: bool = True
    ) -> None:
        """
        Initialize cache with size limit, TTL, and monitoring.

        Args:
            max_size: Maximum number of entries in cache
            ttl_seconds: Default TTL for cache entries
            enable_monitoring: Enable statistics collection
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        
        # Statistics tracking
        self._statistics = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'memory_usage': 0
        } if enable_monitoring else None
        
        # Start cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def get(self, key: str) -> Optional[Any]:
        """
        Retrieve item from cache by key.

        Args:
            key: Cache key to retrieve

        Returns:
            Optional[Any]: Cached value or None if not found/expired

        Raises:
            StorageError: If cache access fails
        """
        try:
            with self._lock:
                entry = self._cache.get(key)
                
                if entry is None:
                    if self._statistics is not None:
                        self._statistics['misses'] += 1
                    return None
                
                if entry.is_expired():
                    if self._statistics is not None:
                        self._statistics['expirations'] += 1
                    del self._cache[key]
                    return None
                
                # Update access metadata
                entry.update_access_time()
                
                if self._statistics is not None:
                    self._statistics['hits'] += 1
                
                return entry.value
                
        except Exception as e:
            raise StorageError(
                "Cache access failed",
                ErrorCode.STORAGE_ERROR,
                {"key": key, "error": str(e)}
            )

    async def set(self, key: str, value: Any, ttl_seconds: Optional[float] = None) -> None:
        """
        Store item in cache with optional TTL override.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Optional TTL override

        Raises:
            StorageError: If cache storage fails
        """
        try:
            with self._lock:
                # Create new entry
                entry = CacheEntry(value, ttl_seconds or self._ttl_seconds)
                
                # Check if we need to evict entries
                if len(self._cache) >= self._max_size:
                    self._evict_entries()
                
                # Store new entry
                self._cache[key] = entry
                
                if self._statistics is not None:
                    self._statistics['memory_usage'] += entry.memory_size
                    
        except Exception as e:
            raise StorageError(
                "Cache storage failed",
                ErrorCode.STORAGE_ERROR,
                {"key": key, "error": str(e)}
            )

    async def delete(self, key: str) -> bool:
        """
        Remove item from cache.

        Args:
            key: Cache key to remove

        Returns:
            bool: True if item was removed, False if not found

        Raises:
            StorageError: If cache deletion fails
        """
        try:
            with self._lock:
                if key in self._cache:
                    entry = self._cache[key]
                    if self._statistics is not None:
                        self._statistics['memory_usage'] -= entry.memory_size
                    del self._cache[key]
                    return True
                return False
                
        except Exception as e:
            raise StorageError(
                "Cache deletion failed",
                ErrorCode.STORAGE_ERROR,
                {"key": key, "error": str(e)}
            )

    async def clear(self) -> None:
        """
        Remove all items from cache.

        Raises:
            StorageError: If cache clearing fails
        """
        try:
            with self._lock:
                self._cache.clear()
                if self._statistics is not None:
                    self._statistics['memory_usage'] = 0
                    
        except Exception as e:
            raise StorageError(
                "Cache clearing failed",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    async def cleanup_expired(self) -> int:
        """
        Remove expired entries and return count of removed items.

        Returns:
            int: Number of entries removed

        Raises:
            StorageError: If cleanup fails
        """
        try:
            removed = 0
            with self._lock:
                current_time = time.time()
                expired_keys = [
                    key for key, entry in self._cache.items()
                    if current_time > entry.expiration
                ]
                
                for key in expired_keys:
                    entry = self._cache[key]
                    if self._statistics is not None:
                        self._statistics['memory_usage'] -= entry.memory_size
                        self._statistics['expirations'] += 1
                    del self._cache[key]
                    removed += 1
                    
                return removed
                
        except Exception as e:
            raise StorageError(
                "Cache cleanup failed",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def get_statistics(self) -> Optional[Dict[str, int]]:
        """
        Get cache statistics if monitoring is enabled.

        Returns:
            Optional[Dict[str, int]]: Statistics dictionary or None if monitoring disabled
        """
        return dict(self._statistics) if self._statistics is not None else None

    async def _cleanup_loop(self) -> None:
        """Background task for periodic cleanup of expired entries."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL)
                await self.cleanup_expired()
            except Exception:
                # Log error but don't crash cleanup loop
                pass

    def _evict_entries(self) -> None:
        """
        Evict entries using LRU policy when cache is full.
        Should be called with lock held.
        """
        if not self._cache:
            return
            
        # Sort by last accessed time and remove oldest
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].last_accessed
        )
        
        # Remove oldest entries until we're under max size
        while len(self._cache) >= self._max_size:
            key, entry = sorted_entries.pop(0)
            if self._statistics is not None:
                self._statistics['memory_usage'] -= entry.memory_size
                self._statistics['evictions'] += 1
            del self._cache[key]

    def __del__(self) -> None:
        """Cleanup when cache is destroyed."""
        if hasattr(self, '_cleanup_task'):
            self._cleanup_task.cancel()