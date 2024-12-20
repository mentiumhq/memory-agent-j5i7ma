"""
Main entry point for Temporal workflow activities in the Memory Agent system.
Provides centralized access to all activity functions for document storage,
retrieval, caching, indexing, and LLM processing operations.

Version:
- temporalio==1.0.0
- opentelemetry-api==1.20.0
"""

# Version information
__version__ = "1.0.0"

# Cache activities
from .cache_activities import (
    get_document_from_cache,
    store_document_in_cache,
    get_embedding_from_cache,
    store_embedding_in_cache,
    get_query_result_from_cache,
    store_query_result_in_cache,
    invalidate_document_cache,
    cleanup_caches
)

# Document activities
from .document_activities import (
    store_document_activity,
    retrieve_document_activity,
    search_documents_activity,
    update_document_activity,
    delete_document_activity
)

# Index activities
from .index_activities import (
    get_index_activity,
    get_by_document_id_activity,
    create_index_activity,
    update_metadata_activity,
    search_indexes_activity
)

# LLM activities
from .llm_activities import (
    process_document_with_llm,
    process_document_hybrid,
    rank_documents_llm
)

# Storage activities
from .storage_activities import (
    store_document,
    retrieve_document,
    delete_document,
    update_metadata
)

# Export all activities
__all__ = [
    # Cache activities
    "get_document_from_cache",
    "store_document_in_cache",
    "get_embedding_from_cache",
    "store_embedding_in_cache",
    "get_query_result_from_cache",
    "store_query_result_in_cache",
    "invalidate_document_cache",
    "cleanup_caches",

    # Document activities
    "store_document_activity",
    "retrieve_document_activity",
    "search_documents_activity",
    "update_document_activity",
    "delete_document_activity",

    # Index activities
    "get_index_activity",
    "get_by_document_id_activity",
    "create_index_activity",
    "update_metadata_activity",
    "search_indexes_activity",

    # LLM activities
    "process_document_with_llm",
    "process_document_hybrid",
    "rank_documents_llm",

    # Storage activities
    "store_document",
    "retrieve_document",
    "delete_document",
    "update_metadata"
]