"""
Initialization module for Memory Agent integration tests.
Provides comprehensive test environment setup with fixtures, monitoring,
and utilities for API, workflow, security, and performance testing.

Version: 1.0.0
"""

import pytest
import pytest_asyncio
from opentelemetry.trace import get_current_span
from prometheus_client import Counter, Histogram
from typing import Dict, List, Optional

from ..conftest import db_session, test_client, temporal_client
from core.errors import ErrorCode
from core.telemetry import create_tracer, create_meter

# Initialize test monitoring
TRACER = create_tracer("integration_tests")
METER = create_meter("integration_tests")

# Test data constants
TEST_DOCUMENT_CONTENT = "Test document content for integration testing"
TEST_DOCUMENT_FORMAT = "markdown"
TEST_SEARCH_QUERY = "test query"
TEST_STRATEGIES = ["vector", "llm", "hybrid", "rag_kg"]

# Performance thresholds (ms)
PERFORMANCE_THRESHOLDS = {
    "store_latency_ms": 2000,    # 2 seconds max for document storage
    "retrieve_latency_ms": 3000,  # 3 seconds max for document retrieval
    "search_latency_ms": 5000    # 5 seconds max for document search
}

# Test security context
TEST_SECURITY_CONTEXT = {
    "test_jwt": "test_token",
    "test_api_key": "test_key"
}

# Test metrics
test_operation_counter = Counter(
    "test_operations_total",
    "Total number of test operations",
    ["operation_type"]
)

test_operation_duration = Histogram(
    "test_operation_duration_seconds",
    "Duration of test operations",
    ["operation_type"]
)

def pytest_configure(config):
    """
    Configure pytest for comprehensive integration testing with security
    and performance monitoring.
    
    Args:
        config: pytest configuration object
    """
    # Register custom markers
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "performance: mark test as performance test"
    )
    config.addinivalue_line(
        "markers",
        "security: mark test as security test"
    )
    
    # Configure async test settings
    config.option.asyncio_mode = "auto"
    
    # Set test timeouts
    config.option.timeout = 30  # 30 second timeout per test
    
    # Initialize test monitoring
    with TRACER.start_as_current_span("test_setup") as span:
        span.set_attribute("test.framework", "pytest")
        span.set_attribute("test.type", "integration")

class IntegrationTestBase:
    """
    Enhanced base class for integration tests providing comprehensive utilities
    for testing, monitoring, and validation.
    """
    
    def __init__(self):
        """Initialize enhanced test base class with monitoring and security capabilities."""
        self.test_document_content = TEST_DOCUMENT_CONTENT
        self.test_document_format = TEST_DOCUMENT_FORMAT
        self.test_search_query = TEST_SEARCH_QUERY
        self.test_strategies = TEST_STRATEGIES
        
        # Initialize test monitoring
        self.tracer = TRACER
        self.meter = METER
        
        # Initialize test metrics
        self.operation_counter = test_operation_counter
        self.operation_duration = test_operation_duration
        
        # Initialize test security context
        self.security_context = TEST_SECURITY_CONTEXT.copy()
    
    async def setup_test_data(self) -> Dict:
        """
        Sets up comprehensive test data with proper isolation.
        
        Returns:
            Dict: Test data configuration
        """
        with self.tracer.start_as_current_span("setup_test_data") as span:
            try:
                # Create test document data
                test_data = {
                    "document": {
                        "content": self.test_document_content,
                        "format": self.test_document_format,
                        "metadata": {
                            "test_id": "test-123",
                            "test_type": "integration"
                        }
                    },
                    "search": {
                        "query": self.test_search_query,
                        "strategies": self.test_strategies
                    }
                }
                
                # Record test setup
                self.operation_counter.labels(
                    operation_type="test_setup"
                ).inc()
                
                span.set_attribute("test.data.setup", "success")
                return test_data
                
            except Exception as e:
                span.set_attribute("test.data.setup", "failure")
                span.record_exception(e)
                raise
    
    async def cleanup_test_data(self) -> None:
        """
        Ensures proper cleanup of test resources.
        """
        with self.tracer.start_as_current_span("cleanup_test_data") as span:
            try:
                # Clear test security context
                self.security_context.clear()
                
                # Record cleanup
                self.operation_counter.labels(
                    operation_type="test_cleanup"
                ).inc()
                
                span.set_attribute("test.data.cleanup", "success")
                
            except Exception as e:
                span.set_attribute("test.data.cleanup", "failure")
                span.record_exception(e)
                raise
    
    async def measure_performance(self, operation_name: str) -> Dict:
        """
        Collects and validates performance metrics.
        
        Args:
            operation_name: Name of operation being measured
            
        Returns:
            Dict: Performance metrics
        """
        with self.tracer.start_as_current_span(f"measure_{operation_name}") as span:
            try:
                # Get threshold for operation
                threshold_ms = PERFORMANCE_THRESHOLDS.get(
                    f"{operation_name}_latency_ms",
                    5000  # Default 5 second threshold
                )
                
                # Record operation metrics
                self.operation_counter.labels(
                    operation_type=operation_name
                ).inc()
                
                # Get current span duration
                duration_ms = span.end_time - span.start_time
                
                # Record duration
                self.operation_duration.labels(
                    operation_type=operation_name
                ).observe(duration_ms / 1000.0)  # Convert to seconds
                
                # Validate against threshold
                metrics = {
                    "operation": operation_name,
                    "duration_ms": duration_ms,
                    "threshold_ms": threshold_ms,
                    "passed": duration_ms <= threshold_ms
                }
                
                span.set_attribute("performance.check", "success")
                span.set_attribute("performance.passed", metrics["passed"])
                
                return metrics
                
            except Exception as e:
                span.set_attribute("performance.check", "failure")
                span.record_exception(e)
                raise

# Export public interface
__all__ = [
    "IntegrationTestBase",
    "TEST_DOCUMENT_CONTENT",
    "TEST_DOCUMENT_FORMAT",
    "TEST_SEARCH_QUERY",
    "TEST_STRATEGIES",
    "PERFORMANCE_THRESHOLDS"
]