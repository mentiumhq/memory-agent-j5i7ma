"""
SQLAlchemy ORM model for the Document entity.
Implements the core document storage schema with relationships to chunks and indexes.
Handles document metadata, content storage, and token tracking.

Version: SQLAlchemy 2.0+
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

from sqlalchemy import Column, String, Integer, JSON, DateTime, UUID, ForeignKey
from sqlalchemy.orm import relationship

from ..base import Base


class Document(Base):
    """
    SQLAlchemy ORM model representing a document in the system.
    
    Implements comprehensive document storage with metadata, content references,
    and relationships to chunks and indexes. Ensures data integrity and efficient
    querying capabilities.
    """
    
    __tablename__ = "documents"

    # Primary key using UUID for global uniqueness
    id = Column(UUID, primary_key=True, default=uuid4)
    
    # S3 reference to document content
    content = Column(String, nullable=False)
    
    # Document format (e.g., markdown, json)
    format = Column(String, nullable=False)
    
    # Timestamps for document lifecycle tracking
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    
    # Flexible metadata storage as JSON
    metadata = Column(JSON, nullable=False, default=dict)
    
    # Token count for LLM processing
    token_count = Column(Integer, nullable=False)
    
    # Relationships to related entities
    chunks = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    index = relationship(
        "DocumentIndex",
        back_populates="document",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __init__(
        self,
        content: str,
        format: str,
        metadata: Optional[Dict] = None,
        token_count: int = 0
    ) -> None:
        """
        Initialize a new Document instance with validation.

        Args:
            content: S3 reference to document content
            format: Document format identifier
            metadata: Optional document metadata
            token_count: Number of tokens in document
        """
        # Set primary key
        self.id = uuid4()
        
        # Validate and set content reference
        if not content.startswith("s3://"):
            raise ValueError("Content must be an S3 reference")
        self.content = content
        
        # Validate and set format
        if not format:
            raise ValueError("Format must be specified")
        self.format = format
        
        # Initialize metadata
        self.metadata = metadata or {}
        
        # Validate and set token count
        if token_count < 0:
            raise ValueError("Token count must be non-negative")
        self.token_count = token_count
        
        # Set timestamps
        current_time = datetime.now(timezone.utc)
        self.created_at = current_time
        self.updated_at = current_time

    def update_content(self, content: str, token_count: int) -> None:
        """
        Update document content and token count.

        Args:
            content: New S3 content reference
            token_count: New token count
        """
        # Validate content reference
        if not content.startswith("s3://"):
            raise ValueError("Content must be an S3 reference")
        
        # Validate token count
        if token_count < 0:
            raise ValueError("Token count must be non-negative")
        
        # Update fields
        self.content = content
        self.token_count = token_count
        self.updated_at = datetime.now(timezone.utc)

    def update_metadata(self, metadata: Dict) -> None:
        """
        Update document metadata using merge strategy.

        Args:
            metadata: New metadata to merge
        """
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")
        
        # Merge new metadata with existing
        self.metadata.update(metadata)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        """
        Convert document to dictionary representation.

        Returns:
            Dict containing document attributes and relationships
        """
        # Get base dictionary from parent class
        result = super().to_dict()
        
        # Format timestamps as ISO strings
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        
        return result

    def __repr__(self) -> str:
        """String representation of Document instance."""
        return f"<Document(id={self.id}, format={self.format}, tokens={self.token_count})>"