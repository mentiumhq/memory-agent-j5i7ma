"""
Enterprise-grade telemetry implementation for the Memory Agent service.
Provides comprehensive distributed tracing, metrics collection, and security monitoring
using OpenTelemetry instrumentation.

External Dependencies:
- opentelemetry-api==1.20.0: Core OpenTelemetry API
- opentelemetry-sdk==1.20.0: OpenTelemetry implementation
- opentelemetry-exporter-otlp-proto-grpc==1.20.0: OTLP gRPC exporter
- opentelemetry-instrumentation==0.40b0: Auto-instrumentation support
"""

from typing import Dict, Optional, Tuple, Any
import time
from fastapi import Request, Response
from opentelemetry.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.grpc import (
    OTLPSpanExporter,
    OTLPMetricExporter
)
from opentelemetry.sdk.metrics.export import PrometheusMetricReader
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Tracer, Span
from opentelemetry.metrics import Meter, Counter, Histogram
from opentelemetry.sdk.trace.sampling import ParentBasedTraceIdRatio
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from config.settings import Settings
from config.logging import get_logger

# Initialize logger
LOGGER = get_logger(__name__)

# Constants
SERVICE_NAME = "memory-agent"
SECURITY_RELEVANT_PATHS = {"/login", "/documents", "/admin"}
LATENCY_BUCKETS = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]

# Cache for tracer and meter instances
_TRACER_CACHE: Dict[str, Tracer] = {}
_METER_CACHE: Dict[str, Meter] = {}

def setup_telemetry(settings: Settings) -> Tuple[TracerProvider, MeterProvider]:
    """
    Initialize OpenTelemetry instrumentation with comprehensive configuration.
    
    Args:
        settings: Application settings instance
        
    Returns:
        Tuple containing configured TracerProvider and MeterProvider
    """
    try:
        # Create resource with detailed service information
        resource = Resource.create({
            "service.name": SERVICE_NAME,
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENVIRONMENT.value,
            "host.name": settings.TEMPORAL_HOST,
        })

        # Configure sampling rate based on environment
        sampling_rate = 1.0 if settings.ENVIRONMENT.value == "development" else 0.1
        sampler = ParentBasedTraceIdRatio(sampling_rate)

        # Initialize TracerProvider with resource and sampling
        tracer_provider = TracerProvider(
            resource=resource,
            sampler=sampler
        )

        # Configure span exporter with retry and timeout
        otlp_span_exporter = OTLPSpanExporter(
            endpoint=settings.OTLP_ENDPOINT,
            insecure=settings.ENVIRONMENT.value != "production",
            timeout=30  # 30 second timeout
        )

        # Set up batch processor with configurable settings
        span_processor = BatchSpanProcessor(
            otlp_span_exporter,
            max_export_batch_size=512,
            max_queue_size=2048,
            schedule_delay_millis=5000,
            export_timeout_millis=30000,
        )
        tracer_provider.add_span_processor(span_processor)

        # Initialize MeterProvider with resource
        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=[
                PrometheusMetricReader(),
                OTLPMetricExporter(
                    endpoint=settings.OTLP_ENDPOINT,
                    insecure=settings.ENVIRONMENT.value != "production",
                    timeout=30
                )
            ]
        )

        return tracer_provider, meter_provider

    except Exception as e:
        LOGGER.error(f"Failed to initialize telemetry: {e}", exc_info=True)
        raise

def create_tracer(component_name: str) -> Tracer:
    """
    Create or retrieve a cached tracer instance for a specific component.
    
    Args:
        component_name: Name of the component requiring tracing
        
    Returns:
        Component-specific tracer instance
    """
    if not component_name or not isinstance(component_name, str):
        raise ValueError("Invalid component name")

    if component_name in _TRACER_CACHE:
        return _TRACER_CACHE[component_name]

    try:
        tracer = TracerProvider().get_tracer(
            instrumenting_module_name=component_name,
            instrumenting_library_version=Settings.VERSION
        )
        _TRACER_CACHE[component_name] = tracer
        return tracer
    except Exception as e:
        LOGGER.error(f"Failed to create tracer for {component_name}: {e}", exc_info=True)
        raise

def create_meter(component_name: str) -> Meter:
    """
    Create or retrieve a cached meter instance for a specific component.
    
    Args:
        component_name: Name of the component requiring metrics
        
    Returns:
        Component-specific meter instance
    """
    if not component_name or not isinstance(component_name, str):
        raise ValueError("Invalid component name")

    if component_name in _METER_CACHE:
        return _METER_CACHE[component_name]

    try:
        meter = MeterProvider().get_meter(
            name=component_name,
            version=Settings.VERSION
        )
        _METER_CACHE[component_name] = meter
        return meter
    except Exception as e:
        LOGGER.error(f"Failed to create meter for {component_name}: {e}", exc_info=True)
        raise

class TelemetryMiddleware:
    """FastAPI middleware for comprehensive request telemetry and security monitoring."""

    def __init__(self, app: Any):
        """
        Initialize telemetry middleware with metrics and security monitoring.
        
        Args:
            app: FastAPI application instance
        """
        self.app = app
        self.tracer = create_tracer("http_middleware")
        self.meter = create_meter("http_middleware")
        
        # Initialize request metrics
        self.request_counter = self.meter.create_counter(
            name="http_requests_total",
            description="Total HTTP requests",
            unit="1"
        )
        
        self.request_duration = self.meter.create_histogram(
            name="http_request_duration_seconds",
            description="HTTP request duration",
            unit="s",
            boundaries=LATENCY_BUCKETS
        )
        
        self.error_counter = self.meter.create_counter(
            name="http_errors_total",
            description="Total HTTP errors",
            unit="1"
        )

    async def __call__(self, request: Request, call_next: Any) -> Response:
        """
        Process request with comprehensive telemetry and security monitoring.
        
        Args:
            request: FastAPI request instance
            call_next: Next middleware in chain
            
        Returns:
            Processed response with telemetry data
        """
        start_time = time.time()
        
        # Extract trace context
        context = TraceContextTextMapPropagator().extract(
            carrier=dict(request.headers)
        )
        
        # Start request span
        with self.tracer.start_as_current_span(
            name=f"HTTP {request.method} {request.url.path}",
            context=context,
            kind=Span.KIND_SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.route": request.url.path,
                "http.user_agent": request.headers.get("user-agent", ""),
                "net.peer.ip": request.client.host if request.client else "",
            }
        ) as span:
            try:
                # Process request
                response = await call_next(request)
                duration = time.time() - start_time
                
                # Record metrics
                self.request_counter.add(
                    1,
                    {"method": request.method, "path": request.url.path}
                )
                self.request_duration.record(
                    duration,
                    {"method": request.method, "path": request.url.path}
                )
                
                # Add response attributes
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_content_length", 
                                 len(response.body) if hasattr(response, "body") else 0)
                
                # Monitor security-relevant requests
                if request.url.path in SECURITY_RELEVANT_PATHS:
                    LOGGER.info(
                        "Security relevant request",
                        extra={
                            "path": request.url.path,
                            "method": request.method,
                            "client_ip": request.client.host if request.client else "",
                            "status_code": response.status_code
                        }
                    )
                
                return response
                
            except Exception as e:
                # Record error metrics
                self.error_counter.add(
                    1,
                    {
                        "method": request.method,
                        "path": request.url.path,
                        "error_type": type(e).__name__
                    }
                )
                
                # Log error with trace context
                LOGGER.error(
                    f"Request failed: {str(e)}",
                    exc_info=True,
                    extra={
                        "trace_id": span.get_span_context().trace_id,
                        "span_id": span.get_span_context().span_id
                    }
                )
                raise

__all__ = [
    "setup_telemetry",
    "create_tracer",
    "create_meter",
    "TelemetryMiddleware"
]