"""
FastAPI middleware for standardized error handling across the Memory Agent API.
Implements comprehensive error handling with proper logging, sanitization, and monitoring.

Version: 1.0.0
External Dependencies:
- fastapi==0.100+: FastAPI framework and HTTP components
- pydantic==2.0+: Data validation
"""

import uuid
from typing import Dict, Any, Callable, Union
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from ...core.errors import MemoryAgentError, ErrorCode
from ...config.logging import get_logger

# Initialize logger with proper context
logger = get_logger(__name__)

def format_validation_error(exc: Union[RequestValidationError, ValidationError]) -> Dict[str, Any]:
    """
    Format validation errors into a standardized and sanitized response format.
    
    Args:
        exc: Validation exception from FastAPI or Pydantic
        
    Returns:
        Dict containing sanitized error details with proper structure
    """
    # Extract error details
    error_details = []
    for error in exc.errors():
        # Create sanitized error message
        field_path = " -> ".join(str(loc) for loc in error.get("loc", []))
        error_msg = error.get("msg", "Invalid value")
        error_type = error.get("type", "validation_error")
        
        # Sanitize error details to prevent information disclosure
        sanitized_error = {
            "field": field_path,
            "message": error_msg,
            "type": error_type
        }
        error_details.append(sanitized_error)
    
    # Create standardized error response
    return {
        "error": {
            "code": ErrorCode.VALIDATION_ERROR.value,
            "message": "Request validation failed",
            "details": {
                "validation_errors": error_details
            },
            "correlation_id": str(uuid.uuid4())
        }
    }

class ErrorHandlerMiddleware:
    """
    Middleware for catching and handling all API errors with proper logging and sanitization.
    Ensures consistent error responses while preventing sensitive information disclosure.
    """
    
    def __init__(self, app: Callable) -> None:
        """
        Initialize the error handler middleware.
        
        Args:
            app: ASGI application instance
        """
        self.app = app
        self.logger = logger
    
    async def __call__(self, request: Request, call_next: Callable) -> JSONResponse:
        """
        Process requests and handle any errors with proper logging and sanitization.
        
        Args:
            request: FastAPI request instance
            call_next: Next middleware in chain
            
        Returns:
            JSONResponse with properly formatted and sanitized error details
        """
        # Generate correlation ID for request tracking
        correlation_id = str(uuid.uuid4())
        
        try:
            # Log incoming request with context
            self.logger.info(
                "Processing request",
                extra={
                    "correlation_id": correlation_id,
                    "method": request.method,
                    "url": str(request.url),
                    "client_host": request.client.host if request.client else None
                }
            )
            
            # Process request normally
            response = await call_next(request)
            return response
            
        except MemoryAgentError as exc:
            # Handle known application errors
            self.logger.error(
                "Application error occurred",
                extra={
                    "correlation_id": correlation_id,
                    "error_code": exc.error_code.value,
                    "error_message": exc.message
                }
            )
            return JSONResponse(
                status_code=400,
                content=exc.to_dict(),
                headers={"X-Correlation-ID": correlation_id}
            )
            
        except (RequestValidationError, ValidationError) as exc:
            # Handle validation errors
            self.logger.warning(
                "Validation error occurred",
                extra={
                    "correlation_id": correlation_id,
                    "error_details": str(exc)
                }
            )
            return JSONResponse(
                status_code=422,
                content=format_validation_error(exc),
                headers={"X-Correlation-ID": correlation_id}
            )
            
        except HTTPException as exc:
            # Handle HTTP exceptions
            self.logger.error(
                "HTTP error occurred",
                extra={
                    "correlation_id": correlation_id,
                    "status_code": exc.status_code,
                    "error_detail": str(exc.detail)
                }
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": exc.status_code,
                        "message": str(exc.detail),
                        "correlation_id": correlation_id
                    }
                },
                headers={"X-Correlation-ID": correlation_id}
            )
            
        except Exception as exc:
            # Handle unexpected errors
            self.logger.exception(
                "Unexpected error occurred",
                extra={
                    "correlation_id": correlation_id,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)
                }
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": ErrorCode.UNKNOWN_ERROR.value,
                        "message": "An unexpected error occurred",
                        "correlation_id": correlation_id
                    }
                },
                headers={"X-Correlation-ID": correlation_id}
            )