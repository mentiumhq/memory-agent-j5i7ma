"""
Temporal workflow activities for LLM-based document operations.
Implements document reasoning and selection using OpenAI's GPT models with
comprehensive token management, error handling, and telemetry.

Version: 1.0.0
External Dependencies:
- temporalio==1.0.0: Temporal workflow SDK
- openai==1.0.0: OpenAI API client
"""

from typing import List, Dict, Optional
from temporalio import activity
from temporalio.activity import retry
from opentelemetry.trace import Span

from services.llm import LLMService
from integrations.llm.openai import OpenAIClient
from core.errors import LLMError, ErrorCode
from core.telemetry import create_tracer
from config.logging import get_logger

# Initialize logging and telemetry
LOGGER = get_logger(__name__)
TRACER = create_tracer("llm_activities")

# Default configuration
DEFAULT_OPTIONS = {
    "temperature": 0.7,
    "max_tokens": 1000,
    "model": "gpt-4"
}

# Retry configuration for activities
RETRY_CONFIG = {
    "attempts": 3,
    "initial_interval": 1.0,
    "backoff_coefficient": 2.0,
    "max_interval": 10.0
}

def trace_activity(func):
    """Decorator for activity tracing and monitoring."""
    async def wrapper(*args, **kwargs):
        with TRACER.start_as_current_span(
            name=f"activity.{func.__name__}",
            kind=Span.KIND_SERVER
        ) as span:
            try:
                # Record activity start
                LOGGER.info(
                    f"Starting activity {func.__name__}",
                    extra={
                        "activity": func.__name__,
                        "args_length": len(args),
                        "kwargs_keys": list(kwargs.keys())
                    }
                )
                
                # Execute activity
                result = await func(*args, **kwargs)
                
                # Record success metrics
                span.set_attribute("success", True)
                span.set_attribute("activity", func.__name__)
                
                return result
                
            except Exception as e:
                # Record error metrics
                span.set_attribute("success", False)
                span.set_attribute("error", str(e))
                LOGGER.error(
                    f"Activity {func.__name__} failed",
                    exc_info=True,
                    extra={"error": str(e)}
                )
                raise
    return wrapper

@activity.defn(name="reason_documents")
@retry(**RETRY_CONFIG)
@trace_activity
async def reason_documents(
    query: str,
    documents: List[str],
    options: Optional[Dict] = None
) -> Dict:
    """
    Temporal activity for performing LLM reasoning on documents.
    
    Args:
        query: Reasoning query
        documents: List of documents to reason about
        options: Optional configuration parameters
        
    Returns:
        Dictionary containing reasoning results with confidence scores
        
    Raises:
        LLMError: If reasoning operation fails
    """
    try:
        # Validate inputs
        if not query or not documents:
            raise LLMError(
                message="Invalid input for reasoning",
                error_code=ErrorCode.VALIDATION_ERROR,
                details={
                    "query_length": len(query) if query else 0,
                    "document_count": len(documents)
                }
            )
        
        # Initialize LLM service
        llm_service = LLMService(OpenAIClient(settings=Settings()))
        
        # Merge options with defaults
        merged_options = {**DEFAULT_OPTIONS, **(options or {})}
        
        # Log activity details
        LOGGER.info(
            "Executing document reasoning",
            extra={
                "query_length": len(query),
                "document_count": len(documents),
                "options": merged_options
            }
        )
        
        # Perform reasoning
        result = await llm_service.async_reason_documents(
            query=query,
            documents=documents,
            options=merged_options
        )
        
        # Log success
        LOGGER.info(
            "Document reasoning completed",
            extra={
                "token_usage": result.get("tokens_used", 0),
                "confidence": result.get("confidence", 0)
            }
        )
        
        return result
        
    except LLMError as e:
        LOGGER.error(
            "Document reasoning failed",
            exc_info=True,
            extra={"error": str(e)}
        )
        raise
    except Exception as e:
        LOGGER.error(
            "Unexpected error in document reasoning",
            exc_info=True,
            extra={"error": str(e)}
        )
        raise LLMError(
            message="Document reasoning failed",
            error_code=ErrorCode.LLM_ERROR,
            details={"error": str(e)}
        )

@activity.defn(name="select_documents")
@retry(**RETRY_CONFIG)
@trace_activity
async def select_documents(
    query: str,
    candidates: List[str],
    options: Optional[Dict] = None
) -> List[str]:
    """
    Temporal activity for selecting relevant documents using LLM.
    
    Args:
        query: Selection query
        candidates: List of candidate documents
        options: Optional configuration parameters
        
    Returns:
        List of selected relevant documents with confidence scores
        
    Raises:
        LLMError: If selection operation fails
    """
    try:
        # Validate inputs
        if not query or not candidates:
            return []
        
        # Initialize LLM service
        llm_service = LLMService(OpenAIClient(settings=Settings()))
        
        # Merge options with defaults
        merged_options = {**DEFAULT_OPTIONS, **(options or {})}
        
        # Log activity details
        LOGGER.info(
            "Executing document selection",
            extra={
                "query_length": len(query),
                "candidate_count": len(candidates),
                "options": merged_options
            }
        )
        
        # Perform selection
        selected = await llm_service.async_select_documents(
            query=query,
            candidates=candidates,
            options=merged_options
        )
        
        # Log success
        LOGGER.info(
            "Document selection completed",
            extra={
                "selected_count": len(selected),
                "total_candidates": len(candidates)
            }
        )
        
        return selected
        
    except LLMError as e:
        LOGGER.error(
            "Document selection failed",
            exc_info=True,
            extra={"error": str(e)}
        )
        raise
    except Exception as e:
        LOGGER.error(
            "Unexpected error in document selection",
            exc_info=True,
            extra={"error": str(e)}
        )
        raise LLMError(
            message="Document selection failed",
            error_code=ErrorCode.LLM_ERROR,
            details={"error": str(e)}
        )