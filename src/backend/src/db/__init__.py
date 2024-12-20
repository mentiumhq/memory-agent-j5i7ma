"""
Database package initialization module for the Memory Agent system.
Provides centralized access to database functionality with SQLite optimization.

Version:
- SQLAlchemy==2.0+
- SQLAlchemy-Utils==0.41.1
"""

# Import core database components
from .base import Base
from .session import (
    get_session,
    init_db,
    AsyncSessionFactory,
    DatabaseSession,
    AsyncDatabaseSession
)
from .models.document import Document

# Export core components for external use
__all__ = [
    # Base declarative class for ORM models
    'Base',
    
    # Session management
    'get_session',
    'init_db',
    'AsyncSessionFactory',
    'DatabaseSession',
    'AsyncDatabaseSession',
    
    # ORM Models
    'Document'
]

# Package metadata
__version__ = '1.0.0'
__author__ = 'Memory Agent Team'

# Initialize logging for database operations
import logging
logger = logging.getLogger(__name__)

def configure_logging():
    """Configure database-specific logging handlers."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Configure package logging
configure_logging()

# Validate database configuration on import
try:
    from config.settings import settings
    if not settings.SQLITE_URL:
        raise ValueError("Database URL not configured")
    logger.info(f"Database configured with URL: {settings.SQLITE_URL}")
except Exception as e:
    logger.error(f"Database configuration error: {str(e)}")
    raise

# Initialize database connection pool and session factory
try:
    init_db()
    logger.info("Database initialization completed successfully")
except Exception as e:
    logger.error(f"Database initialization failed: {str(e)}")
    raise