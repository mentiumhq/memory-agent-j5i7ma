"""
Service module for generating and managing document embeddings using OpenAI's text embedding models.
Implements high-performance, fault-tolerant vector generation with comprehensive telemetry and error handling.

Version: 1.0.0
"""

import asyncio
import numpy as np
from typing import List, Dict, Optional, Union
import openai
from openai import AsyncOpenAI
import logging
from functools import lru_cache

from core.errors import ErrorCode, LLMError
from core.telemetry import create_tracer
from config.logging import get_logger

# Initialize logging and telemetry
LOGGER = get_logger(__name__)
TRACER = create_tracer('embedding')

# Constants for embedding service
DEFAULT_MODEL = 'text-embedding-ada-002'
MAX_RETRIES = 3
RETRY_DELAY = 1.0
MAX_BATCH_SIZE = 100
EMBEDDING_DIMENSION = 1536  # Ada-002 dimension

class EmbeddingService:
    """High-performance service for generating and managing document embeddings with comprehensive error handling and telemetry."""
    
    def __init__(self, settings) -> None:
        """
        Initialize embedding service with configuration and telemetry setup.
        
        Args:
            settings: Application settings instance containing API keys and configuration
        """
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._model = DEFAULT_MODEL
        self._dimension = EMBEDDING_DIMENSION
        self._cache: Dict[str, np.ndarray] = {}
        self._retry_count = 0
        self._semaphore = asyncio.Semaphore(10)  # Limit concurrent API calls
        
        # Initialize metrics
        self._meter = create_tracer('embedding').get_meter()
        self._embedding_counter = self._meter.create_counter(
            "embedding_requests_total",
            description="Total number of embedding requests"
        )
        self._embedding_latency = self._meter.create_histogram(
            "embedding_latency_seconds",
            description="Embedding request latency"
        )
        self._error_counter = self._meter.create_counter(
            "embedding_errors_total",
            description="Total number of embedding errors"
        )

    async def async_generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate embedding vector for input text with error handling and telemetry.
        
        Args:
            text: Input text to generate embedding for
            
        Returns:
            Normalized embedding vector as numpy array
            
        Raises:
            LLMError: If embedding generation fails
        """
        with TRACER.start_as_current_span("generate_embedding") as span:
            span.set_attribute("text_length", len(text))
            
            # Check cache
            cache_key = hash(text)
            if cache_key in self._cache:
                span.set_attribute("cache_hit", True)
                return self._cache[cache_key]
            
            try:
                async with self._semaphore:
                    self._embedding_counter.add(1)
                    start_time = asyncio.get_event_loop().time()
                    
                    response = await self._client.embeddings.create(
                        model=self._model,
                        input=text,
                        encoding_format="float"
                    )
                    
                    duration = asyncio.get_event_loop().time() - start_time
                    self._embedding_latency.record(duration)
                    
                    embedding = np.array(response.data[0].embedding, dtype=np.float32)
                    normalized = normalize_vector(embedding)
                    
                    # Cache the result
                    self._cache[cache_key] = normalized
                    
                    span.set_attribute("success", True)
                    return normalized
                    
            except openai.RateLimitError as e:
                await self._handle_rate_limit(e)
                return await self.async_generate_embedding(text)
                
            except Exception as e:
                await self._handle_error(e)
                raise LLMError(
                    f"Failed to generate embedding: {str(e)}",
                    error_code=ErrorCode.EMBEDDING_ERROR,
                    details={"text_length": len(text)}
                )

    async def async_batch_generate_embeddings(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts with optimized batch processing.
        
        Args:
            texts: List of input texts to generate embeddings for
            
        Returns:
            List of normalized embedding vectors
            
        Raises:
            LLMError: If batch embedding generation fails
        """
        with TRACER.start_as_current_span("batch_generate_embeddings") as span:
            span.set_attribute("batch_size", len(texts))
            
            if not texts:
                return []
                
            # Split into batches
            batches = [texts[i:i + MAX_BATCH_SIZE] 
                      for i in range(0, len(texts), MAX_BATCH_SIZE)]
            
            try:
                # Process batches concurrently
                tasks = []
                for batch in batches:
                    tasks.append(self._process_batch(batch))
                
                results = await asyncio.gather(*tasks)
                embeddings = [emb for batch in results for emb in batch]
                
                span.set_attribute("success", True)
                return embeddings
                
            except Exception as e:
                await self._handle_error(e)
                raise LLMError(
                    f"Failed to generate batch embeddings: {str(e)}",
                    error_code=ErrorCode.EMBEDDING_ERROR,
                    details={"batch_size": len(texts)}
                )

    async def _process_batch(self, texts: List[str]) -> List[np.ndarray]:
        """
        Process a batch of texts to generate embeddings.
        
        Args:
            texts: Batch of texts to process
            
        Returns:
            List of embedding vectors for the batch
        """
        async with self._semaphore:
            try:
                self._embedding_counter.add(len(texts))
                start_time = asyncio.get_event_loop().time()
                
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                    encoding_format="float"
                )
                
                duration = asyncio.get_event_loop().time() - start_time
                self._embedding_latency.record(duration)
                
                embeddings = [np.array(data.embedding, dtype=np.float32) 
                            for data in response.data]
                return [normalize_vector(emb) for emb in embeddings]
                
            except Exception as e:
                LOGGER.error(f"Batch processing failed: {str(e)}", exc_info=True)
                raise

    async def _handle_rate_limit(self, error: Exception) -> None:
        """
        Handle rate limit errors with exponential backoff.
        
        Args:
            error: Rate limit error from API
        """
        self._retry_count += 1
        if self._retry_count > MAX_RETRIES:
            raise LLMError(
                "Max retries exceeded for rate limit",
                error_code=ErrorCode.EMBEDDING_ERROR
            )
            
        delay = RETRY_DELAY * (2 ** (self._retry_count - 1))
        LOGGER.warning(f"Rate limit hit, retrying in {delay}s")
        await asyncio.sleep(delay)

    async def _handle_error(self, error: Exception) -> None:
        """
        Comprehensive error handling for embedding operations.
        
        Args:
            error: Exception to handle
        """
        self._error_counter.add(1)
        LOGGER.error(
            f"Embedding error: {str(error)}",
            exc_info=True,
            extra={"error_type": type(error).__name__}
        )

    def calculate_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate optimized cosine similarity between embedding vectors.
        
        Args:
            vector1: First embedding vector
            vector2: Second embedding vector
            
        Returns:
            Cosine similarity score between 0 and 1
        """
        if vector1.shape != vector2.shape:
            raise ValueError("Vector dimensions must match")
            
        similarity = np.dot(vector1, vector2)
        return float(np.clip(similarity, 0, 1))

@lru_cache(maxsize=10000)
def normalize_vector(vector: np.ndarray) -> np.ndarray:
    """
    Normalize embedding vector to unit length with caching optimization.
    
    Args:
        vector: Input vector to normalize
        
    Returns:
        Normalized vector with unit L2 norm
    """
    norm = np.linalg.norm(vector)
    if norm == 0:
        return vector
    return vector / norm

__all__ = ['EmbeddingService', 'normalize_vector']