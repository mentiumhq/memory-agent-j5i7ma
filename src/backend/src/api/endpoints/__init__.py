"""
Entry point for Memory Agent API endpoints that exports all endpoint routers and combines them
into a unified API interface. Provides centralized access to document operations and health check
endpoints with comprehensive security, monitoring, and validation capabilities.

Version:
- fastapi==0.100.0+
- opentelemetry-api==1.20.0
- circuitbreaker==1.4.0
"""

from fastapi import FastAPI, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from opentelemetry import trace
from circuitbreaker import circuit
from typing import Tuple

from .documents import router as document_router
from .health import router as health_router
from core.telemetry import create_tracer, TelemetryMiddleware
from core.security import SecurityManager, create_security_manager
from core.errors import SecurityError, ErrorCode
from config.settings import Settings

# Initialize tracer and security components
TRACER = create_tracer('api_endpoints')
settings = Settings()
security_manager = create_security_manager(settings.KMS_KEY_ID)
security = HTTPBearer()

# Circuit breaker configuration
FAILURE_THRESHOLD = 5
RECOVERY_TIMEOUT = 60

def initialize_routers() -> Tuple[FastAPI, FastAPI]:
    """
    Initialize and configure all API routers with security, validation, and monitoring.
    Implements comprehensive request validation, authentication, and telemetry.

    Returns:
        Tuple containing configured document_router and health_router
    """
    with TRACER.start_as_current_span("initialize_routers") as span:
        try:
            # Configure security middleware for document router
            @document_router.middleware("http")
            @circuit(failure_threshold=FAILURE_THRESHOLD, recovery_timeout=RECOVERY_TIMEOUT)
            async def authenticate_requests(request: Request, call_next):
                """Authenticate and authorize API requests."""
                try:
                    # Skip auth for OPTIONS requests
                    if request.method == "OPTIONS":
                        return await call_next(request)

                    # Get and validate token
                    credentials: HTTPAuthorizationCredentials = await security(request)
                    if not credentials:
                        raise SecurityError(
                            "Missing authentication credentials",
                            ErrorCode.AUTHENTICATION_ERROR
                        )

                    # Authenticate token
                    token_payload = security_manager.authenticate_request(
                        credentials.credentials
                    )

                    # Authorize operation based on path
                    operation = _get_operation_from_path(request.url.path)
                    if not security_manager.authorize_operation(
                        token_payload.role,
                        operation
                    ):
                        raise SecurityError(
                            "Unauthorized operation",
                            ErrorCode.AUTHORIZATION_ERROR
                        )

                    # Add security context to request state
                    request.state.user = token_payload

                    return await call_next(request)

                except SecurityError as e:
                    return Response(
                        content=e.to_dict(),
                        status_code=401 if e.error_code == ErrorCode.AUTHENTICATION_ERROR else 403,
                        media_type="application/json"
                    )

            # Add telemetry middleware
            document_router.middleware("http")(TelemetryMiddleware)
            health_router.middleware("http")(TelemetryMiddleware)

            # Configure CORS
            document_router.add_middleware(
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"]
            )

            # Add error handlers
            @document_router.exception_handler(SecurityError)
            async def security_error_handler(request: Request, exc: SecurityError):
                """Handle security-related errors."""
                return Response(
                    content=exc.to_dict(),
                    status_code=401 if exc.error_code == ErrorCode.AUTHENTICATION_ERROR else 403,
                    media_type="application/json"
                )

            span.set_attribute("routers_initialized", True)
            return document_router, health_router

        except Exception as e:
            span.record_exception(e)
            raise

def _get_operation_from_path(path: str) -> str:
    """Map API path to security operation name."""
    operations = {
        "/v1/documents/store": "store",
        "/v1/documents/retrieve": "retrieve",
        "/v1/documents/search": "search",
        "/v1/health": "health"
    }
    return operations.get(path, "unknown")

# Export configured routers
__all__ = [
    "document_router",
    "health_router",
    "initialize_routers"
]