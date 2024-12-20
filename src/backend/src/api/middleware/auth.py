"""
FastAPI middleware implementation for JWT-based authentication and role-based access control.
Provides secure request authentication with comprehensive error handling and audit logging.

Version: 1.0.0
External Dependencies:
- fastapi==0.100.0: FastAPI framework and security utilities
"""

import logging
from typing import Dict, Optional
import uuid
from datetime import datetime, timezone

from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer
import logging

from core.auth import verify_token, check_permissions
from core.errors import SecurityError, ErrorCode

# Initialize bearer token scheme with JWT format
BEARER_SCHEME = HTTPBearer(auto_error=True, bearer_format='JWT')

# Define public endpoints that bypass authentication
PUBLIC_ENDPOINTS = ['/api/v1/health', '/api/v1/metrics']

# Security configuration
MAX_TOKEN_AGE = 3600  # Maximum token age in seconds
MAX_AUTH_FAILURES = 5  # Maximum authentication failures before rate limiting

class AuthMiddleware:
    """
    FastAPI middleware for JWT authentication and authorization with enhanced security controls.
    Implements comprehensive request authentication, permission checking, and security logging.
    """

    def __init__(self, app):
        """
        Initialize authentication middleware with security controls.

        Args:
            app: FastAPI application instance
        """
        self.app = app
        self._failure_counts: Dict[str, int] = {}  # Track authentication failures by IP
        self._permission_cache: Dict[str, str] = {}  # Cache endpoint permissions
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

    async def authenticate(self, request: Request) -> Dict:
        """
        Authenticate and authorize API requests with comprehensive security checks.

        Args:
            request: FastAPI request object

        Returns:
            Dict: Validated token payload

        Raises:
            HTTPException: For authentication/authorization failures
        """
        try:
            # Generate request correlation ID
            correlation_id = str(uuid.uuid4())
            request.state.correlation_id = correlation_id

            # Check if endpoint is public
            if request.url.path in PUBLIC_ENDPOINTS:
                return {}

            # Get client IP for rate limiting
            client_ip = request.client.host
            if self.track_auth_failure(client_ip):
                raise SecurityError(
                    "Too many authentication failures",
                    ErrorCode.RATE_LIMIT_ERROR,
                    {"source": client_ip}
                )

            # Extract and validate token
            token = get_token_from_request(request)
            if not token:
                raise SecurityError(
                    "Missing authentication token",
                    ErrorCode.AUTHENTICATION_ERROR
                )

            # Verify JWT token
            try:
                token_payload = verify_token(token)
            except SecurityError as e:
                if e.error_code == ErrorCode.TOKEN_EXPIRED:
                    raise SecurityError(
                        "Token has expired",
                        ErrorCode.TOKEN_EXPIRED
                    )
                raise SecurityError(
                    "Invalid authentication token",
                    ErrorCode.INVALID_TOKEN
                )

            # Check token age
            token_age = (datetime.now(timezone.utc) - token_payload.exp).total_seconds()
            if token_age > MAX_TOKEN_AGE:
                raise SecurityError(
                    "Token exceeds maximum age",
                    ErrorCode.TOKEN_EXPIRED
                )

            # Get required permission for endpoint
            required_permission = get_endpoint_permission(request.url.path)
            
            # Check role permissions
            if not check_permissions(token_payload.role, required_permission):
                raise SecurityError(
                    "Insufficient permissions",
                    ErrorCode.AUTHORIZATION_ERROR,
                    {"role": token_payload.role, "required": required_permission}
                )

            # Store token payload in request state
            request.state.token_payload = token_payload

            # Log successful authentication
            self.logger.info(
                f"Authentication successful: user={token_payload.sub} "
                f"role={token_payload.role} correlation_id={correlation_id}"
            )

            return token_payload

        except SecurityError as e:
            # Log security error
            self.logger.warning(
                f"Authentication failed: code={e.error_code.value} "
                f"message={e.message} correlation_id={correlation_id}",
                extra={"details": e.details}
            )
            raise HTTPException(
                status_code=401,
                detail=e.to_dict()
            )
        except Exception as e:
            # Log unexpected error
            self.logger.error(
                f"Unexpected authentication error: {str(e)} "
                f"correlation_id={correlation_id}"
            )
            raise HTTPException(
                status_code=500,
                detail={"error": "Internal server error"}
            )

    def track_auth_failure(self, client_ip: str) -> bool:
        """
        Track authentication failures for rate limiting.

        Args:
            client_ip: Client IP address

        Returns:
            bool: True if rate limit exceeded
        """
        if client_ip in self._failure_counts:
            self._failure_counts[client_ip] += 1
        else:
            self._failure_counts[client_ip] = 1

        if self._failure_counts[client_ip] > MAX_AUTH_FAILURES:
            self.logger.warning(
                f"Rate limit exceeded for IP: {client_ip}",
                extra={"failure_count": self._failure_counts[client_ip]}
            )
            return True
        return False


def get_token_from_request(request: Request) -> Optional[str]:
    """
    Extract and validate JWT token from request authorization header.

    Args:
        request: FastAPI request object

    Returns:
        Optional[str]: JWT token if valid, None otherwise

    Raises:
        SecurityError: If token format is invalid
    """
    try:
        auth = request.headers.get("Authorization")
        if not auth:
            return None

        scheme, token = auth.split()
        if scheme.lower() != "bearer":
            raise SecurityError(
                "Invalid authentication scheme",
                ErrorCode.AUTHENTICATION_ERROR
            )

        if not token or len(token) > 2048:  # Prevent token length attacks
            raise SecurityError(
                "Invalid token format",
                ErrorCode.AUTHENTICATION_ERROR
            )

        return token

    except ValueError:
        raise SecurityError(
            "Invalid authorization header format",
            ErrorCode.AUTHENTICATION_ERROR
        )


def get_endpoint_permission(path: str) -> str:
    """
    Get required permission for API endpoint with caching.

    Args:
        path: API endpoint path

    Returns:
        str: Required permission string
    """
    # Check cache first
    if path in AuthMiddleware._permission_cache:
        return AuthMiddleware._permission_cache[path]

    # Parse endpoint path
    parts = path.strip('/').split('/')
    if len(parts) < 3:
        return 'default'

    # Map endpoint to permission
    operation = parts[2]  # Assuming format: /api/v1/{operation}/...
    permission_mapping = {
        'store': 'store',
        'retrieve': 'retrieve',
        'search': 'search',
        'admin': 'admin'
    }

    permission = permission_mapping.get(operation, 'default')
    
    # Cache permission mapping
    AuthMiddleware._permission_cache[path] = permission
    
    return permission