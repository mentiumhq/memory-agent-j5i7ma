"""
Package initialization file exposing core Temporal workflow functionality for document operations.
Provides a unified interface for document storage, retrieval, search, and management workflows
with comprehensive type hints, performance monitoring, and fault tolerance.

Version: 1.0.0
External Dependencies:
- temporalio==1.0.0: Temporal workflow SDK
- opentelemetry-api==1.0.0: Distributed tracing
"""

from typing import Dict, List, Optional

# Import core document workflow functions
from .document import (
    store_document_workflow,
    retrieve_document_workflow,
    search_documents_workflow,
    update_document_workflow,
    delete_document_workflow
)

# Import search workflow classes
from .search import (
    VectorSearchWorkflow,
    LLMSearchWorkflow,
    HybridSearchWorkflow,
    RAGKGSearchWorkflow
)

# Package metadata
__version__ = "1.0.0"
__author__ = "Memory Agent Team"

# Define public interface
__all__ = [
    # Document workflows
    "store_document_workflow",
    "retrieve_document_workflow", 
    "search_documents_workflow",
    "update_document_workflow",
    "delete_document_workflow",
    
    # Search workflows
    "VectorSearchWorkflow",
    "LLMSearchWorkflow",
    "HybridSearchWorkflow", 
    "RAGKGSearchWorkflow",
]

# Performance targets from technical specification
PERFORMANCE_TARGETS = {
    "VECTOR_SEARCH_MS": 500,  # Vector search < 500ms
    "LLM_SEARCH_MS": 3000,    # LLM search < 3000ms
    "CONCURRENT_REQUESTS": 50  # 50 requests/second
}

# Search strategy configuration
SEARCH_STRATEGIES = {
    "VECTOR": "vector",      # Pure vector similarity search
    "LLM": "llm",           # Pure LLM-based search
    "HYBRID": "hybrid",      # Combined vector + LLM approach
    "RAG_KG": "rag_kg"      # RAG with Knowledge Graph
}

# Workflow retry configuration
WORKFLOW_RETRY_POLICY = {
    "initial_interval": 1,      # Start with 1 second delay
    "backoff_coefficient": 2,   # Double delay on each retry
    "maximum_attempts": 5,      # Maximum 5 retry attempts
    "maximum_interval": 60      # Cap delay at 60 seconds
}

# Workflow timeout configuration
WORKFLOW_TIMEOUTS = {
    "schedule_to_close": 300,  # Total workflow timeout
    "start_to_close": 60,      # Single attempt timeout
    "heartbeat": 10           # Activity heartbeat interval
}