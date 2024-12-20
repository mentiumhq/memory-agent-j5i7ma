"""
Pydantic models for document-related API requests and responses.

Implements comprehensive data validation, serialization, and token-aware processing
for the Memory Agent system. Includes security-focused validation rules and support
for multiple LLM contexts.

Version: Pydantic 2.0+
"""

from typing import Dict, Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

from ...db.models.document import Document
from ...core.utils import generate_uuid

# Supported document formats
SUPPORTED_FORMATS = ["text", "markdown", "json"]

# Content length limits
MAX_CONTENT_LENGTH = 1_000_000  # 1MB

# Token limits for different LLM contexts
GPT35_MAX_TOKENS = 4096  # GPT-3.5 context window
GPT4_MAX_TOKENS = 8192   # GPT-4 context window


class DocumentBase(BaseModel):
    """
    Base Pydantic model for document data validation with comprehensive security checks.
    """
    content: str = Field(
        ...,
        min_length=1,
        max_length=MAX_CONTENT_LENGTH,
        description="Document content"
    )
    format: str = Field(
        ...,
        description="Document format (text, markdown, json)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional document metadata"
    )

    @model_validator(mode='before')
    def validate_document(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate complete document data with security checks.

        Args:
            values: Raw input values

        Returns:
            Validated values dictionary

        Raises:
            ValueError: If validation fails
        """
        # Validate content length
        content = values.get('content')
        if content and len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"Content length exceeds maximum of {MAX_CONTENT_LENGTH} characters")

        # Validate format
        format_value = values.get('format')
        if format_value and format_value not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format. Must be one of: {SUPPORTED_FORMATS}")

        # Initialize metadata if None
        if values.get('metadata') is None:
            values['metadata'] = {}

        return values

    @model_validator(mode='after')
    def check_security(self) -> 'DocumentBase':
        """
        Perform security validation on document data.

        Returns:
            Self if validation passes

        Raises:
            ValueError: If security validation fails
        """
        # Check for potential XSS in content
        if '<script' in self.content.lower():
            raise ValueError("Content contains potentially malicious script tags")

        # Validate metadata structure
        if not isinstance(self.metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        # Check metadata for sensitive information
        sensitive_keys = {'password', 'token', 'secret', 'key', 'credential'}
        if any(k.lower() in sensitive_keys for k in self.metadata.keys()):
            raise ValueError("Metadata contains sensitive information")

        return self


class DocumentCreate(DocumentBase):
    """
    Pydantic model for document creation requests with enhanced validation.
    """
    class Config:
        json_schema_extra = {
            "example": {
                "content": "# Sample Document\nThis is a test document.",
                "format": "markdown",
                "metadata": {"source": "user", "tags": ["test"]}
            }
        }


class DocumentResponse(DocumentBase):
    """
    Pydantic model for document API responses with token awareness.
    """
    id: UUID = Field(
        default_factory=generate_uuid,
        description="Document UUID"
    )
    token_count: int = Field(
        ...,
        ge=0,
        le=GPT4_MAX_TOKENS,
        description="Number of tokens in document"
    )

    @classmethod
    def from_orm(cls, db_document: Document) -> 'DocumentResponse':
        """
        Create response model from ORM model with validation.

        Args:
            db_document: SQLAlchemy Document instance

        Returns:
            Validated DocumentResponse instance

        Raises:
            ValueError: If validation fails
        """
        if not db_document:
            raise ValueError("Invalid database document")

        # Validate token count against LLM limits
        if db_document.token_count > GPT4_MAX_TOKENS:
            raise ValueError(f"Document exceeds maximum token limit of {GPT4_MAX_TOKENS}")

        return cls(
            id=db_document.id,
            content=db_document.content,
            format=db_document.format,
            metadata=db_document.metadata,
            token_count=db_document.token_count
        )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "content": "# Sample Document\nThis is a test document.",
                "format": "markdown",
                "metadata": {"source": "user", "tags": ["test"]},
                "token_count": 42
            }
        }