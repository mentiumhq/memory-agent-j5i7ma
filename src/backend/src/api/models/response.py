"""
Pydantic models for API response validation and serialization.

This module implements comprehensive response models for document operations with enhanced
validation, security sanitization, and support for all retrieval strategies.

Version: Pydantic ^2.0.0
"""

from typing import List, Dict, Any, Optional, Literal
from uuid import UUID
from pydantic import BaseModel, Field, constr, confloat

from .document import DocumentResponse
from .request import RetrievalStrategy

# Status literals for response validation
SUCCESS_STATUS: Literal["success"] = "success"
ERROR_STATUS: Literal["error"] = "error"

# Confidence score bounds
MIN_CONFIDENCE_SCORE = 0.0
MAX_CONFIDENCE_SCORE = 1.0

class BaseResponse(BaseModel):
    """
    Base response model for all API responses with enhanced validation.
    
    Implements core response fields and validation rules used across
    all API response types.
    """
    status: Literal["success", "error"] = Field(
        ...,
        description="Response status indicator"
    )
    message: Optional[constr(strip_whitespace=True, min_length=1)] = Field(
        None,
        description="Optional response message"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Operation completed successfully"
            }
        }


class StoreDocumentResponse(BaseResponse):
    """
    Response model for document storage operation with enhanced validation.
    
    Extends BaseResponse with document-specific fields and validation rules
    for storage operations.
    """
    status: Literal["success"] = Field(
        SUCCESS_STATUS,
        description="Storage operation status"
    )
    document_id: UUID = Field(
        ...,
        description="UUID of stored document"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "document_id": "123e4567-e89b-12d3-a456-426614174000",
                "message": "Document stored successfully"
            }
        }


class GetDocumentResponse(BaseResponse):
    """
    Response model for document retrieval operation with enhanced validation.
    
    Extends BaseResponse with comprehensive document content and metadata
    validation using DocumentResponse model.
    """
    status: Literal["success"] = Field(
        SUCCESS_STATUS,
        description="Retrieval operation status"
    )
    document: DocumentResponse = Field(
        ...,
        description="Retrieved document data"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "document": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "content": "# Sample Document\nThis is a test document.",
                    "format": "markdown",
                    "metadata": {"source": "user", "tags": ["test"]},
                    "token_count": 42
                }
            }
        }


class SearchDocumentResponse(BaseResponse):
    """
    Enhanced response model for document search operation with comprehensive validation.
    
    Extends BaseResponse with search-specific fields including retrieval strategy,
    confidence scores, and result validation.
    """
    status: Literal["success"] = Field(
        SUCCESS_STATUS,
        description="Search operation status"
    )
    documents: List[DocumentResponse] = Field(
        ...,
        description="List of matching documents"
    )
    strategy: RetrievalStrategy = Field(
        ...,
        description="Strategy used for retrieval"
    )
    confidence: confloat(ge=MIN_CONFIDENCE_SCORE, le=MAX_CONFIDENCE_SCORE) = Field(
        ...,
        description="Confidence score for results"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "documents": [
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "content": "# Technical Documentation\nSystem architecture...",
                        "format": "markdown",
                        "metadata": {"source": "system", "tags": ["technical"]},
                        "token_count": 156
                    }
                ],
                "strategy": "hybrid",
                "confidence": 0.95,
                "message": "Found 1 matching document"
            }
        }


class ErrorResponse(BaseResponse):
    """
    Enhanced error response model with secure error handling and sanitization.
    
    Implements comprehensive error reporting with security-focused sanitization
    of error details.
    """
    status: Literal["error"] = Field(
        ERROR_STATUS,
        description="Error status indicator"
    )
    message: constr(strip_whitespace=True, min_length=1) = Field(
        ...,
        description="Error message"
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "error",
                "message": "Failed to process request",
                "details": {
                    "error_code": "VALIDATION_ERROR",
                    "correlation_id": "123e4567-e89b-12d3-a456-426614174000"
                }
            }
        }