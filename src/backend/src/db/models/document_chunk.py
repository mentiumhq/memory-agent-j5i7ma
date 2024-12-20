"""
SQLAlchemy ORM model for document chunks with token-aware chunking and vector embeddings.
Implements storage schema for document segments with configurable token limits and 
maintains relationships with parent documents.

Version: SQLAlchemy 2.0+
"""

from uuid import uuid4
from typing import Dict, Optional

from sqlalchemy import Column, String, Integer, ForeignKey, UUID, LargeBinary
from sqlalchemy.orm import relationship

from ..base import Base


class DocumentChunk(Base):
    """
    SQLAlchemy ORM model representing a chunk of a document.
    
    Implements token-aware document chunking with support for vector embeddings.
    Maintains relationship with parent document and handles chunk-level metadata.
    Supports configurable token limits (4K for GPT-3.5, 8K for GPT-4).
    """
    
    __tablename__ = "document_chunks"

    # Primary key using UUID for global uniqueness
    id = Column(UUID, primary_key=True, default=uuid4)
    
    # Foreign key to parent document
    document_id = Column(
        UUID,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False
    )
    
    # Chunk content and metadata
    content = Column(String, nullable=False)
    chunk_number = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=False)
    
    # Vector embedding storage
    embedding = Column(LargeBinary, nullable=True)
    
    # Relationship to parent document
    document = relationship(
        "Document",
        back_populates="chunks",
        lazy="select"
    )

    def __init__(
        self,
        document_id: UUID,
        content: str,
        chunk_number: int,
        token_count: int,
        embedding: Optional[bytes] = None
    ) -> None:
        """
        Initialize a new DocumentChunk instance with validation.

        Args:
            document_id: UUID of parent document
            content: Text content of the chunk
            chunk_number: Sequential number of chunk within document
            token_count: Number of tokens in chunk
            embedding: Optional vector embedding of chunk content
        """
        # Set primary key
        self.id = uuid4()
        
        # Validate and set document reference
        if not document_id:
            raise ValueError("Document ID must be specified")
        self.document_id = document_id
        
        # Validate and set content
        if not content:
            raise ValueError("Content must be specified")
        self.content = content
        
        # Validate and set chunk number
        if chunk_number < 0:
            raise ValueError("Chunk number must be non-negative")
        self.chunk_number = chunk_number
        
        # Validate and set token count
        if token_count < 0:
            raise ValueError("Token count must be non-negative")
        if token_count > 8192:  # Max tokens for GPT-4
            raise ValueError("Token count exceeds maximum limit")
        self.token_count = token_count
        
        # Set embedding if provided
        if embedding is not None:
            self.update_embedding(embedding)

    def update_embedding(self, embedding: bytes) -> None:
        """
        Update the chunk's vector embedding.

        Args:
            embedding: New vector embedding as bytes
        """
        if not isinstance(embedding, bytes):
            raise ValueError("Embedding must be bytes")
        self.embedding = embedding

    def to_dict(self) -> Dict:
        """
        Convert chunk to dictionary representation.

        Returns:
            Dict containing chunk attributes and relationships
        """
        # Get base dictionary from parent class
        result = super().to_dict()
        
        # Convert embedding to hex string if present
        if self.embedding is not None:
            result["embedding"] = self.embedding.hex()
            
        return result

    def __repr__(self) -> str:
        """String representation of DocumentChunk instance."""
        return (
            f"<DocumentChunk("
            f"id={self.id}, "
            f"document_id={self.document_id}, "
            f"chunk={self.chunk_number}, "
            f"tokens={self.token_count}"
            f")>"
        )