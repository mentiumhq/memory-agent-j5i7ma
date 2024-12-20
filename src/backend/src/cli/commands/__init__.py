"""
Initialization module for Memory Agent CLI commands providing centralized command registry.
Implements comprehensive document management operations and service health monitoring.

External Dependencies:
- click==8.1.0: CLI framework for command creation
- rich==13.0.0: Enhanced terminal output formatting
- asyncio==3.11+: Async runtime for command execution

Version: 1.0.0
"""

from typing import List, Dict, Any

# Import CLI commands
from .document import (
    store_document,
    retrieve_document,
    search_documents,
    delete_document
)
from .health import health_check

# Export all available commands
__all__: List[str] = [
    "store_document",
    "retrieve_document", 
    "search_documents",
    "delete_document",
    "health_check"
]

# Command metadata for help text and documentation
COMMAND_METADATA: Dict[str, Dict[str, Any]] = {
    "store_document": {
        "name": "store",
        "help": "Store a new document with metadata",
        "options": [
            "--file, -f: Path to document file (required)",
            "--format: Document format (default: markdown)",
            "--metadata: Document metadata as JSON string"
        ]
    },
    "retrieve_document": {
        "name": "retrieve",
        "help": "Retrieve a document by ID",
        "options": [
            "document_id: Document identifier (required)",
            "--format: Output format (rich, json, text)"
        ]
    },
    "search_documents": {
        "name": "search",
        "help": "Search documents using multiple strategies",
        "options": [
            "query: Search query string (required)",
            "--strategy: Search strategy (vector, llm, hybrid, rag_kg)",
            "--filters: Search filters as JSON string",
            "--limit: Maximum number of results"
        ]
    },
    "delete_document": {
        "name": "delete",
        "help": "Delete a document by ID",
        "options": [
            "document_id: Document identifier (required)",
            "--force: Skip confirmation prompt"
        ]
    },
    "health_check": {
        "name": "health",
        "help": "Check service health status",
        "options": [
            "--verbose, -v: Show detailed component status"
        ]
    }
}

# Security roles and permissions for commands
COMMAND_PERMISSIONS: Dict[str, List[str]] = {
    "store_document": ["agent", "executor", "admin"],
    "retrieve_document": ["agent", "executor", "admin"],
    "search_documents": ["agent", "executor", "admin"],
    "delete_document": ["executor", "admin"],
    "health_check": ["executor", "admin"]
}

# Command rate limits (operations per minute)
COMMAND_RATE_LIMITS: Dict[str, int] = {
    "store_document": 60,
    "retrieve_document": 120,
    "search_documents": 100,
    "delete_document": 30,
    "health_check": 10
}