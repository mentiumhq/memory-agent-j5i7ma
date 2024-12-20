"""
Comprehensive logging configuration module for the Memory Agent service.
Implements structured JSON logging with security monitoring, distributed tracing,
and cloud-based log aggregation.

External Dependencies:
- python-json-logger==2.0.7: Structured JSON logging
- opentelemetry-instrumentation-logging==0.40b0: Distributed tracing
- watchtower==3.0.1: AWS CloudWatch integration
"""

import logging
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
from opentelemetry.instrumentation.logging import OpenTelemetryHandler
from opentelemetry.trace import get_trace_id
import watchtower
import threading
import uuid
import json
import re
from typing import Dict, Any
from config.settings import Settings

# Global constants for logging configuration
DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(correlation_id)s"
JSON_LOG_FORMAT = "%(timestamp)s %(level)s %(name)s %(message)s %(correlation_id)s %(trace_id)s %(span_id)s %(environment)s"
LOG_ROTATION_SIZE = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Cache for logger instances
LOGGER_CACHE: Dict[str, logging.Logger] = {}

class CorrelationIdFilter(logging.Filter):
    """
    Thread-safe logging filter that adds correlation ID and trace context to log records.
    Enables request tracking and distributed tracing correlation.
    """
    
    def __init__(self) -> None:
        """Initialize correlation tracking with thread-safe storage."""
        super().__init__()
        self._local = threading.local()
        self._local.correlation_id = None
        self._metrics = {
            "records_processed": 0,
            "correlation_ids_set": 0
        }

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Enrich log records with correlation and trace data.
        
        Args:
            record: LogRecord instance to be enriched
            
        Returns:
            bool: Always True to include the record
        """
        # Add correlation ID
        record.correlation_id = getattr(self._local, 'correlation_id', None) or str(uuid.uuid4())
        
        # Add trace context
        record.trace_id = get_trace_id()
        record.span_id = getattr(record, 'span_id', None)
        
        # Add security context
        record.environment = Settings.ENVIRONMENT
        
        # Update metrics
        self._metrics["records_processed"] += 1
        
        return True

    def set_correlation_id(self, correlation_id: str) -> None:
        """
        Set correlation ID for the current thread.
        
        Args:
            correlation_id: Unique identifier for request correlation
        """
        if not isinstance(correlation_id, str) or not correlation_id.strip():
            raise ValueError("Invalid correlation ID")
            
        self._local.correlation_id = correlation_id
        self._metrics["correlation_ids_set"] += 1

def sanitize_log_data(log_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize sensitive information from log data.
    
    Args:
        log_data: Dictionary containing log data
        
    Returns:
        Dict containing sanitized log data
    """
    sensitive_patterns = {
        'password': r'.*password.*',
        'token': r'.*token.*',
        'key': r'.*key.*',
        'secret': r'.*secret.*',
        'credential': r'.*credential.*'
    }
    
    def _mask_value(key: str, value: str) -> str:
        for pattern in sensitive_patterns.values():
            if re.match(pattern, key.lower()):
                return '***MASKED***'
        return value

    return {
        k: _mask_value(k, v) if isinstance(v, str) else v
        for k, v in log_data.items()
    }

def setup_logging(settings: Settings) -> None:
    """
    Initialize comprehensive logging system with security monitoring and tracing.
    
    Args:
        settings: Application settings instance
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL.value)
    
    # Create JSON formatter with extended fields
    json_formatter = jsonlogger.JsonFormatter(
        JSON_LOG_FORMAT,
        timestamp=True,
        json_default=str
    )
    
    # Configure console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(json_formatter)
    root_logger.addHandler(console_handler)
    
    # Configure rotating file handler
    file_handler = RotatingFileHandler(
        filename="logs/memory_agent.log",
        maxBytes=LOG_ROTATION_SIZE,
        backupCount=LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(json_formatter)
    root_logger.addHandler(file_handler)
    
    # Configure OpenTelemetry handler
    otel_handler = OpenTelemetryHandler()
    otel_handler.setFormatter(json_formatter)
    root_logger.addHandler(otel_handler)
    
    # Configure CloudWatch handler for production
    if settings.ENVIRONMENT == "production":
        try:
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group=settings.AWS_LOG_GROUP,
                stream_name=f"memory-agent-{settings.ENVIRONMENT}",
                use_queues=True,
                send_interval=60,
                create_log_group=True
            )
            cloudwatch_handler.setFormatter(json_formatter)
            root_logger.addHandler(cloudwatch_handler)
        except Exception as e:
            root_logger.error(f"Failed to initialize CloudWatch logging: {e}")
    
    # Add correlation ID filter
    correlation_filter = CorrelationIdFilter()
    root_logger.addFilter(correlation_filter)

def get_logger(name: str) -> logging.Logger:
    """
    Create or retrieve a cached logger instance with security and tracing capabilities.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger instance
    """
    if name in LOGGER_CACHE:
        return LOGGER_CACHE[name]
    
    logger = logging.getLogger(name)
    
    # Add correlation ID filter if not present
    has_correlation_filter = any(
        isinstance(f, CorrelationIdFilter) for f in logger.filters
    )
    if not has_correlation_filter:
        logger.addFilter(CorrelationIdFilter())
    
    # Cache logger instance
    LOGGER_CACHE[name] = logger
    
    return logger

# Export public interface
__all__ = [
    'setup_logging',
    'get_logger',
    'CorrelationIdFilter'
]