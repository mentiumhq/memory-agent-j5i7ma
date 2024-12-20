"""
Database session management module providing SQLAlchemy session configuration and lifecycle handling.
Implements connection pooling, transaction management, and async support with comprehensive monitoring.

Version:
- SQLAlchemy==2.0+
- SQLAlchemy-Utils==0.41.1
"""

import time
import logging
from contextlib import contextmanager
from typing import Generator, Any, Optional
from prometheus_client import Counter, Histogram

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.exc import SQLAlchemyError

from config.settings import settings
from db.base import Base

# Configure logging
logger = logging.getLogger(__name__)

# Monitoring metrics
db_session_counter = Counter('db_session_total', 'Total number of database sessions created')
db_session_error_counter = Counter('db_session_errors_total', 'Total number of database session errors')
db_operation_duration = Histogram('db_operation_duration_seconds', 'Duration of database operations')

# Create SQLite engines with optimized connection pooling
engine = create_engine(
    settings.SQLITE_URL,
    pool_pre_ping=True,  # Enable connection health checks
    pool_size=5,         # Base pool size
    max_overflow=10,     # Maximum number of additional connections
    echo=False,          # Disable SQL echoing for production
    pool_recycle=3600,   # Recycle connections after 1 hour
    pool_timeout=30,     # Connection timeout in seconds
    connect_args={
        'timeout': 30,   # SQLite connection timeout
        'check_same_thread': False  # Allow multi-threading for SQLite
    }
)

# Create async engine for async operations
async_engine = create_async_engine(
    settings.SQLITE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
    pool_recycle=3600,
    pool_timeout=30,
    connect_args={
        'timeout': 30,
        'check_same_thread': False
    }
)

# Configure session factories
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False
)

AsyncSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configure SQLite connection with performance optimizations."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA cache_size=-2000")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()

def get_session() -> Session:
    """
    Creates and returns a new database session with error handling and monitoring.
    
    Returns:
        Session: New SQLAlchemy session instance
    """
    db_session_counter.inc()
    try:
        session = SessionLocal()
        session.execute("SELECT 1")  # Validate connection
        return session
    except SQLAlchemyError as e:
        db_session_error_counter.inc()
        logger.error(f"Error creating database session: {str(e)}")
        raise

async def get_async_session() -> AsyncSession:
    """
    Creates and returns a new async database session with error handling and monitoring.
    
    Returns:
        AsyncSession: New async SQLAlchemy session instance
    """
    db_session_counter.inc()
    try:
        session = AsyncSessionLocal()
        await session.execute("SELECT 1")  # Validate connection
        return session
    except SQLAlchemyError as e:
        db_session_error_counter.inc()
        logger.error(f"Error creating async database session: {str(e)}")
        raise

def init_db() -> None:
    """
    Initializes database schema with error handling and validation.
    Creates tables, indexes, and configures optimizations.
    """
    try:
        # Import all models to ensure they're registered
        from db import models  # noqa: F401
        
        # Create database schema
        Base.metadata.create_all(bind=engine)
        
        # Verify schema creation
        inspector = inspect(engine)
        for table in Base.metadata.tables:
            if not inspector.has_table(table):
                raise RuntimeError(f"Failed to create table: {table}")
                
        logger.info("Database initialization completed successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {str(e)}")
        raise

class DatabaseSession:
    """Context manager for handling database session lifecycle with comprehensive error handling."""
    
    def __init__(self):
        """Initialize database session context manager with monitoring."""
        self.session: Optional[Session] = None
        self._start_time: float = 0
        self._metrics: dict = {
            'operations': 0,
            'errors': 0
        }

    def __enter__(self) -> Session:
        """
        Enters context and creates new session with monitoring.
        
        Returns:
            Session: Active database session
        """
        self._start_time = time.time()
        self.session = get_session()
        return self.session

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exits context and closes session with error handling.
        
        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        try:
            if exc_type is not None:
                if self.session:
                    self.session.rollback()
                db_session_error_counter.inc()
                self._metrics['errors'] += 1
            
            if self.session:
                self.session.close()
                
            # Record operation duration
            duration = time.time() - self._start_time
            db_operation_duration.observe(duration)
            
        except Exception as e:
            logger.error(f"Error during session cleanup: {str(e)}")
            raise
        finally:
            self.session = None

class AsyncDatabaseSession:
    """Async context manager for handling async database session lifecycle."""
    
    def __init__(self):
        """Initialize async database session context manager."""
        self.session: Optional[AsyncSession] = None
        self._start_time: float = 0
        self._metrics: dict = {
            'operations': 0,
            'errors': 0
        }

    async def __aenter__(self) -> AsyncSession:
        """
        Enters async context and creates new session.
        
        Returns:
            AsyncSession: Active async database session
        """
        self._start_time = time.time()
        self.session = await get_async_session()
        return self.session

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """
        Exits async context and closes session with error handling.
        
        Args:
            exc_type: Exception type if error occurred
            exc_val: Exception value if error occurred
            exc_tb: Exception traceback if error occurred
        """
        try:
            if exc_type is not None:
                if self.session:
                    await self.session.rollback()
                db_session_error_counter.inc()
                self._metrics['errors'] += 1
            
            if self.session:
                await self.session.close()
                
            # Record operation duration
            duration = time.time() - self._start_time
            db_operation_duration.observe(duration)
            
        except Exception as e:
            logger.error(f"Error during async session cleanup: {str(e)}")
            raise
        finally:
            self.session = None

__all__ = [
    'get_session',
    'get_async_session',
    'init_db',
    'DatabaseSession',
    'AsyncDatabaseSession'
]