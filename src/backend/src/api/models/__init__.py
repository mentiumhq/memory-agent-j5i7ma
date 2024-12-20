"""
Entry point for the API models package that exports all Pydantic models for request/response validation and serialization.

This module provides a centralized access point for document-related models, request models, and response models used 
throughout the API. All models implement comprehensive validation rules and security measures.

Version: 1.0.0
"""

# Document models
from .document import (
    Document,
    DocumentChunk
)

# Request models
from .request import (
    RetrievalStrategy,
    StoreDocumentRequest,
    GetDocumentRequest, 
    SearchDocumentRequest
)

# Response models
from .response import (
    BaseResponse,
    ErrorResponse,
    StoreDocumentResponse,
    GetDocumentResponse,
    SearchDocumentResponse
)

# Version information
__version__ = "1.0.0"

# Export all models
__all__ = [
    # Document models
    "Document",
    "DocumentChunk",
    
    # Request models
    "RetrievalStrategy",
    "StoreDocumentRequest",
    "GetDocumentRequest",
    "SearchDocumentRequest",
    
    # Response models
    "BaseResponse",
    "ErrorResponse", 
    "StoreDocumentResponse",
    "GetDocumentResponse",
    "SearchDocumentResponse"
]

# Model metadata for API documentation
model_metadata = {
    "document_models": {
        "Document": "Core document data model with content and metadata validation",
        "DocumentChunk": "Document chunk model for token-aware document segmentation"
    },
    "request_models": {
        "RetrievalStrategy": "Enum of supported document retrieval strategies",
        "StoreDocumentRequest": "Request model for document storage operations",
        "GetDocumentRequest": "Request model for document retrieval operations",
        "SearchDocumentRequest": "Request model for document search operations"
    },
    "response_models": {
        "BaseResponse": "Base response model with status and message fields",
        "ErrorResponse": "Error response model with secure error reporting",
        "StoreDocumentResponse": "Response model for document storage operations",
        "GetDocumentResponse": "Response model for document retrieval operations", 
        "SearchDocumentResponse": "Response model for document search operations"
    }
}