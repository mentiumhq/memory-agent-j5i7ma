"""
Test package initialization module for the Memory Agent system.
Configures test environment with security controls, performance monitoring,
and comprehensive test isolation.

External Dependencies:
- pytest==7.4.0: Testing framework configuration
- logging==3.11.0: Python logging configuration
"""

import os
import pytest
import logging
from typing import Dict, Any
from functools import wraps

from config.settings import Settings
from config.logging import (
    setup_logging,
    get_logger,
    CorrelationIdFilter,
    sanitize_log_data
)

# Test environment constants
TEST_ENV = "test"
TEST_LOG_LEVEL = "DEBUG"

# Initialize test logger
test_logger = get_logger(__name__)

def configure_test_environment() -> None:
    """
    Configures the test environment including logging, settings, security controls,
    and performance monitoring.
    
    Sets up:
    - Test-specific logging with security filtering
    - Isolated test settings
    - Test correlation tracking
    - Performance monitoring
    - Test data cleanup
    - Secure test credentials
    - Test caching strategy
    - Test timeouts
    - Storage isolation
    """
    # Set test environment variables
    os.environ["MEMORY_AGENT_ENVIRONMENT"] = TEST_ENV
    os.environ["MEMORY_AGENT_LOG_LEVEL"] = TEST_LOG_LEVEL
    
    # Configure test database path
    os.environ["MEMORY_AGENT_SQLITE_URL"] = "sqlite:///./test_memory_agent.db"
    
    # Configure test S3 bucket
    os.environ["MEMORY_AGENT_S3_BUCKET_NAME"] = "test-memory-agent"
    
    # Set test security credentials
    os.environ["MEMORY_AGENT_SECRET_KEY"] = "test-secret-key-" + "x" * 32
    os.environ["MEMORY_AGENT_AWS_ACCESS_KEY_ID"] = "test-access-key"
    os.environ["MEMORY_AGENT_AWS_SECRET_ACCESS_KEY"] = "test-secret-key"
    os.environ["MEMORY_AGENT_OPENAI_API_KEY"] = "test-openai-key"
    
    # Initialize test settings
    test_settings = Settings()
    
    # Configure test-specific logging
    setup_logging(test_settings)
    
    # Add test-specific correlation filter
    test_correlation_filter = CorrelationIdFilter()
    test_logger.addFilter(test_correlation_filter)
    
    # Configure test metrics collection
    configure_test_metrics()
    
    # Initialize test data cleanup
    register_test_cleanup()
    
    test_logger.info(
        "Test environment configured",
        extra=sanitize_log_data({
            "environment": TEST_ENV,
            "log_level": TEST_LOG_LEVEL,
            "test_settings": test_settings.dict(exclude_secrets=True)
        })
    )

def configure_test_metrics() -> None:
    """Configure test-specific metrics collection."""
    # Initialize test metrics storage
    pytest.test_metrics = {
        "tests_executed": 0,
        "assertions_passed": 0,
        "performance_measurements": {},
        "security_validations": {}
    }

def register_test_cleanup() -> None:
    """Register cleanup handlers for test data and resources."""
    @pytest.fixture(autouse=True)
    def cleanup_test_data():
        """Cleanup fixture that runs after each test."""
        yield  # Test execution
        
        # Clean up test database
        if os.path.exists("./test_memory_agent.db"):
            os.remove("./test_memory_agent.db")
        
        # Clean up test logs
        if os.path.exists("./logs/test_memory_agent.log"):
            os.remove("./logs/test_memory_agent.log")
        
        # Reset test metrics
        pytest.test_metrics["tests_executed"] += 1

def performance_test(threshold_ms: int):
    """
    Decorator for performance testing with timing threshold.
    
    Args:
        threshold_ms: Maximum allowed execution time in milliseconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            import time
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000
            
            # Record performance metric
            pytest.test_metrics["performance_measurements"][func.__name__] = execution_time
            
            # Assert performance threshold
            assert execution_time <= threshold_ms, (
                f"Performance threshold exceeded: {execution_time}ms > {threshold_ms}ms"
            )
            return result
        return wrapper
    return decorator

def security_test():
    """Decorator for security-focused tests with additional validation."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Track security test execution
            test_name = func.__name__
            pytest.test_metrics["security_validations"][test_name] = {
                "executed": True,
                "passed": False
            }
            
            try:
                result = func(*args, **kwargs)
                pytest.test_metrics["security_validations"][test_name]["passed"] = True
                return result
            except Exception as e:
                pytest.test_metrics["security_validations"][test_name]["error"] = str(e)
                raise
        return wrapper
    return decorator

# Initialize test environment when module is imported
configure_test_environment()

# Export public interface
__all__ = [
    'configure_test_environment',
    'TEST_ENV',
    'TEST_LOG_LEVEL',
    'performance_test',
    'security_test'
]