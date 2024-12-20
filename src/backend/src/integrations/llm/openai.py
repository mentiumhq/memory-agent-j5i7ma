"""
OpenAI API integration module for the Memory Agent system.
Provides LLM capabilities for document reasoning and retrieval with comprehensive
error handling, telemetry, and token management.

Version: 1.0.0
External Dependencies:
- openai==1.0.0: OpenAI API client
- tiktoken==0.5.0: Token counting and management
"""

import asyncio
from typing import List, Dict, Optional, Union, Any
import tiktoken
from openai import AsyncClient, APIError
from core.errors import LLMError, ErrorCode
from config.settings import Settings
from core.telemetry import create_tracer
from config.logging import get_logger

# Initialize logging and telemetry
LOGGER = get_logger(__name__)
TRACER = create_tracer('openai')

# Constants
DEFAULT_MODEL = 'gpt-4'
MAX_RETRIES = 3
RETRY_DELAY = 1.0
DEFAULT_TIMEOUT = 30.0
TOKEN_LIMITS = {
    'gpt-3.5-turbo': 16384,
    'gpt-4': 32768
}

async def initialize_client(settings: Settings) -> AsyncClient:
    """
    Initialize and configure the OpenAI API client with retry and timeout settings.
    
    Args:
        settings: Application settings instance
        
    Returns:
        Configured OpenAI client instance
        
    Raises:
        LLMError: If client initialization fails
    """
    try:
        client = AsyncClient(
            api_key=settings.OPENAI_API_KEY,
            timeout=settings.OPENAI_TIMEOUT or DEFAULT_TIMEOUT,
            max_retries=settings.OPENAI_MAX_RETRIES or MAX_RETRIES
        )
        # Validate client connection
        await client.models.list()
        return client
    except Exception as e:
        LOGGER.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
        raise LLMError(
            message="Failed to initialize OpenAI client",
            error_code=ErrorCode.LLM_ERROR,
            details={"error": str(e)}
        )

def get_token_count(text: str, model: str = DEFAULT_MODEL) -> int:
    """
    Calculate and validate token count for input text.
    
    Args:
        text: Input text to count tokens
        model: Model name for token counting
        
    Returns:
        Number of tokens in text
        
    Raises:
        LLMError: If token counting fails or exceeds limits
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        token_count = len(encoding.encode(text))
        
        # Validate against model limits
        if token_count > TOKEN_LIMITS.get(model, TOKEN_LIMITS[DEFAULT_MODEL]):
            raise LLMError(
                message=f"Text exceeds token limit for model {model}",
                error_code=ErrorCode.LLM_ERROR,
                details={
                    "token_count": token_count,
                    "model_limit": TOKEN_LIMITS.get(model)
                }
            )
        
        return token_count
    except Exception as e:
        LOGGER.error(f"Token counting failed: {e}", exc_info=True)
        raise LLMError(
            message="Failed to count tokens",
            error_code=ErrorCode.LLM_ERROR,
            details={"error": str(e)}
        )

class OpenAIClient:
    """
    OpenAI API client wrapper with comprehensive error handling, telemetry,
    and token management.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize OpenAI client wrapper with configuration and monitoring.
        
        Args:
            settings: Application settings instance
        """
        self._api_key = settings.OPENAI_API_KEY
        self._model = DEFAULT_MODEL
        self._timeout = settings.OPENAI_TIMEOUT or DEFAULT_TIMEOUT
        self._max_retries = settings.OPENAI_MAX_RETRIES or MAX_RETRIES
        self._token_limits = TOKEN_LIMITS.copy()
        self._client = None

    async def _ensure_client(self):
        """Ensure client is initialized."""
        if not self._client:
            self._client = await initialize_client(Settings())

    async def async_reason(
        self,
        query: str,
        documents: List[str],
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Perform LLM reasoning on documents with telemetry and error handling.
        
        Args:
            query: Reasoning query
            documents: List of documents to reason about
            options: Optional configuration parameters
            
        Returns:
            Dictionary containing reasoning results and confidence scores
            
        Raises:
            LLMError: If reasoning operation fails
        """
        with TRACER.start_as_current_span("openai_reason") as span:
            try:
                await self._ensure_client()
                
                # Validate input tokens
                total_tokens = sum(get_token_count(doc) for doc in documents)
                span.set_attribute("input_tokens", total_tokens)
                
                # Prepare prompt
                prompt = self._prepare_reasoning_prompt(query, documents)
                
                # Execute API call with retries
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=options.get('temperature', 0.0),
                    max_tokens=options.get('max_tokens', 1000),
                    timeout=self._timeout
                )
                
                result = {
                    "reasoning": response.choices[0].message.content,
                    "confidence": response.choices[0].finish_reason == "stop",
                    "model": self._model,
                    "tokens_used": response.usage.total_tokens
                }
                
                span.set_attribute("output_tokens", response.usage.total_tokens)
                return result
                
            except APIError as e:
                await self._handle_error(e, "reasoning")
            except Exception as e:
                LOGGER.error(f"Reasoning failed: {e}", exc_info=True)
                raise LLMError(
                    message="Reasoning operation failed",
                    error_code=ErrorCode.LLM_ERROR,
                    details={"error": str(e)}
                )

    async def async_select(
        self,
        query: str,
        candidates: List[str],
        options: Optional[Dict] = None
    ) -> List[str]:
        """
        Select relevant documents using LLM with validation and monitoring.
        
        Args:
            query: Selection query
            candidates: List of candidate documents
            options: Optional configuration parameters
            
        Returns:
            List of selected relevant documents with rankings
            
        Raises:
            LLMError: If selection operation fails
        """
        with TRACER.start_as_current_span("openai_select") as span:
            try:
                await self._ensure_client()
                
                # Validate candidates
                if not candidates:
                    return []
                    
                # Check token limits
                total_tokens = sum(get_token_count(doc) for doc in candidates)
                span.set_attribute("input_tokens", total_tokens)
                
                # Prepare selection prompt
                prompt = self._prepare_selection_prompt(query, candidates)
                
                # Execute API call
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=options.get('temperature', 0.0),
                    max_tokens=options.get('max_tokens', 500),
                    timeout=self._timeout
                )
                
                # Parse selected documents
                selected = self._parse_selection_response(
                    response.choices[0].message.content,
                    candidates
                )
                
                span.set_attribute("output_tokens", response.usage.total_tokens)
                span.set_attribute("selected_count", len(selected))
                
                return selected
                
            except APIError as e:
                await self._handle_error(e, "selection")
            except Exception as e:
                LOGGER.error(f"Document selection failed: {e}", exc_info=True)
                raise LLMError(
                    message="Document selection failed",
                    error_code=ErrorCode.LLM_ERROR,
                    details={"error": str(e)}
                )

    async def _handle_error(self, error: APIError, operation: str) -> None:
        """
        Handle OpenAI API errors with comprehensive error mapping.
        
        Args:
            error: OpenAI API error
            operation: Operation type for context
            
        Raises:
            LLMError: Mapped error with context
        """
        LOGGER.error(f"OpenAI {operation} error: {error}", exc_info=True)
        
        error_mapping = {
            "rate_limit": ErrorCode.RATE_LIMIT_ERROR,
            "invalid_request": ErrorCode.LLM_ERROR,
            "authentication": ErrorCode.AUTHENTICATION_ERROR
        }
        
        error_code = error_mapping.get(
            error.type,
            ErrorCode.LLM_ERROR
        )
        
        raise LLMError(
            message=f"OpenAI {operation} failed: {error.message}",
            error_code=error_code,
            details={
                "operation": operation,
                "error_type": error.type,
                "error_code": error.code
            }
        )

    def _prepare_reasoning_prompt(self, query: str, documents: List[str]) -> str:
        """Prepare optimized prompt for reasoning task."""
        return f"""Given the following documents, answer the query:
Documents:
{chr(10).join(f'[{i+1}] {doc}' for i, doc in enumerate(documents))}

Query: {query}

Provide a detailed reasoning based on the documents above."""

    def _prepare_selection_prompt(self, query: str, candidates: List[str]) -> str:
        """Prepare optimized prompt for document selection."""
        return f"""Select the most relevant documents for the query:
Query: {query}

Documents:
{chr(10).join(f'[{i+1}] {doc}' for i, doc in enumerate(candidates))}

Return only the numbers of relevant documents in order of relevance."""

    def _parse_selection_response(
        self,
        response: str,
        candidates: List[str]
    ) -> List[str]:
        """Parse and validate selection response."""
        try:
            # Extract document numbers from response
            numbers = [
                int(n.strip('[]., ')) - 1
                for n in response.split()
                if n.strip('[]., ').isdigit()
            ]
            
            # Validate and return selected documents
            return [
                candidates[i] for i in numbers
                if 0 <= i < len(candidates)
            ]
        except Exception as e:
            LOGGER.error(f"Failed to parse selection response: {e}", exc_info=True)
            return []