"""
FastAPI server configuration and initialization module implementing a production-ready
API server with comprehensive middleware stack, security controls, monitoring capabilities,
and gRPC/HTTP2 support for the Memory Agent system.

Version: 1.0.0
External Dependencies:
- fastapi==0.100.0+: API framework
- starlette==0.27.0+: ASGI toolkit
- uvicorn==0.22.0+: ASGI server
"""

import logging
from typing import Dict, Any
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from api.router import document_router, health_router
from api.middleware.auth import AuthMiddleware
from core.telemetry import TelemetryMiddleware, create_tracer
from core.errors import SecurityError, ErrorCode
from config.settings import settings
from config.logging import get_logger

# Initialize logging and tracing
LOGGER = get_logger(__name__)
TRACER = create_tracer('api_server')

# Security configuration
CORS_ORIGINS = ["*"]  # Customize based on environment
CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_HEADERS = ["*"]
TRUSTED_HOSTS = ["*"]  # Customize based on environment

# Performance configuration
COMPRESSION_MINIMUM_SIZE = 1000  # Minimum size in bytes for compression
RATE_LIMIT = "100/minute"  # Default rate limit

def create_app() -> FastAPI:
    """
    Create and configure FastAPI application with comprehensive middleware stack.
    
    Returns:
        FastAPI: Configured FastAPI application instance
    """
    # Initialize FastAPI with project info and documentation URLs
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json"
    )

    # Configure middleware stack
    configure_middleware(app)

    # Include API routers
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

    # Configure error handlers
    @app.exception_handler(SecurityError)
    async def security_error_handler(request: Request, exc: SecurityError) -> Response:
        LOGGER.error(
            f"Security error: {exc.message}",
            extra={
                "error_code": exc.error_code.value,
                "path": request.url.path,
                "details": exc.details
            }
        )
        return Response(
            content=exc.to_dict(),
            status_code=401,
            media_type="application/json"
        )

    # Configure shutdown handlers
    @app.on_event("shutdown")
    async def shutdown_event():
        LOGGER.info("Shutting down API server")
        await handle_shutdown(app)

    return app

def configure_middleware(app: FastAPI) -> None:
    """
    Configure comprehensive middleware stack with security and monitoring.
    
    Args:
        app: FastAPI application instance
    """
    # Security middleware
    app.add_middleware(AuthMiddleware)
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=TRUSTED_HOSTS
    )
    if settings.ENVIRONMENT == "production":
        app.add_middleware(HTTPSRedirectMiddleware)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=CORS_METHODS,
        allow_headers=CORS_HEADERS,
        expose_headers=["X-Request-ID", "X-Correlation-ID"]
    )

    # Performance middleware
    app.add_middleware(
        GZipMiddleware,
        minimum_size=COMPRESSION_MINIMUM_SIZE
    )

    # Rate limiting
    app.add_middleware(
        RateLimiter,
        key_func=lambda r: r.client.host,
        rate=RATE_LIMIT
    )

    # Telemetry middleware
    app.add_middleware(TelemetryMiddleware)

    # Add security headers
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # Add request ID
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(TRACER.get_current_span().context.trace_id)
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

async def handle_shutdown(app: FastAPI) -> None:
    """
    Handle graceful shutdown of FastAPI application.
    
    Args:
        app: FastAPI application instance
    """
    # Complete in-flight requests
    await app.state.limiter.close()
    
    # Close database connections
    if hasattr(app.state, "db"):
        await app.state.db.close()
    
    # Close cache connections
    if hasattr(app.state, "cache"):
        await app.state.cache.close()
    
    # Stop monitoring
    if hasattr(app.state, "metrics"):
        await app.state.metrics.shutdown()

# Create global application instance
app = create_app()