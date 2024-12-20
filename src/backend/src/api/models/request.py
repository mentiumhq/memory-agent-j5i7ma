"""
Pydantic models for API request validation and serialization.

This module implements comprehensive request models for document operations including
storage, retrieval, and search with strict validation rules and security measures.

Version: Pydantic 2.0+
"""

from enum import Enum
from typing import Dict, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field, validator

from .document import DocumentBase

# Search result limits
DEFAULT_SEARCH_LIMIT = 10
MAX_SEARCH_LIMIT = 100

class RetrievalStrategy(str, Enum):
    """
    Supported document retrieval strategies.
    
    Defines the available approaches for document retrieval and search operations
    with comprehensive strategy options.
    """
    VECTOR = "vector"     # Vector-based similarity search
    LLM = "llm"          # Pure LLM-based reasoning and selection
    HYBRID = "hybrid"    # Combined vector and LLM approach
    RAG_KG = "rag_kg"    # Knowledge graph enhanced retrieval


class StoreDocumentRequest(DocumentBase):
    """
    Request model for document storage operations.
    
    Inherits from DocumentBase to ensure consistent validation rules
    and security measures across document operations.
    """
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "# Sample Document\nThis is a test document.",
                "format": "markdown",
                "metadata": {
                    "source": "user",
                    "tags": ["test"]
                }
            }
        }


class GetDocumentRequest(BaseModel):
    """
    Request model for document retrieval operations.
    
    Implements secure UUID validation for document identification.
    """
    document_id: UUID = Field(
        ...,
        description="UUID of the document to retrieve"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class SearchDocumentRequest(BaseModel):
    """
    Request model for document search operations.
    
    Implements comprehensive validation for search parameters including
    query validation, strategy selection, and result limiting.
    """
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Search query string"
    )
    
    strategy: RetrievalStrategy = Field(
        default=RetrievalStrategy.HYBRID,
        description="Document retrieval strategy to use"
    )
    
    filters: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional metadata filters for search"
    )
    
    limit: Optional[int] = Field(
        default=DEFAULT_SEARCH_LIMIT,
        ge=1,
        le=MAX_SEARCH_LIMIT,
        description="Maximum number of results to return"
    )

    @validator("limit")
    def validate_limit(cls, v: Optional[int]) -> int:
        """
        Validate search result limit within acceptable bounds.
        
        Args:
            v: Limit value to validate
            
        Returns:
            Validated limit value
            
        Raises:
            ValueError: If limit is outside acceptable range
        """
        # Use default if None provided
        if v is None:
            return DEFAULT_SEARCH_LIMIT
            
        # Ensure limit is within bounds
        if v < 1:
            raise ValueError("Limit must be positive")
        if v > MAX_SEARCH_LIMIT:
            raise ValueError(f"Limit cannot exceed {MAX_SEARCH_LIMIT}")
            
        return v

    @validator("filters")
    def validate_filters(cls, v: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate search filters for security and correctness.
        
        Args:
            v: Filters dictionary to validate
            
        Returns:
            Validated filters dictionary
            
        Raises:
            ValueError: If filters are invalid
        """
        if v is None:
            return {}
            
        # Validate filter structure
        if not isinstance(v, dict):
            raise ValueError("Filters must be a dictionary")
            
        # Check for sensitive keys
        sensitive_keys = {'password', 'token', 'secret', 'key', 'credential'}
        if any(k.lower() in sensitive_keys for k in v.keys()):
            raise ValueError("Filters contain sensitive information")
            
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "query": "technical documentation about system architecture",
                "strategy": "hybrid",
                "filters": {
                    "format": "markdown",
                    "tags": ["technical", "architecture"]
                },
                "limit": 10
            }
        }