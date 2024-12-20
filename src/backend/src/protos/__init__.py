"""
Protocol Buffer initialization module for the Memory Agent system.

This module exposes gRPC service stubs and message types generated from Protocol Buffers,
providing a clean interface for client applications to access the Memory Agent's gRPC services.

Version: 1.0.0
"""

# Import all generated protobuf modules
from .memory_agent_pb2 import (  # type: ignore
    # Document Storage Models
    StoreDocumentRequest,
    StoreDocumentResponse,
    
    # Document Retrieval Models
    GetDocumentRequest,
    GetDocumentResponse,
    
    # Document Search Models
    SearchDocumentRequest,
    SearchDocumentResponse,
    
    # Health Check Models
    HealthCheckRequest,
    HealthCheckResponse,
    
    # Common Models
    Document,
    DocumentMetadata,
    SearchStrategy,
    RetrievalResult
)

# Import generated service stubs
from .memory_agent_pb2_grpc import (  # type: ignore
    # Service Stubs
    MemoryAgentServiceStub,
    MemoryAgentServiceServicer,
    
    # Service registration method
    add_MemoryAgentServiceServicer_to_server
)

# Version information
__version__ = "1.0.0"

# Public API
__all__ = [
    # Document Storage
    "StoreDocumentRequest",
    "StoreDocumentResponse",
    
    # Document Retrieval
    "GetDocumentRequest",
    "GetDocumentResponse",
    
    # Document Search
    "SearchDocumentRequest",
    "SearchDocumentResponse",
    
    # Health Check
    "HealthCheckRequest",
    "HealthCheckResponse",
    
    # Common Models
    "Document",
    "DocumentMetadata",
    "SearchStrategy",
    "RetrievalResult",
    
    # Service Components
    "MemoryAgentServiceStub",
    "MemoryAgentServiceServicer",
    "add_MemoryAgentServiceServicer_to_server",
]