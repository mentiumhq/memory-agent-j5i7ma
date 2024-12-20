"""
Temporal workflow activities for document caching operations.
Provides async activities for storing, retrieving, and managing cached document chunks
with LRU and TTL support, including comprehensive error handling and monitoring.

Version:
- temporalio==1.2.0
- typing==3.11+
"""

from typing import Optional, Dict, Any, List
from temporalio import activity
from temporalio.activity.retry import retry

from services.cache import CacheService
from db.models.document_chunk import DocumentChunk
from core.errors import StorageError, ErrorCode

# Cache configuration constants
DEFAULT_CACHE_SIZE = 1000  # Maximum number of entries
DEFAULT_TTL_SECONDS = 3600  # Default TTL of 1 hour
MAX_RETRY_ATTEMPTS = 3  # Maximum retry attempts for activities
MEMORY_PRESSURE_THRESHOLD = 0.85  # 85% memory threshold

# Initialize cache service with configuration
cache_service = CacheService(
    cache_size=DEFAULT_CACHE_SIZE,
    ttl_seconds=DEFAULT_TTL_SECONDS,
    memory_threshold=MEMORY_PRESSURE_THRESHOLD
)

@activity.defn
@retry(attempts=MAX_RETRY_ATTEMPTS)
async def get_document_chunk_activity(chunk_id: str) -> Optional[Dict[str, Any]]:
    """
    Temporal activity to retrieve a document chunk from cache with monitoring.

    Args:
        chunk_id: Unique identifier of chunk to retrieve

    Returns:
        Optional[Dict[str, Any]]: Cached chunk data or None if not found

    Raises:
        StorageError: If cache retrieval fails
    """
    try:
        # Validate chunk ID
        if not chunk_id:
            raise StorageError(
                "Invalid chunk ID",
                ErrorCode.VALIDATION_ERROR
            )

        # Attempt to retrieve from cache
        cached_data = await cache_service.get_document_chunk(chunk_id)

        # Update monitoring metrics
        stats = await cache_service.get_cache_stats()
        activity.heartbeat({"cache_stats": stats})

        return cached_data

    except StorageError:
        raise
    except Exception as e:
        raise StorageError(
            "Failed to retrieve chunk from cache",
            ErrorCode.STORAGE_ERROR,
            {"chunk_id": chunk_id, "error": str(e)}
        )

@activity.defn
@retry(attempts=MAX_RETRY_ATTEMPTS)
async def cache_document_chunk_activity(chunk: DocumentChunk) -> bool:
    """
    Temporal activity to store a document chunk in cache with memory pressure management.

    Args:
        chunk: DocumentChunk instance to cache

    Returns:
        bool: True if cached successfully, False if skipped due to memory pressure

    Raises:
        StorageError: If cache storage fails
    """
    try:
        # Validate chunk object
        if not isinstance(chunk, DocumentChunk):
            raise StorageError(
                "Invalid chunk object",
                ErrorCode.VALIDATION_ERROR
            )

        # Check memory pressure and trigger cleanup if needed
        stats = await cache_service.get_cache_stats()
        if stats and stats.get('memory_usage', 0) > MEMORY_PRESSURE_THRESHOLD:
            await cleanup_expired_cache_activity()

        # Store chunk in cache
        success = await cache_service.cache_document_chunk(chunk)

        # Update monitoring metrics
        activity.heartbeat({"cache_stats": stats})

        return success

    except StorageError:
        raise
    except Exception as e:
        raise StorageError(
            "Failed to cache document chunk",
            ErrorCode.STORAGE_ERROR,
            {"chunk_id": str(chunk.id), "error": str(e)}
        )

@activity.defn
@retry(attempts=MAX_RETRY_ATTEMPTS)
async def invalidate_document_chunk_activity(chunk_id: str) -> bool:
    """
    Temporal activity to remove a document chunk from cache with metrics collection.

    Args:
        chunk_id: Unique identifier of chunk to remove

    Returns:
        bool: True if invalidated, False if not found

    Raises:
        StorageError: If cache invalidation fails
    """
    try:
        # Validate chunk ID
        if not chunk_id:
            raise StorageError(
                "Invalid chunk ID",
                ErrorCode.VALIDATION_ERROR
            )

        # Remove chunk from cache
        success = await cache_service.invalidate_document_chunk(chunk_id)

        # Update monitoring metrics
        stats = await cache_service.get_cache_stats()
        activity.heartbeat({"cache_stats": stats})

        return success

    except StorageError:
        raise
    except Exception as e:
        raise StorageError(
            "Failed to invalidate chunk from cache",
            ErrorCode.STORAGE_ERROR,
            {"chunk_id": chunk_id, "error": str(e)}
        )

@activity.defn
@retry(attempts=MAX_RETRY_ATTEMPTS)
async def invalidate_document_chunks_activity(document_id: str) -> int:
    """
    Temporal activity to remove all chunks for a document from cache with batch processing.

    Args:
        document_id: Document ID whose chunks should be invalidated

    Returns:
        int: Number of chunks invalidated

    Raises:
        StorageError: If cache invalidation fails
    """
    try:
        # Validate document ID
        if not document_id:
            raise StorageError(
                "Invalid document ID",
                ErrorCode.VALIDATION_ERROR
            )

        # Invalidate all chunks for document
        invalidated_count = await cache_service.invalidate_document_chunks(document_id)

        # Update monitoring metrics
        stats = await cache_service.get_cache_stats()
        activity.heartbeat({
            "cache_stats": stats,
            "invalidated_count": invalidated_count
        })

        return invalidated_count

    except StorageError:
        raise
    except Exception as e:
        raise StorageError(
            "Failed to invalidate document chunks",
            ErrorCode.STORAGE_ERROR,
            {"document_id": document_id, "error": str(e)}
        )

@activity.defn
@retry(attempts=MAX_RETRY_ATTEMPTS)
async def cleanup_expired_cache_activity() -> int:
    """
    Temporal activity to remove expired entries from cache with memory pressure handling.

    Returns:
        int: Number of expired entries removed

    Raises:
        StorageError: If cleanup fails
    """
    try:
        # Get current memory usage
        stats = await cache_service.get_cache_stats()
        memory_usage = stats.get('memory_usage', 0) if stats else 0

        # Perform cleanup
        removed_count = await cache_service.cleanup_expired()

        # If memory pressure is still high, force additional cleanup
        if memory_usage > MEMORY_PRESSURE_THRESHOLD:
            additional_removed = await cache_service.cleanup_expired()
            removed_count += additional_removed

        # Update monitoring metrics
        stats = await cache_service.get_cache_stats()
        activity.heartbeat({
            "cache_stats": stats,
            "removed_count": removed_count
        })

        return removed_count

    except StorageError:
        raise
    except Exception as e:
        raise StorageError(
            "Failed to cleanup cache",
            ErrorCode.STORAGE_ERROR,
            {"error": str(e)}
        )