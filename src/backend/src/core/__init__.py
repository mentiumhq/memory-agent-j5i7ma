"""
Core package initializer for the Memory Agent system.

This module exposes essential functionality, error classes, utilities, and authentication
components for the Memory Agent system. It provides a clean public API for the core module
while maintaining proper encapsulation and security.

Version: 1.0.0
Author: Memory Agent Team
License: MIT
"""

# Version information
__version__ = "1.0.0"
__author__ = "Memory Agent Team"
__license__ = "MIT"

# Import error classes
from .errors import (
    MemoryAgentError,
    DocumentError,
    StorageError,
    WorkflowError,
    LLMError,
    SecurityError as ValidationError  # Aliased for better semantic meaning
)

# Import core utilities
from .utils import (
    generate_uuid,
    get_current_timestamp,
    parse_timestamp,
    sanitize_dict,
    JsonSerializer
)

# Import authentication components
from .auth import (
    TokenPayload,
    create_access_token,
    verify_token,
    check_permissions,
    ROLE_PERMISSIONS
)

# Define public API
__all__ = [
    # Error classes
    "MemoryAgentError",
    "DocumentError",
    "StorageError",
    "WorkflowError",
    "LLMError",
    "ValidationError",
    
    # Core utilities
    "generate_uuid",
    "get_current_timestamp",
    "parse_timestamp",
    "sanitize_dict",
    "JsonSerializer",
    
    # Authentication components
    "TokenPayload",
    "create_access_token",
    "verify_token",
    "check_permissions",
    "ROLE_PERMISSIONS",
    
    # Version info
    "__version__",
    "__author__",
    "__license__"
]

# Prevent direct attribute access to internal modules
del errors
del utils
del auth