"""
Main FastAPI router configuration implementing enterprise-grade API routing with
comprehensive middleware integration, security controls, and observability features.

Version:
- fastapi==0.100.0+
- slowapi==0.1.8
- opentelemetry-api==1.20.0
"""

import logging
from typing import List, Dict, Any
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .endpoints.documents import router as document_router
from .endpoints.health import router as health_router
from core.telemetry import TelemetryMiddleware
from core.security import SecurityManager
from core.errors import SecurityError, ErrorCode
from config.settings import settings
from config.logging import get_logger

# Initialize logging
LOGGER = get_logger(__name__)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize security manager
security_manager = SecurityManager(
    encryption_client=None,  # Will be injected by app startup
    kms_client=None  # Will be injected by app startup
)

# Configure CORS settings
CORS_ORIGINS = ["*"]  # Customize based on environment
CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_HEADERS = ["*"]

# Configure compression
COMPRESSION_MINIMUM_SIZE = 1000  # Minimum size in bytes for compression

def configure_routes(app: FastAPI) -> None:
    """
    Configure API routes with comprehensive middleware stack and security controls.

    Args:
        app: FastAPI application instance
    """
    # Configure rate limiting middleware
    app.state.limiter = limiter
    app.add_middleware(
        limiter.middleware,
        config={
            "default_limits": [f"{settings.RATE_LIMIT_PER_MINUTE}/minute"]
        }
    )

    # Configure CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=CORS_METHODS,
        allow_headers=CORS_HEADERS,
        expose_headers=["X-Request-ID", "X-Correlation-ID"]
    )

    # Configure compression middleware
    app.add_middleware(
        GZipMiddleware,
        minimum_size=COMPRESSION_MINIMUM_SIZE
    )

    # Configure telemetry middleware
    app.add_middleware(TelemetryMiddleware)

    # Configure security middleware
    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        try:
            # Extract and validate JWT token
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                token_payload = security_manager.authenticate_request(token)
                request.state.user = token_payload
            
            response = await call_next(request)
            return response

        except SecurityError as e:
            LOGGER.error(
                "Security middleware error",
                extra={
                    "error": str(e),
                    "error_code": e.error_code,
                    "path": request.url.path
                }
            )
            return Response(
                content={"error": str(e)},
                status_code=401,
                media_type="application/json"
            )

    # Configure error handling middleware
    @app.middleware("http")
    async def error_handler(request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except Exception as e:
            LOGGER.error(
                "Unhandled error",
                exc_info=True,
                extra={"path": request.url.path}
            )
            return Response(
                content={"error": "Internal server error"},
                status_code=500,
                media_type="application/json"
            )

    # Include routers with versioning
    app.include_router(
        document_router,
        prefix="/api/v1/documents",
        tags=["documents"]
    )
    app.include_router(
        health_router,
        prefix="/health",
        tags=["health"]
    )

    # Configure OpenTelemetry instrumentation
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health/live",
        trace_all_requests=True
    )

def configure_middleware(app: FastAPI) -> None:
    """
    Set up middleware stack with proper ordering and configuration.

    Args:
        app: FastAPI application instance
    """
    # Add request ID generation
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # Add security headers
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Add response caching control
    @app.middleware("http")
    async def add_cache_control(request: Request, call_next):
        response = await call_next(request)
        if request.method in ["GET", "HEAD"]:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        return response

    # Add timeout handling
    @app.middleware("http")
    async def timeout_handler(request: Request, call_next):
        try:
            response = await asyncio.wait_for(
                call_next(request),
                timeout=30.0
            )
            return response
        except asyncio.TimeoutError:
            return Response(
                content={"error": "Request timeout"},
                status_code=504,
                media_type="application/json"
            )

# Export configured router
api_router = FastAPI(
    title="Memory Agent API",
    version=settings.VERSION,
    docs_url="/api/docs",
    redoc_url="/api/redoc"
)

# Configure routes and middleware
configure_middleware(api_router)
configure_routes(api_router)