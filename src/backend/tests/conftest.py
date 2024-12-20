"""
Pytest configuration and fixtures for Memory Agent system tests.
Provides comprehensive test environment setup with database isolation,
mock services, telemetry, and security context.

Version: 1.0.0
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
import moto
import pytest_asyncio
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from config.settings import Settings
from db.session import get_session, init_db
from integrations.aws.s3 import S3Client
from integrations.temporal.client import TemporalClient
from core.telemetry import setup_telemetry, create_tracer
from config.logging import setup_logging, get_logger

# Initialize test logger
LOGGER = get_logger(__name__)

# Test configuration constants
TEST_DB_URL = "sqlite:///./test.db"
TEST_TELEMETRY_CONFIG = {
    "sampling_rate": 1.0,
    "trace_id_ratio": 1.0,
    "metrics_interval": 1.0
}
TEST_SECURITY_CONTEXT = {
    "encryption_key": Fernet.generate_key(),
    "auth_token": "test_token_123",
    "test_namespace": "memory-agent-test"
}

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Creates instrumented event loop for async tests with telemetry.
    
    Returns:
        Generator yielding configured asyncio event loop
    """
    try:
        # Initialize test telemetry
        tracer_provider, meter_provider = setup_telemetry(Settings())
        
        # Create and configure loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Start telemetry recording
        tracer = create_tracer("test_execution")
        with tracer.start_as_current_span("test_session"):
            yield loop
            
        # Cleanup
        loop.close()
        
    except Exception as e:
        LOGGER.error(f"Failed to setup test event loop: {e}")
        raise

@pytest.fixture(scope="function")
def test_db() -> Generator[Session, None, None]:
    """
    Sets up isolated test database with transaction boundaries.
    
    Returns:
        Generator yielding SQLAlchemy session for test database
    """
    try:
        # Override database URL for tests
        Settings.SQLITE_URL = TEST_DB_URL
        
        # Initialize test database
        init_db()
        
        # Create test session with transaction
        session = get_session()
        session.begin_nested()
        
        yield session
        
        # Rollback transaction after test
        session.rollback()
        session.close()
        
    except Exception as e:
        LOGGER.error(f"Failed to setup test database: {e}")
        raise

@pytest.fixture(scope="function")
def mock_s3() -> Generator[S3Client, None, None]:
    """
    Provides secure mocked S3 client for testing.
    
    Returns:
        Generator yielding mocked S3 client instance
    """
    try:
        # Start moto S3 mock
        with moto.mock_s3():
            # Initialize mock client with test config
            s3_client = S3Client(Settings())
            
            # Create test bucket
            s3_client._client.create_bucket(
                Bucket=Settings.S3_BUCKET_NAME,
                ObjectOwnership="BucketOwner"
            )
            
            # Enable versioning
            s3_client._client.put_bucket_versioning(
                Bucket=Settings.S3_BUCKET_NAME,
                VersioningConfiguration={"Status": "Enabled"}
            )
            
            yield s3_client
            
    except Exception as e:
        LOGGER.error(f"Failed to setup mock S3: {e}")
        raise

@pytest_asyncio.fixture(scope="function")
async def mock_temporal() -> AsyncGenerator[TemporalClient, None]:
    """
    Provides monitored mock Temporal client for testing.
    
    Returns:
        AsyncGenerator yielding mocked Temporal client instance
    """
    try:
        # Initialize mock client with test config
        client = TemporalClient(
            settings=Settings(),
            retry_policy=None  # Disable retries for tests
        )
        
        # Configure test namespace
        client._settings.TEMPORAL_NAMESPACE = TEST_SECURITY_CONTEXT["test_namespace"]
        
        # Start telemetry recording
        tracer = create_tracer("temporal_tests")
        with tracer.start_as_current_span("temporal_test"):
            yield client
            
    except Exception as e:
        LOGGER.error(f"Failed to setup mock Temporal client: {e}")
        raise

@pytest.fixture(scope="session")
def test_telemetry() -> Generator[TracerProvider, None, None]:
    """
    Configures OpenTelemetry for test execution monitoring.
    
    Returns:
        Generator yielding configured test tracer provider
    """
    try:
        # Initialize test tracer provider
        tracer_provider, meter_provider = setup_telemetry(Settings())
        
        # Configure test sampling
        tracer_provider.update_sampling_rate(TEST_TELEMETRY_CONFIG["sampling_rate"])
        
        yield tracer_provider
        
        # Export collected telemetry
        tracer_provider.force_flush()
        meter_provider.force_flush()
        
    except Exception as e:
        LOGGER.error(f"Failed to setup test telemetry: {e}")
        raise

@pytest.fixture(scope="session")
def test_security() -> Generator[dict, None, None]:
    """
    Manages security context for test execution.
    
    Returns:
        Generator yielding test security configuration
    """
    try:
        # Initialize encryption for tests
        fernet = Fernet(TEST_SECURITY_CONTEXT["encryption_key"])
        
        # Configure test credentials
        security_context = {
            "fernet": fernet,
            "auth_token": TEST_SECURITY_CONTEXT["auth_token"],
            "test_namespace": TEST_SECURITY_CONTEXT["test_namespace"]
        }
        
        yield security_context
        
        # Clear sensitive data
        security_context.clear()
        
    except Exception as e:
        LOGGER.error(f"Failed to setup test security context: {e}")
        raise