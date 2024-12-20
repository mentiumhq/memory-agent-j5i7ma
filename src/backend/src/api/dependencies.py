"""
FastAPI dependency injection module providing thread-safe service initialization,
session management, and comprehensive error handling with telemetry.

Version:
- fastapi==0.100+
- circuitbreaker==1.4+
"""

import logging
from typing import AsyncGenerator
from threading import Lock
from fastapi import Depends
from circuitbreaker import circuit_breaker

from db.session import get_session
from services.document import DocumentService
from services.llm import LLMService
from core.telemetry import create_tracer
from core.errors import StorageError, ErrorCode
from config.logging import get_logger

# Initialize logging and tracing
LOGGER = get_logger(__name__)
TRACER = create_tracer('api_dependencies')

# Thread-safe service initialization
_document_service = None
_llm_service = None
_service_lock = Lock()

@circuit_breaker(failure_threshold=5, recovery_timeout=60)
async def get_db() -> AsyncGenerator:
    """
    Provides database session with automatic cleanup and telemetry.
    
    Yields:
        Database session with configured timeout and error handling
        
    Raises:
        StorageError: If session creation or management fails
    """
    with TRACER.start_as_current_span("get_db_session") as span:
        try:
            # Get new session
            session = get_session()
            span.set_attribute("session_id", str(id(session)))
            
            try:
                # Validate session
                session.execute("SELECT 1")
                
                # Yield session for request
                yield session
                
                # Commit if no errors
                if session.is_active:
                    session.commit()
                    
            except Exception as e:
                # Rollback on error
                if session.is_active:
                    session.rollback()
                LOGGER.error(f"Session error: {str(e)}", exc_info=True)
                raise StorageError(
                    "Database session error",
                    ErrorCode.STORAGE_ERROR,
                    {"error": str(e)}
                )
            finally:
                # Always close session
                session.close()
                
        except Exception as e:
            LOGGER.error(f"Failed to create database session: {str(e)}", exc_info=True)
            raise StorageError(
                "Failed to create database session",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

@circuit_breaker(failure_threshold=3, recovery_timeout=30)
async def get_document_service() -> DocumentService:
    """
    Thread-safe singleton provider for DocumentService with health monitoring.
    
    Returns:
        Validated DocumentService instance
        
    Raises:
        StorageError: If service initialization or validation fails
    """
    global _document_service
    
    with TRACER.start_as_current_span("get_document_service") as span:
        try:
            with _service_lock:
                # Return existing service if healthy
                if _document_service is not None:
                    # Validate service health
                    if await _document_service.health_check():
                        return _document_service
                    
                # Initialize new service
                session = get_session()
                _document_service = DocumentService(
                    storage_service=session.storage_service,
                    embedding_service=session.embedding_service,
                    document_repo=session.document_repo
                )
                
                # Validate new service
                if not await _document_service.health_check():
                    raise StorageError(
                        "Document service validation failed",
                        ErrorCode.STORAGE_ERROR
                    )
                
                span.set_attribute("service_initialized", True)
                return _document_service
                
        except Exception as e:
            LOGGER.error(f"Failed to get document service: {str(e)}", exc_info=True)
            raise StorageError(
                "Failed to initialize document service",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

@circuit_breaker(failure_threshold=3, recovery_timeout=30)
async def get_llm_service() -> LLMService:
    """
    Thread-safe singleton provider for LLMService with API validation.
    
    Returns:
        Validated LLMService instance
        
    Raises:
        StorageError: If service initialization or validation fails
    """
    global _llm_service
    
    with TRACER.start_as_current_span("get_llm_service") as span:
        try:
            with _service_lock:
                # Return existing service if healthy
                if _llm_service is not None:
                    # Validate service health
                    if await _llm_service.health_check():
                        return _llm_service
                    
                # Initialize new service
                session = get_session()
                _llm_service = LLMService(
                    llm_client=session.llm_client,
                    cache_ttl=3600  # 1 hour cache TTL
                )
                
                # Validate API key and service health
                if not await _llm_service.validate_api_key():
                    raise StorageError(
                        "LLM service API validation failed",
                        ErrorCode.AUTHENTICATION_ERROR
                    )
                
                if not await _llm_service.health_check():
                    raise StorageError(
                        "LLM service health check failed",
                        ErrorCode.STORAGE_ERROR
                    )
                
                span.set_attribute("service_initialized", True)
                return _llm_service
                
        except Exception as e:
            LOGGER.error(f"Failed to get LLM service: {str(e)}", exc_info=True)
            raise StorageError(
                "Failed to initialize LLM service",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )
```

This implementation provides:

1. Thread-safe singleton initialization for services with comprehensive health monitoring and validation

2. Database session management with automatic cleanup, error handling, and telemetry

3. Circuit breaker patterns to prevent cascading failures

4. Comprehensive error handling and logging

5. OpenTelemetry integration for monitoring and tracing

6. Proper resource cleanup and session management

The dependencies can be used in FastAPI endpoints like:

```python
@app.get("/documents/{id}")
async def get_document(
    id: str,
    db: Session = Depends(get_db),
    doc_service: DocumentService = Depends(get_document_service)
):
    # Use injected dependencies
    pass