"""
Main entry point for the Memory Agent service layer that exposes core services including
document management, caching, LLM processing, and storage operations.

Version: 1.0.0

External Dependencies:
- openai==1.0.0: OpenAI API integration
- tiktoken==0.5.0: Token management
- opentelemetry-api==1.20.0: Telemetry and monitoring
"""

from .cache import CacheService
from .document import DocumentService
from .llm import LLMService

# Export core service interfaces
__all__ = [
    'CacheService',  # Document and query caching functionality
    'DocumentService',  # Core document operations
    'LLMService',  # LLM processing and retrieval strategies
]

# Service version and metadata
SERVICE_VERSION = "1.0.0"
SERVICE_METADATA = {
    "name": "Memory Agent Service Layer",
    "description": "Core service layer for document storage, retrieval, and processing",
    "version": SERVICE_VERSION,
    "cache_service": {
        "description": "Document and query caching functionality",
        "features": [
            "Document chunk caching",
            "Embedding caching",
            "Query result caching",
            "Memory pressure management",
            "Automatic cache invalidation"
        ]
    },
    "document_service": {
        "description": "Core document management functionality",
        "features": [
            "Document storage and retrieval",
            "Token-aware chunking",
            "Multi-strategy search",
            "Document metadata management",
            "Versioning support"
        ]
    },
    "llm_service": {
        "description": "LLM-based document processing",
        "features": [
            "Document reasoning",
            "Relevance ranking",
            "Embedding generation",
            "Similarity calculation",
            "Token management"
        ]
    }
}

# Service capabilities and limits
SERVICE_CAPABILITIES = {
    "supported_models": {
        "gpt-3.5-turbo": {
            "max_tokens": 16384,
            "chunk_size": 4000
        },
        "gpt-4": {
            "max_tokens": 32768,
            "chunk_size": 8000
        }
    },
    "retrieval_strategies": [
        "vector",
        "llm",
        "hybrid",
        "rag+kg"
    ],
    "caching": {
        "document_ttl": 3600,  # 1 hour
        "embedding_ttl": 86400,  # 24 hours
        "query_ttl": 900  # 15 minutes
    }
}

def get_service_info() -> dict:
    """
    Get comprehensive service layer information including version,
    capabilities, and metadata.

    Returns:
        dict: Service information and capabilities
    """
    return {
        "version": SERVICE_VERSION,
        "metadata": SERVICE_METADATA,
        "capabilities": SERVICE_CAPABILITIES
    }