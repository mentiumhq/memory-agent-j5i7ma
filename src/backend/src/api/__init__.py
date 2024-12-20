"""
API package initialization module that exports the main FastAPI application instance 
and router configuration. Serves as the entry point for the Memory Agent's API layer,
providing gRPC/HTTP2 protocol support and comprehensive middleware stack.

Version: 1.0.0
External Dependencies:
- fastapi==0.100.0+: API framework
- starlette==0.27.0+: ASGI toolkit
- opentelemetry-api==1.20.0: Distributed tracing
"""

from .server import app, create_app
from .router import api_router, configure_routes

# Initialize FastAPI application with configured middleware stack
app = create_app()

# Configure API routes with versioning and security
configure_routes(app)

# Export public interface
__all__ = [
    'app',  # Main FastAPI application instance
    'create_app',  # Factory function for creating FastAPI instances
    'api_router',  # Configured API router with versioned endpoints
    'configure_routes'  # Router configuration function
]