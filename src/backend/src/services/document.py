"""
High-level document service implementing comprehensive document operations including storage,
retrieval, chunking, embedding, and search functionality with multiple retrieval strategies.

Version:
- asyncio==3.11+
- typing==3.11+
- opentelemetry-api==1.20.0
"""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from functools import wraps
from prometheus_client import Counter, Histogram
import logging

from .storage import StorageService
from .embedding import EmbeddingService
from repositories.document import DocumentRepository
from core.errors import StorageError, ErrorCode, LLMError
from core.telemetry import create_tracer
from config.logging import get_logger
from db.models.document import Document
from db.models.document_chunk import DocumentChunk

# Initialize logging and tracing
LOGGER = get_logger(__name__)
TRACER = create_tracer('document_service')

# Configuration constants
DEFAULT_SEARCH_LIMIT = 10
SIMILARITY_THRESHOLD = 0.8
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30
CHUNK_SIZES = {
    "gpt-3.5": 4000,  # 4K tokens for GPT-3.5
    "gpt-4": 8000     # 8K tokens for GPT-4
}

# Monitoring metrics
document_operations = Counter('document_operations_total', 'Total document operations', ['operation'])
document_errors = Counter('document_errors_total', 'Total document errors', ['error_type'])
operation_duration = Histogram('document_operation_duration_seconds', 'Operation duration')

def monitor_performance(func):
    """Decorator for monitoring operation performance and errors."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = datetime.now(timezone.utc)
        try:
            result = await func(*args, **kwargs)
            document_operations.labels(operation=func.__name__).inc()
            return result
        except Exception as e:
            document_errors.labels(error_type=type(e).__name__).inc()
            raise
        finally:
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            operation_duration.observe(duration)
    return wrapper

class DocumentService:
    """
    Core service for managing document operations with support for multiple retrieval
    strategies, error handling, monitoring, and security features.
    """

    def __init__(
        self,
        storage_service: StorageService,
        embedding_service: EmbeddingService,
        document_repo: DocumentRepository
    ) -> None:
        """
        Initialize document service with required dependencies.

        Args:
            storage_service: Service for document storage operations
            embedding_service: Service for embedding generation
            document_repo: Repository for document database operations
        """
        self._storage_service = storage_service
        self._embedding_service = embedding_service
        self._document_repo = document_repo
        
        # Initialize rate limiting and concurrency control
        self._semaphore = asyncio.Semaphore(10)
        self._retry_delays = [1, 2, 4]  # Exponential backoff

    @monitor_performance
    async def store_document(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Store document with content chunking and embedding generation.

        Args:
            content: Document content
            metadata: Document metadata

        Returns:
            str: Stored document ID

        Raises:
            StorageError: If document storage fails
        """
        async with self._semaphore:
            try:
                with TRACER.start_as_current_span("store_document") as span:
                    span.set_attribute("content_length", len(content))
                    
                    # Calculate chunks based on model limits
                    model = metadata.get("model", "gpt-3.5")
                    chunk_size = CHUNK_SIZES.get(model, CHUNK_SIZES["gpt-3.5"])
                    chunks = self._create_document_chunks(content, chunk_size)
                    
                    # Generate embeddings for chunks
                    embeddings = await self._embedding_service.async_batch_generate_embeddings(
                        [chunk.content for chunk in chunks]
                    )
                    
                    # Store document content
                    document_id = await self._storage_service.store_document(
                        content.encode('utf-8'),
                        metadata
                    )
                    
                    # Create document record with chunks
                    document = Document(
                        content=f"s3://{document_id}",
                        format=metadata.get("format", "text"),
                        metadata=metadata,
                        token_count=sum(chunk.token_count for chunk in chunks)
                    )
                    
                    # Update chunks with embeddings
                    for chunk, embedding in zip(chunks, embeddings):
                        chunk.update_embedding(embedding.tobytes())
                    
                    # Store in repository
                    stored_doc = self._document_repo.create_with_chunks(document, chunks)
                    
                    LOGGER.info(
                        "Document stored successfully",
                        extra={
                            "document_id": str(stored_doc.id),
                            "chunk_count": len(chunks)
                        }
                    )
                    
                    return str(stored_doc.id)

            except Exception as e:
                LOGGER.error(f"Document storage failed: {str(e)}", exc_info=True)
                raise StorageError(
                    "Failed to store document",
                    ErrorCode.STORAGE_ERROR,
                    {"error": str(e)}
                )

    @monitor_performance
    async def search_documents(
        self,
        query: str,
        strategy: str = "hybrid",
        filters: Optional[Dict[str, Any]] = None,
        limit: int = DEFAULT_SEARCH_LIMIT
    ) -> List[Dict[str, Any]]:
        """
        Search documents using specified strategy with fallback mechanisms.

        Args:
            query: Search query
            strategy: Search strategy (vector, llm, hybrid, or rag+kg)
            filters: Optional metadata filters
            limit: Maximum number of results

        Returns:
            List of matching documents with relevance scores

        Raises:
            StorageError: If search operation fails
        """
        async with self._semaphore:
            try:
                with TRACER.start_as_current_span("search_documents") as span:
                    span.set_attribute("strategy", strategy)
                    span.set_attribute("query_length", len(query))
                    
                    # Generate query embedding
                    query_embedding = await self._embedding_service.async_generate_embedding(query)
                    
                    # Execute search based on strategy
                    if strategy == "vector":
                        results = await self._vector_search(query_embedding, filters, limit)
                    elif strategy == "llm":
                        results = await self._llm_search(query, filters, limit)
                    elif strategy == "hybrid":
                        results = await self._hybrid_search(query, query_embedding, filters, limit)
                    elif strategy == "rag+kg":
                        results = await self._rag_kg_search(query, query_embedding, filters, limit)
                    else:
                        raise ValueError(f"Invalid search strategy: {strategy}")
                    
                    # Enrich results with metadata
                    enriched_results = []
                    for doc, score in results:
                        doc_dict = doc.to_dict()
                        doc_dict["relevance_score"] = score
                        enriched_results.append(doc_dict)
                    
                    return enriched_results

            except Exception as e:
                LOGGER.error(f"Document search failed: {str(e)}", exc_info=True)
                raise StorageError(
                    "Failed to search documents",
                    ErrorCode.STORAGE_ERROR,
                    {"strategy": strategy, "error": str(e)}
                )

    async def _vector_search(
        self,
        query_embedding: Any,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[Tuple[Document, float]]:
        """Execute vector-based similarity search."""
        # Get all document chunks
        chunks = await self._document_repo.get_all_chunks()
        
        # Calculate similarities
        chunk_scores = []
        for chunk in chunks:
            if chunk.embedding:
                similarity = self._embedding_service.calculate_similarity(
                    query_embedding,
                    chunk.embedding
                )
                if similarity >= SIMILARITY_THRESHOLD:
                    chunk_scores.append((chunk, similarity))
        
        # Sort by similarity and get unique documents
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        seen_docs = set()
        results = []
        
        for chunk, score in chunk_scores:
            if len(results) >= limit:
                break
            if chunk.document_id not in seen_docs:
                doc = self._document_repo.get(chunk.document_id)
                if doc and self._matches_filters(doc, filters):
                    results.append((doc, score))
                    seen_docs.add(chunk.document_id)
        
        return results

    async def _llm_search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[Tuple[Document, float]]:
        """Execute LLM-based semantic search."""
        # Implementation would use LLM to evaluate semantic relevance
        # This is a placeholder for the actual implementation
        raise NotImplementedError("LLM search not implemented")

    async def _hybrid_search(
        self,
        query: str,
        query_embedding: Any,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[Tuple[Document, float]]:
        """Execute hybrid search combining vector and LLM approaches."""
        # Get vector search results
        vector_results = await self._vector_search(query_embedding, filters, limit * 2)
        
        # Rerank using LLM (placeholder)
        # This would use LLM to rerank vector results
        return vector_results[:limit]

    async def _rag_kg_search(
        self,
        query: str,
        query_embedding: Any,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[Tuple[Document, float]]:
        """Execute RAG+KG search using knowledge graph relationships."""
        # Implementation would use knowledge graph for enhanced retrieval
        # This is a placeholder for the actual implementation
        raise NotImplementedError("RAG+KG search not implemented")

    def _create_document_chunks(
        self,
        content: str,
        chunk_size: int
    ) -> List[DocumentChunk]:
        """
        Create document chunks with token-aware splitting.

        Args:
            content: Document content
            chunk_size: Maximum chunk size in tokens

        Returns:
            List of document chunks
        """
        # Simple chunking by paragraphs
        # In production, use proper tokenization and semantic chunking
        paragraphs = content.split('\n\n')
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for para in paragraphs:
            # Simple token count approximation
            para_tokens = len(para.split())
            
            if current_tokens + para_tokens > chunk_size:
                if current_chunk:
                    chunk_content = '\n\n'.join(current_chunk)
                    chunks.append(DocumentChunk(
                        document_id=None,  # Will be set after document creation
                        content=chunk_content,
                        chunk_number=len(chunks),
                        token_count=current_tokens
                    ))
                    current_chunk = []
                    current_tokens = 0
            
            current_chunk.append(para)
            current_tokens += para_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_content = '\n\n'.join(current_chunk)
            chunks.append(DocumentChunk(
                document_id=None,
                content=chunk_content,
                chunk_number=len(chunks),
                token_count=current_tokens
            ))
        
        return chunks

    def _matches_filters(self, document: Document, filters: Optional[Dict[str, Any]]) -> bool:
        """Check if document matches metadata filters."""
        if not filters:
            return True
            
        for key, value in filters.items():
            if key not in document.metadata or document.metadata[key] != value:
                return False
        return True