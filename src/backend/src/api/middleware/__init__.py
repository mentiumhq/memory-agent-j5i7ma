"""
Initializes and exports FastAPI middleware components for authentication, error handling,
logging, and rate limiting. This module serves as the central point for middleware 
configuration and management in the Memory Agent API.

Version: 1.0.0
"""

from .auth import AuthMiddleware
from .error_handler import ErrorHandlerMiddleware
from .logging import LoggingMiddleware
from .rate_limiter import RateLimitMiddleware

# Export middleware components for API configuration
__all__ = [
    "AuthMiddleware",
    "ErrorHandlerMiddleware", 
    "LoggingMiddleware",
    "RateLimitMiddleware"
]