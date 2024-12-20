"""
SQLAlchemy ORM model for the DocumentIndex entity.
Implements comprehensive indexing schema for documents with metadata,
access tracking, and retrieval optimization capabilities.

Version: SQLAlchemy 2.0+
"""

from datetime import datetime, timezone
from typing import Dict, Optional
from uuid import uuid4

from sqlalchemy import Column, ForeignKey, String, Integer, JSON, DateTime, UUID
from sqlalchemy.orm import relationship

from ..base import Base
from .document import Document


class DocumentIndex(Base):
    """
    SQLAlchemy ORM model representing a document index with comprehensive
    metadata and access tracking capabilities. Manages document search
    optimization, access patterns, and caching strategy support.
    """
    
    __tablename__ = "document_indexes"

    # Primary key using UUID for global uniqueness
    id = Column(UUID, primary_key=True, default=uuid4)
    
    # Foreign key relationship to Document
    document_id = Column(
        UUID,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Flexible metadata storage for search optimization
    metadata = Column(JSON, nullable=False, default=dict)
    
    # Access pattern tracking
    last_accessed = Column(DateTime(timezone=True), nullable=False)
    access_count = Column(Integer, nullable=False, default=0)
    
    # Bidirectional relationship with Document
    document = relationship(
        "Document",
        back_populates="index",
        lazy="select"
    )

    def __init__(self, document_id: UUID, metadata: Dict) -> None:
        """
        Initialize a new DocumentIndex instance with required attributes.

        Args:
            document_id: UUID of the associated document
            metadata: Initial metadata dictionary for indexing
        
        Raises:
            ValueError: If metadata is not a valid dictionary
        """
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        # Set primary key
        self.id = uuid4()
        
        # Set document relationship
        self.document_id = document_id
        
        # Initialize metadata
        self.metadata = metadata
        
        # Initialize access tracking
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count = 0

    def update_metadata(self, metadata: Dict) -> None:
        """
        Updates the index metadata while maintaining access tracking.

        Args:
            metadata: New metadata to merge with existing

        Raises:
            ValueError: If metadata is not a valid dictionary
        """
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a dictionary")

        # Preserve existing required fields
        required_fields = {
            key: self.metadata[key]
            for key in self.metadata
            if key.startswith("_")  # Protected fields start with underscore
        }
        
        # Merge new metadata with required fields preserved
        self.metadata = {**metadata, **required_fields}
        
        # Update access timestamp
        self.last_accessed = datetime.now(timezone.utc)

    def record_access(self) -> None:
        """
        Records a document access event by updating tracking metrics.
        Implements overflow protection and maintains access patterns.
        """
        # Protect against counter overflow
        if self.access_count < (2**31 - 1):  # Max value for 32-bit integer
            self.access_count += 1
        
        # Update access timestamp
        self.last_accessed = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        """
        Converts the index to a secure dictionary representation.

        Returns:
            Dict containing sanitized index attributes
        """
        return {
            "id": str(self.id),
            "document_id": str(self.document_id),
            "metadata": self.metadata,
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            # Include document data if relationship is loaded
            "document": self.document.to_dict() if self.document else None
        }

    def __repr__(self) -> str:
        """String representation of DocumentIndex instance."""
        return (
            f"<DocumentIndex(id={self.id}, "
            f"document_id={self.document_id}, "
            f"access_count={self.access_count})>"
        )