"""
Enterprise-grade logging middleware for the Memory Agent service.
Provides comprehensive request/response logging with correlation tracking,
security monitoring, and OpenTelemetry integration.

External Dependencies:
- fastapi==0.100+: FastAPI middleware base classes
- starlette==0.27+: Base middleware functionality
- opentelemetry-api==1.20.0: Distributed tracing integration
"""

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4
from contextvars import ContextVar
from typing import Dict, Any, List, Optional
import time
import re
import json

from config.logging import get_logger
from core.telemetry import create_tracer

# Initialize structured logger
LOGGER = get_logger(__name__)

# Context variable for correlation ID tracking
correlation_id_context: ContextVar[str] = ContextVar('correlation_id', default='')

def get_correlation_id() -> str:
    """
    Retrieve the current correlation ID from context.
    
    Returns:
        str: Current correlation ID or empty string if not set
    """
    return correlation_id_context.get()

def set_correlation_id(correlation_id: str) -> None:
    """
    Set a new correlation ID in the current context.
    
    Args:
        correlation_id: Unique identifier for request correlation
    """
    correlation_id_context.set(correlation_id)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for comprehensive request/response logging with security 
    monitoring, audit trails, and telemetry integration.
    """

    def __init__(
        self,
        app: FastAPI,
        max_body_size: Optional[int] = 100_000,  # 100KB default
        sampling_rate: Optional[float] = 0.1  # 10% default sampling
    ):
        """
        Initialize logging middleware with security and telemetry configuration.
        
        Args:
            app: FastAPI application instance
            max_body_size: Maximum request body size to log
            sampling_rate: Request body sampling rate
        """
        super().__init__(app)
        self.logger = LOGGER
        self.tracer = create_tracer("api_logging")
        self.max_body_size = max_body_size
        self.sampling_rate = sampling_rate
        
        # Patterns for sensitive data detection
        self.sensitive_patterns = {
            'password': r'(?i)(password|passwd|pwd)[:=]\s*\S+',
            'token': r'(?i)(token|jwt|bearer)[:=]\s*\S+',
            'key': r'(?i)(api[-_]?key|secret[-_]?key)[:=]\s*\S+',
            'credential': r'(?i)(credential|auth)[:=]\s*\S+',
            'cookie': r'(?i)(session|cookie)[:=]\s*\S+'
        }

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """
        Process request with comprehensive logging and security monitoring.
        
        Args:
            request: FastAPI request instance
            call_next: Next middleware in chain
            
        Returns:
            Response: Processed response with correlation ID and telemetry data
        """
        # Generate correlation ID with timestamp
        correlation_id = f"{int(time.time())}-{str(uuid4())}"
        set_correlation_id(correlation_id)
        
        # Start request span
        with self.tracer.start_span("http_request") as span:
            start_time = time.time()
            
            # Log sanitized request details
            request_data = {
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "headers": self.sanitize_data(dict(request.headers)),
                "client_host": request.client.host if request.client else None,
                "correlation_id": correlation_id
            }
            
            # Sample and log request body if within limits
            try:
                if (
                    request.method in ["POST", "PUT", "PATCH"] and 
                    time.time() % (1/self.sampling_rate) < 1
                ):
                    body = await request.body()
                    if len(body) <= self.max_body_size:
                        try:
                            body_json = json.loads(body)
                            request_data["body"] = self.sanitize_data(body_json)
                        except json.JSONDecodeError:
                            request_data["body"] = "<non-JSON body>"
            except Exception as e:
                self.logger.warning(f"Failed to process request body: {e}")

            self.logger.info("Incoming request", extra=request_data)
            
            try:
                # Process request
                response = await call_next(request)
                duration = time.time() - start_time
                
                # Log response details
                response_data = {
                    "status_code": response.status_code,
                    "duration_ms": int(duration * 1000),
                    "correlation_id": correlation_id,
                    "headers": self.sanitize_data(dict(response.headers))
                }
                
                # Add security events if detected
                security_events = self.detect_security_events(request, response)
                if security_events:
                    response_data["security_events"] = security_events
                
                # Log response
                log_level = "error" if response.status_code >= 500 else "info"
                getattr(self.logger, log_level)("Request completed", extra=response_data)
                
                # Add correlation headers
                response.headers["X-Correlation-ID"] = correlation_id
                response.headers["X-Trace-ID"] = str(span.get_context().trace_id)
                
                return response
                
            except Exception as e:
                # Log error with full context
                self.logger.error(
                    "Request failed",
                    extra={
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "correlation_id": correlation_id,
                        "duration_ms": int((time.time() - start_time) * 1000)
                    },
                    exc_info=True
                )
                raise

    def sanitize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize sensitive information from log data.
        
        Args:
            data: Dictionary containing data to sanitize
            
        Returns:
            Dict: Sanitized data safe for logging
        """
        if not isinstance(data, dict):
            return data
            
        sanitized = {}
        for key, value in data.items():
            # Skip binary data
            if isinstance(value, bytes):
                sanitized[key] = "<binary data>"
                continue
                
            # Recursively sanitize nested dictionaries
            if isinstance(value, dict):
                sanitized[key] = self.sanitize_data(value)
                continue
                
            # Convert value to string for pattern matching
            str_value = str(value)
            
            # Check for sensitive patterns
            should_mask = False
            for pattern in self.sensitive_patterns.values():
                if re.search(pattern, f"{key}={str_value}"):
                    should_mask = True
                    break
                    
            sanitized[key] = "***MASKED***" if should_mask else value
            
        return sanitized

    def detect_security_events(self, request: Request, response: Response) -> List[Dict[str, Any]]:
        """
        Analyze request/response for security events.
        
        Args:
            request: FastAPI request instance
            response: FastAPI response instance
            
        Returns:
            List[Dict]: Detected security events
        """
        events = []
        
        # Check for authentication failures
        if response.status_code == 401:
            events.append({
                "type": "auth_failure",
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None
            })
            
        # Check for authorization failures
        if response.status_code == 403:
            events.append({
                "type": "authorization_failure",
                "path": request.url.path,
                "client_ip": request.client.host if request.client else None
            })
            
        # Check for potential security probes
        if request.url.path.lower().find("admin") >= 0 and response.status_code in [401, 403, 404]:
            events.append({
                "type": "potential_probe",
                "path": request.url.path,
                "method": request.method
            })
            
        # Check for unusual patterns
        headers = dict(request.headers)
        if "user-agent" not in headers or not headers["user-agent"]:
            events.append({
                "type": "missing_user_agent",
                "client_ip": request.client.host if request.client else None
            })
            
        return events
```

This implementation provides:

1. Comprehensive request/response logging with correlation tracking
2. Security event monitoring and audit trails
3. OpenTelemetry integration for distributed tracing
4. Sensitive data sanitization
5. Request body sampling
6. Performance metrics tracking
7. Error handling and logging
8. Security event detection

Key features:

- Uses structured JSON logging with CloudWatch integration
- Implements correlation ID tracking across requests
- Sanitizes sensitive data like passwords and tokens
- Integrates with OpenTelemetry for distributed tracing
- Monitors for security events and suspicious patterns
- Provides sampling for large request bodies
- Adds correlation and trace headers to responses
- Handles errors with full context logging

The middleware can be added to a FastAPI application like:

```python
app = FastAPI()
app.add_middleware(LoggingMiddleware)