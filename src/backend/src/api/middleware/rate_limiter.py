"""
Thread-safe FastAPI middleware implementing token bucket algorithm for rate limiting
with OpenTelemetry metrics integration.

External Dependencies:
- fastapi==0.100.0: FastAPI framework
- starlette==0.27.0: ASGI framework
- opentelemetry-api==1.20.0: Telemetry instrumentation

Version: 1.0.0
"""

from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
import asyncio
import time
from typing import Dict
import logging
from config.settings import Settings
from core.errors import ErrorCode, SecurityError
from core.telemetry import create_meter

# Initialize logger
LOGGER = logging.getLogger(__name__)

# Constants
BUCKET_CLEANUP_INTERVAL = 300  # 5 minutes in seconds

class RateLimiterMiddleware:
    """
    Thread-safe FastAPI middleware implementing token bucket algorithm for rate limiting
    with OpenTelemetry metrics integration.
    """

    def __init__(self, app: FastAPI, settings: Settings):
        """
        Initialize rate limiter middleware with thread-safe token bucket storage and metrics.

        Args:
            app: FastAPI application instance
            settings: Application settings instance
        """
        self.app = app
        self.token_buckets: Dict[str, Dict] = {}
        self.bucket_lock = asyncio.Lock()
        self.rate_limit = settings.RATE_LIMIT_PER_MINUTE
        self.tokens_per_second = self.rate_limit / 60.0

        # Initialize OpenTelemetry metrics
        self.meter = create_meter("rate_limiter")
        self.rate_limit_counter = self.meter.create_counter(
            name="rate_limit_exceeded_total",
            description="Total number of rate limit exceeded events",
            unit="1"
        )
        self.request_counter = self.meter.create_counter(
            name="rate_limited_requests_total",
            description="Total number of rate limited requests",
            unit="1"
        )
        self.tokens_histogram = self.meter.create_histogram(
            name="rate_limit_tokens_remaining",
            description="Distribution of remaining rate limit tokens",
            unit="tokens"
        )

        # Schedule periodic cleanup task
        asyncio.create_task(self._cleanup_buckets())

    async def _cleanup_buckets(self) -> None:
        """Thread-safe periodic cleanup of expired token buckets."""
        while True:
            try:
                async with self.bucket_lock:
                    current_time = time.time()
                    expired_clients = [
                        client_id for client_id, bucket in self.token_buckets.items()
                        if current_time - bucket["last_access"] > BUCKET_CLEANUP_INTERVAL
                    ]
                    
                    for client_id in expired_clients:
                        del self.token_buckets[client_id]
                    
                    if expired_clients:
                        LOGGER.info(
                            f"Cleaned up {len(expired_clients)} expired token buckets",
                            extra={"expired_count": len(expired_clients)}
                        )
                
                await asyncio.sleep(BUCKET_CLEANUP_INTERVAL)
            
            except Exception as e:
                LOGGER.error(f"Error in bucket cleanup: {e}", exc_info=True)
                await asyncio.sleep(60)  # Retry after 1 minute on error

    def _get_client_id(self, request: Request) -> str:
        """
        Extract and sanitize unique client identifier from request.

        Args:
            request: FastAPI request instance

        Returns:
            str: Sanitized unique client identifier
        """
        # Try X-Forwarded-For header first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        # Sanitize the IP address
        client_ip = "".join(c for c in client_ip if c.isalnum() or c in ".-:")
        return client_ip[:64]  # Limit length to prevent memory issues

    async def __call__(self, request: Request, call_next) -> Response:
        """
        Process request with thread-safe rate limiting check and metrics collection.

        Args:
            request: FastAPI request instance
            call_next: Next middleware in chain

        Returns:
            Response: HTTP response if allowed, rate limit error if exceeded

        Raises:
            SecurityError: When rate limit is exceeded
        """
        client_id = self._get_client_id(request)
        current_time = time.time()

        async with self.bucket_lock:
            # Get or create token bucket for client
            if client_id not in self.token_buckets:
                self.token_buckets[client_id] = {
                    "tokens": self.rate_limit,
                    "last_update": current_time,
                    "last_access": current_time
                }
            
            bucket = self.token_buckets[client_id]
            
            # Calculate tokens to add based on time elapsed
            time_passed = current_time - bucket["last_update"]
            tokens_to_add = time_passed * self.tokens_per_second
            bucket["tokens"] = min(
                self.rate_limit,
                bucket["tokens"] + tokens_to_add
            )
            
            # Update bucket timestamps
            bucket["last_update"] = current_time
            bucket["last_access"] = current_time

            # Record metrics
            self.tokens_histogram.record(
                bucket["tokens"],
                {"client_id": client_id}
            )
            self.request_counter.add(
                1,
                {"client_id": client_id}
            )

            # Check if request can be processed
            if bucket["tokens"] < 1:
                self.rate_limit_counter.add(
                    1,
                    {"client_id": client_id}
                )
                LOGGER.warning(
                    f"Rate limit exceeded for client {client_id}",
                    extra={
                        "client_id": client_id,
                        "path": request.url.path,
                        "method": request.method
                    }
                )
                raise SecurityError(
                    message="Rate limit exceeded",
                    error_code=ErrorCode.RATE_LIMIT_ERROR,
                    details={
                        "retry_after": int(60 / self.tokens_per_second)
                    }
                )

            # Consume one token
            bucket["tokens"] -= 1

        # Process request if allowed
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(int(bucket["tokens"]))
        response.headers["X-RateLimit-Reset"] = str(
            int(current_time + (self.rate_limit - bucket["tokens"]) / self.tokens_per_second)
        )

        return response