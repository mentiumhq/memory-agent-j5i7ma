"""
Repository package initialization module providing centralized access to document storage,
caching, and indexing implementations through a clean repository pattern interface.

This module exports repository classes for managing documents, caches, and indexes while
ensuring proper initialization order and type safety. It implements the storage router
pattern through repository abstractions.

Version:
- SQLAlchemy==2.0+
- SQLAlchemy-Utils==0.41.1
"""

from typing import Type, TypeVar, Dict, Any

# Import repository implementations
from .base import BaseRepository
from .document import DocumentRepository
from .cache import CacheRepository
from .index import IndexRepository

# Type variable for repository implementations
T = TypeVar('T', bound=BaseRepository)

# Export repository classes
__all__ = [
    'BaseRepository',
    'DocumentRepository', 
    'CacheRepository',
    'IndexRepository'
]

# Repository configuration constants
DEFAULT_CACHE_SIZE = 1000  # Maximum entries in cache
DEFAULT_TTL_SECONDS = 3600  # Default TTL of 1 hour

# Repository factory registry
_repository_registry: Dict[str, Type[BaseRepository]] = {
    'document': DocumentRepository,
    'cache': CacheRepository,
    'index': IndexRepository
}

def get_repository(repo_type: str, **kwargs: Any) -> BaseRepository:
    """
    Factory function to get repository instance with configuration.

    Args:
        repo_type: Type of repository to create ('document', 'cache', 'index')
        **kwargs: Optional configuration parameters for repository

    Returns:
        Configured repository instance

    Raises:
        ValueError: If repository type is invalid
    """
    if repo_type not in _repository_registry:
        raise ValueError(f"Invalid repository type: {repo_type}")
        
    repository_class = _repository_registry[repo_type]
    return repository_class(**kwargs)

# Initialize repositories with default configuration
document_repository = DocumentRepository()
cache_repository = CacheRepository(
    cache_size=DEFAULT_CACHE_SIZE,
    ttl_seconds=DEFAULT_TTL_SECONDS
)
index_repository = IndexRepository()

# Version information
__version__ = "1.0.0"