"""
SQLAlchemy declarative base configuration with SQLite optimizations and secure serialization.

This module defines the base SQLAlchemy model class with type-safe ORM functionality,
SQLite-specific optimizations, and secure data serialization methods.

Version: 2.0+
"""

from typing import Any, Dict, List, Optional, Type
from sqlalchemy import MetaData, inspect
from sqlalchemy.orm import as_declarative, declarative_base
from sqlalchemy import TypeDecorator
import json

# Configure SQLAlchemy metadata with naming conventions and SQLite optimizations
metadata = MetaData(
    # Standard naming conventions for constraints and indexes
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    },
    # SQLite-specific pragmas for performance and durability
    sqlite_on_connect=[
        "PRAGMA journal_mode=WAL",  # Write-Ahead Logging for better concurrency
        "PRAGMA synchronous=NORMAL",  # Balance between safety and performance
        "PRAGMA foreign_keys=ON",    # Enforce referential integrity
        "PRAGMA cache_size=-2000",   # 2MB cache size for better performance
        "PRAGMA temp_store=MEMORY",  # Store temp tables in memory
    ]
)

class JSONEncodedDict(TypeDecorator):
    """
    Custom SQLAlchemy type for secure JSON serialization.
    Handles conversion between Python dictionaries and JSON strings.
    """
    impl = str
    cache_ok = True

    def process_bind_param(self, value: Optional[Dict], dialect: Any) -> Optional[str]:
        """Securely convert dictionary to JSON string for storage."""
        if value is None:
            return None
        return json.dumps(value, sort_keys=True)

    def process_result_value(self, value: Optional[str], dialect: Any) -> Optional[Dict]:
        """Securely convert stored JSON string back to dictionary."""
        if value is None:
            return None
        return json.loads(value)

@as_declarative(metadata=metadata)
class Base:
    """
    SQLAlchemy declarative base class providing type-safe ORM functionality
    with SQLite optimizations and secure serialization.
    """
    
    # Mark as abstract base class
    __abstract__ = True
    
    # Default table arguments for all models
    __table_args__ = {
        "sqlite_on_conflict": "ROLLBACK",  # Default conflict resolution
        "sqlite_with_rowid": True,         # Enable implicit rowid
        "keep_existing": True              # Preserve existing tables during reflection
    }

    def to_dict(
        self,
        exclude_fields: Optional[List[str]] = None,
        sanitize: bool = True
    ) -> Dict[str, Any]:
        """
        Securely converts model instance to dictionary representation with type validation.

        Args:
            exclude_fields: List of field names to exclude from the output
            sanitize: Whether to sanitize sensitive information

        Returns:
            Dict containing validated and sanitized model attributes
        """
        if exclude_fields is None:
            exclude_fields = []

        # Get model inspection interface
        mapper = inspect(self.__class__)
        
        # Initialize result dictionary
        result = {}
        
        # Process all model attributes
        for column in mapper.attrs:
            # Skip excluded fields
            if column.key in exclude_fields:
                continue
                
            value = getattr(self, column.key)
            
            # Handle relationships
            if hasattr(column, 'collection_class'):
                if value is not None:
                    # Convert relationship collections to list of dicts
                    value = [
                        item.to_dict(exclude_fields=exclude_fields, sanitize=sanitize)
                        for item in value
                    ]
            elif hasattr(column, 'mapper'):
                if value is not None:
                    # Convert single relationship to dict
                    value = value.to_dict(
                        exclude_fields=exclude_fields,
                        sanitize=sanitize
                    )
            
            # Sanitize sensitive fields if required
            if sanitize and column.key.lower() in {
                'password', 'secret', 'token', 'key', 'credential'
            }:
                value = '***REDACTED***'
            
            result[column.key] = value
            
        return result

    def validate_types(self) -> bool:
        """
        Validates attribute types against model definitions.

        Returns:
            bool: True if all types are valid, False otherwise
        """
        # Get model inspection interface
        mapper = inspect(self.__class__)
        
        # Validate each column
        for column in mapper.attrs:
            if not hasattr(column, 'type'):
                continue
                
            value = getattr(self, column.key)
            if value is not None:
                # Get expected Python type from SQLAlchemy type
                expected_type = column.type.python_type
                
                # Check if value matches expected type
                if not isinstance(value, expected_type):
                    return False
                    
                # Additional validation for JSON fields
                if isinstance(column.type, JSONEncodedDict):
                    try:
                        json.dumps(value)
                    except (TypeError, ValueError):
                        return False
        
        return True

    @classmethod
    def get_relationships(cls) -> List[str]:
        """
        Returns list of relationship attribute names for the model.

        Returns:
            List[str]: Names of relationship attributes
        """
        mapper = inspect(cls)
        return [
            attr.key for attr in mapper.attrs
            if hasattr(attr, 'mapper') or hasattr(attr, 'collection_class')
        ]