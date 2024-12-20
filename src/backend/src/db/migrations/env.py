"""
Alembic migrations environment configuration for SQLite database.
Provides enhanced migration handling with SQLite-specific optimizations and safety measures.

Version: 1.12.0 (alembic)
Version: 2.0.0 (sqlalchemy)
"""

import logging
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool, event
from sqlalchemy.engine import Connection
from sqlalchemy.exc import OperationalError

from ...db.base import Base
from ...config.settings import Settings

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("alembic.env")

# Alembic Config object
config = context.config

# Interpret the config file for Python logging if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy MetaData object containing declarative tables
target_metadata = Base.metadata

# Initialize settings
settings = Settings()

def include_object(object, name, type_, reflected, compare_to):
    """
    Filter objects included in migrations based on type and name.
    
    Args:
        object: The database object being considered
        name: Name of the object
        type_: Type of object (table, index, etc.)
        reflected: Whether object was reflected
        compare_to: Object being compared to
        
    Returns:
        bool: Whether to include the object in migrations
    """
    # Skip SQLite internal tables
    if name.startswith('sqlite_'):
        return False
    return True

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode for generating SQL scripts.
    
    This includes SQLite-specific configuration and enhanced safety measures.
    """
    url = settings.SQLITE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        # SQLite-specific configuration
        render_as_batch=True,  # Enable batch migrations for SQLite
        compare_type=True,     # Compare column types
        compare_server_default=True,  # Compare default values
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode with enhanced SQLite safety measures.
    
    Implements WAL mode, connection pooling optimizations, and transaction safety.
    """
    # SQLite-specific configuration
    def configure_sqlite_connection(connection: Connection, _):
        """Configure SQLite connection with optimizations and safety measures."""
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA temp_store=MEMORY")

    # SQLAlchemy configuration with SQLite optimizations
    config_section = config.get_section(config.config_ini_section)
    if not config_section:
        config_section = {}
    
    config_section.update({
        'sqlalchemy.url': settings.SQLITE_URL,
        'sqlalchemy.connect_args': {
            'timeout': 30,  # Connection timeout in seconds
            'check_same_thread': False,  # Allow multi-threading
        },
        'sqlalchemy.pool_pre_ping': True,  # Enable connection health checks
        'sqlalchemy.pool_size': 1,  # Single connection pool for SQLite
        'sqlalchemy.max_overflow': 0,  # Prevent connection overflow
    })

    connectable = engine_from_config(
        config_section,
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,  # Disable pooling for migrations
    )

    # Register SQLite connection configuration
    event.listen(connectable, 'connect', configure_sqlite_connection)

    try:
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                include_object=include_object,
                # SQLite-specific configuration
                render_as_batch=True,  # Enable batch migrations
                compare_type=True,     # Compare column types
                compare_server_default=True,  # Compare default values
                transaction_per_migration=True,  # Separate transaction per migration
            )

            with context.begin_transaction():
                logger.info("Running migrations...")
                context.run_migrations()
                logger.info("Migrations completed successfully")

    except OperationalError as e:
        logger.error(f"Migration failed: {str(e)}")
        raise
    finally:
        connectable.dispose()

def run_migrations():
    """
    Main migration execution function with enhanced error handling and logging.
    """
    logger.info("Starting database migrations...")
    
    try:
        if context.is_offline_mode():
            logger.info("Running offline migrations...")
            run_migrations_offline()
        else:
            logger.info("Running online migrations...")
            run_migrations_online()
        
        logger.info("Migration process completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed with error: {str(e)}")
        raise
    finally:
        logger.info("Migration process finished")

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()