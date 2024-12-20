"""
High-level LLM service module for document reasoning and retrieval capabilities.
Implements comprehensive token management, caching, telemetry, and error handling.

Version: 1.0.0
External Dependencies:
- tiktoken==0.5.0: Token counting and management
"""

import asyncio
from typing import List, Dict, Optional, Union
import tiktoken
from integrations.llm.openai import OpenAIClient
from core.errors import LLMError, ErrorCode
from core.telemetry import create_tracer
from config.logging import get_logger

# Initialize logging and telemetry
LOGGER = get_logger(__name__)
TRACER = create_tracer('llm_service')

# Constants for retry and caching
MAX_RETRIES = 3
RETRY_DELAY = 1.0

# Token management constants
MODEL_LIMITS = {
    'gpt-3.5-turbo': 16384,
    'gpt-4': 32768
}

def get_token_count(text: str) -> int:
    """
    Calculate token count for input text using tiktoken.
    
    Args:
        text: Input text to count tokens
        
    Returns:
        Number of tokens in text
        
    Raises:
        LLMError: If token counting fails
    """
    try:
        encoding = tiktoken.encoding_for_model('gpt-4')
        return len(encoding.encode(text))
    except Exception as e:
        LOGGER.error(f"Token counting failed: {e}", exc_info=True)
        raise LLMError(
            message="Failed to count tokens",
            error_code=ErrorCode.LLM_ERROR,
            details={"error": str(e)}
        )

class LLMService:
    """
    High-level service for LLM-based document operations with enhanced
    caching, token management, and telemetry.
    """
    
    def __init__(self, llm_client: OpenAIClient, cache_ttl: Optional[int] = 3600):
        """
        Initialize LLM service with OpenAI client, cache, and model limits.
        
        Args:
            llm_client: OpenAI client instance
            cache_ttl: Cache TTL in seconds (default: 1 hour)
        """
        self._client = llm_client
        self._cache = {}  # Simple in-memory cache
        self._cache_ttl = cache_ttl
        self._model_limits = MODEL_LIMITS.copy()
        
        LOGGER.info(
            "Initialized LLM service",
            extra={
                "cache_ttl": cache_ttl,
                "model_limits": self._model_limits
            }
        )

    async def async_reason_documents(
        self,
        query: str,
        documents: List[str],
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Perform LLM reasoning on documents with query using caching and telemetry.
        
        Args:
            query: Reasoning query
            documents: List of documents to reason about
            options: Optional configuration parameters
            
        Returns:
            Dictionary containing reasoning results with confidence metrics
            
        Raises:
            LLMError: If reasoning operation fails
        """
        with TRACER.start_as_current_span("llm_reason_documents") as span:
            try:
                # Set span attributes
                span.set_attribute("query_length", len(query))
                span.set_attribute("document_count", len(documents))
                
                # Generate cache key
                cache_key = f"reason:{query}:{':'.join(documents)}"
                
                # Check cache
                if cache_key in self._cache:
                    LOGGER.debug("Cache hit for reasoning query")
                    return self._cache[cache_key]
                
                # Validate inputs
                if not query or not documents:
                    raise LLMError(
                        message="Invalid input for reasoning",
                        error_code=ErrorCode.VALIDATION_ERROR
                    )
                
                # Check token limits
                self._validate_token_limits(documents, 'gpt-4')
                
                # Apply retry strategy
                for attempt in range(MAX_RETRIES):
                    try:
                        result = await self._client.async_reason(
                            query=query,
                            documents=documents,
                            options=options or {}
                        )
                        
                        # Cache successful result
                        self._cache[cache_key] = result
                        
                        # Record metrics
                        span.set_attribute("success", True)
                        span.set_attribute("retry_count", attempt)
                        
                        return result
                        
                    except Exception as e:
                        if attempt == MAX_RETRIES - 1:
                            raise
                        await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                
            except Exception as e:
                LOGGER.error(f"Document reasoning failed: {e}", exc_info=True)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise LLMError(
                    message="Document reasoning failed",
                    error_code=ErrorCode.LLM_ERROR,
                    details={"error": str(e)}
                )

    async def async_select_documents(
        self,
        query: str,
        candidates: List[str],
        options: Optional[Dict] = None
    ) -> List[str]:
        """
        Select most relevant documents for query using LLM with caching and telemetry.
        
        Args:
            query: Selection query
            candidates: List of candidate documents
            options: Optional configuration parameters
            
        Returns:
            List of selected relevant documents with confidence scores
            
        Raises:
            LLMError: If selection operation fails
        """
        with TRACER.start_as_current_span("llm_select_documents") as span:
            try:
                # Set span attributes
                span.set_attribute("query_length", len(query))
                span.set_attribute("candidate_count", len(candidates))
                
                # Generate cache key
                cache_key = f"select:{query}:{':'.join(candidates)}"
                
                # Check cache
                if cache_key in self._cache:
                    LOGGER.debug("Cache hit for document selection")
                    return self._cache[cache_key]
                
                # Validate inputs
                if not query or not candidates:
                    return []
                
                # Check token limits
                self._validate_token_limits(candidates, 'gpt-4')
                
                # Apply retry strategy
                for attempt in range(MAX_RETRIES):
                    try:
                        selected = await self._client.async_select(
                            query=query,
                            candidates=candidates,
                            options=options or {}
                        )
                        
                        # Cache successful result
                        self._cache[cache_key] = selected
                        
                        # Record metrics
                        span.set_attribute("success", True)
                        span.set_attribute("retry_count", attempt)
                        span.set_attribute("selected_count", len(selected))
                        
                        return selected
                        
                    except Exception as e:
                        if attempt == MAX_RETRIES - 1:
                            raise
                        await asyncio.sleep(RETRY_DELAY * (2 ** attempt))
                
            except Exception as e:
                LOGGER.error(f"Document selection failed: {e}", exc_info=True)
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                raise LLMError(
                    message="Document selection failed",
                    error_code=ErrorCode.LLM_ERROR,
                    details={"error": str(e)}
                )

    def _validate_token_limits(self, documents: List[str], model_type: str) -> bool:
        """
        Validate token counts against model-specific limits with detailed error handling.
        
        Args:
            documents: List of documents to validate
            model_type: Model type for limit checking
            
        Returns:
            True if within limits
            
        Raises:
            LLMError: If token limits are exceeded
        """
        try:
            total_tokens = sum(get_token_count(doc) for doc in documents)
            model_limit = self._model_limits.get(model_type, self._model_limits['gpt-4'])
            
            # Log warning if approaching limit
            if total_tokens > (model_limit * 0.8):
                LOGGER.warning(
                    "Approaching token limit",
                    extra={
                        "total_tokens": total_tokens,
                        "model_limit": model_limit,
                        "usage_percentage": (total_tokens / model_limit) * 100
                    }
                )
            
            # Check against limit
            if total_tokens > model_limit:
                raise LLMError(
                    message=f"Combined documents exceed {model_type} token limit",
                    error_code=ErrorCode.LLM_ERROR,
                    details={
                        "total_tokens": total_tokens,
                        "model_limit": model_limit,
                        "document_count": len(documents)
                    }
                )
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Token validation failed: {e}", exc_info=True)
            raise LLMError(
                message="Token validation failed",
                error_code=ErrorCode.LLM_ERROR,
                details={"error": str(e)}
            )