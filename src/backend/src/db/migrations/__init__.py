"""
Database migrations package initialization for Memory Agent.
Provides type-safe access to SQLite schema migrations with WAL mode compatibility.

Version: 1.0.0
External Dependencies:
- alembic==1.11.0: Database migration management
"""

from typing import List
from alembic import command, config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from .env import run_migrations_offline, run_migrations_online

# Export migration functions for external use
__all__: List[str] = ["run_migrations_offline", "run_migrations_online"]

# Package version
__version__: str = "1.0.0"

# Migration configuration metadata
MIGRATION_METADATA = {
    "transaction_safety": {
        "mode": "atomic",
        "wal_compatible": True,
        "backup_required": True
    },
    "schema_tracking": {
        "enabled": True,
        "version_table": "alembic_version",
        "version_column": "version_num"
    }
}

def get_current_revision() -> str:
    """
    Get current database schema revision.
    
    Returns:
        str: Current revision identifier or None if no migrations applied
    """
    cfg = config.Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    with MigrationContext.configure(cfg.get_main_option("sqlalchemy.url")) as context:
        return context.get_current_revision()

def get_migration_history() -> List[str]:
    """
    Get list of applied migrations in chronological order.
    
    Returns:
        List[str]: List of migration revision identifiers
    """
    cfg = config.Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    with MigrationContext.configure(cfg.get_main_option("sqlalchemy.url")) as context:
        history = []
        current = context.get_current_revision()
        
        while current:
            history.append(current)
            current = script.get_revision(current).down_revision
            
        return list(reversed(history))

def verify_migration_consistency() -> bool:
    """
    Verify consistency between migration history and expected state.
    
    Returns:
        bool: True if migration state is consistent, False otherwise
    """
    cfg = config.Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    with MigrationContext.configure(cfg.get_main_option("sqlalchemy.url")) as context:
        current = context.get_current_revision()
        head = script.get_current_head()
        
        # Check if current revision matches latest available
        if current != head:
            return False
            
        # Verify migration chain integrity
        history = get_migration_history()
        for idx, rev in enumerate(history[:-1]):
            next_rev = script.get_revision(rev).nextrev
            if history[idx + 1] not in next_rev:
                return False
                
        return True

def get_pending_migrations() -> List[str]:
    """
    Get list of pending migrations that need to be applied.
    
    Returns:
        List[str]: List of pending migration revision identifiers
    """
    cfg = config.Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    
    with MigrationContext.configure(cfg.get_main_option("sqlalchemy.url")) as context:
        current = context.get_current_revision()
        
        # Get all revisions between current and head
        revisions = []
        for rev in script.iterate_revisions(current, script.get_current_head()):
            revisions.append(rev.revision)
            
        return list(reversed(revisions))

# Initialize package with required configuration
def __init_package() -> None:
    """Initialize migration package with required configuration."""
    # Verify alembic.ini exists
    cfg = config.Config()
    try:
        cfg.get_main_option("script_location")
    except Exception:
        raise RuntimeError(
            "alembic.ini not found. Ensure migration configuration is properly set up."
        )

__init_package()