"""
Core utility functions for the Memory Agent system.

This module provides essential utility functions for common operations across the system,
including secure UUID generation, timestamp handling, JSON serialization, and data validation.
All functions implement comprehensive error handling and security measures.

Version: 1.0.0
"""

import uuid
from datetime import datetime, timezone
import json
from typing import Dict, Any, Optional, Union, List
import threading
from .errors import MemoryAgentError, ErrorCode

# Constants for timestamp formatting
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"

# Secure JSON serialization settings
JSON_DUMPS_KWARGS = {
    "ensure_ascii": False,
    "allow_nan": False,
    "indent": 2,
    "separators": (",", ":"),
    "sort_keys": True
}

# Safety limits for recursive operations
MAX_JSON_DEPTH = 100
SANITIZE_MAX_DEPTH = 50

def generate_uuid() -> str:
    """
    Generate a cryptographically secure UUID4 string.
    
    Returns:
        str: Validated UUID string in standard format
        
    Raises:
        MemoryAgentError: If UUID generation fails
    """
    try:
        new_uuid = uuid.uuid4()
        # Validate UUID format
        uuid.UUID(str(new_uuid))
        return str(new_uuid)
    except Exception as e:
        raise MemoryAgentError(
            "Failed to generate UUID",
            ErrorCode.VALIDATION_ERROR,
            {"original_error": str(e)}
        )

def get_current_timestamp() -> str:
    """
    Get current UTC timestamp in ISO 8601 format with microsecond precision.
    
    Returns:
        str: ISO 8601 formatted UTC timestamp
        
    Raises:
        MemoryAgentError: If timestamp formatting fails
    """
    try:
        # Get current UTC time with timezone awareness
        current_time = datetime.now(timezone.utc)
        timestamp = current_time.strftime(DATETIME_FORMAT)
        
        # Validate format
        datetime.strptime(timestamp, DATETIME_FORMAT)
        return timestamp
    except Exception as e:
        raise MemoryAgentError(
            "Failed to generate timestamp",
            ErrorCode.VALIDATION_ERROR,
            {"original_error": str(e)}
        )

def parse_timestamp(timestamp: str) -> datetime:
    """
    Parse ISO 8601 formatted timestamp string to timezone-aware datetime.
    
    Args:
        timestamp: ISO 8601 formatted timestamp string
        
    Returns:
        datetime: Timezone-aware datetime object
        
    Raises:
        MemoryAgentError: If timestamp parsing fails
    """
    try:
        # Parse timestamp and ensure timezone awareness
        dt = datetime.strptime(timestamp, DATETIME_FORMAT)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception as e:
        raise MemoryAgentError(
            "Failed to parse timestamp",
            ErrorCode.VALIDATION_ERROR,
            {"timestamp": timestamp, "original_error": str(e)}
        )

def sanitize_dict(data: Dict[str, Any], depth: Optional[int] = None) -> Dict[str, Any]:
    """
    Recursively sanitize dictionary by removing None values and converting datetime objects.
    
    Args:
        data: Dictionary to sanitize
        depth: Current recursion depth (internal use)
        
    Returns:
        Dict[str, Any]: Sanitized dictionary
        
    Raises:
        MemoryAgentError: If sanitization fails or max depth exceeded
    """
    if not isinstance(data, dict):
        raise MemoryAgentError(
            "Input must be a dictionary",
            ErrorCode.VALIDATION_ERROR,
            {"type": str(type(data))}
        )
    
    if depth is None:
        depth = 0
    elif depth > SANITIZE_MAX_DEPTH:
        raise MemoryAgentError(
            "Maximum recursion depth exceeded",
            ErrorCode.VALIDATION_ERROR,
            {"max_depth": SANITIZE_MAX_DEPTH}
        )
    
    try:
        result = {}
        for key, value in data.items():
            # Skip None values
            if value is None:
                continue
                
            # Convert datetime objects to ISO format
            if isinstance(value, datetime):
                result[key] = value.strftime(DATETIME_FORMAT)
            # Recursively process nested dictionaries
            elif isinstance(value, dict):
                result[key] = sanitize_dict(value, depth + 1)
            # Process lists/tuples
            elif isinstance(value, (list, tuple)):
                result[key] = [
                    sanitize_dict(item, depth + 1) if isinstance(item, dict)
                    else item
                    for item in value
                ]
            else:
                result[key] = value
                
        return result
    except Exception as e:
        raise MemoryAgentError(
            "Failed to sanitize dictionary",
            ErrorCode.VALIDATION_ERROR,
            {"original_error": str(e)}
        )

class JsonSerializer:
    """
    Thread-safe utility class for consistent and secure JSON serialization.
    
    Provides methods for serializing and deserializing JSON with consistent formatting,
    depth checking, and thread safety.
    """
    
    def __init__(
        self,
        dumps_kwargs: Optional[Dict[str, Any]] = None,
        max_depth: Optional[int] = None
    ):
        """
        Initialize serializer with secure default settings.
        
        Args:
            dumps_kwargs: Optional custom JSON dumps arguments
            max_depth: Optional custom maximum parsing depth
        """
        self._dumps_kwargs = {**JSON_DUMPS_KWARGS, **(dumps_kwargs or {})}
        self._max_depth = max_depth or MAX_JSON_DEPTH
        self._lock = threading.Lock()
        
    def _check_depth(self, obj: Any, current_depth: int = 0) -> None:
        """
        Check object depth to prevent stack overflow attacks.
        
        Args:
            obj: Object to check
            current_depth: Current recursion depth
            
        Raises:
            MemoryAgentError: If maximum depth is exceeded
        """
        if current_depth > self._max_depth:
            raise MemoryAgentError(
                "Maximum JSON depth exceeded",
                ErrorCode.VALIDATION_ERROR,
                {"max_depth": self._max_depth}
            )
            
        if isinstance(obj, dict):
            for value in obj.values():
                self._check_depth(value, current_depth + 1)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                self._check_depth(item, current_depth + 1)
    
    def dumps(self, obj: Any) -> str:
        """
        Securely serialize object to JSON string with depth checking.
        
        Args:
            obj: Object to serialize
            
        Returns:
            str: Securely formatted JSON string
            
        Raises:
            MemoryAgentError: If serialization fails
        """
        try:
            with self._lock:
                # Check object depth
                self._check_depth(obj)
                
                # Handle datetime objects
                def default(o):
                    if isinstance(o, datetime):
                        return o.strftime(DATETIME_FORMAT)
                    raise TypeError(f"Object of type {type(o)} is not JSON serializable")
                
                return json.dumps(obj, default=default, **self._dumps_kwargs)
        except Exception as e:
            raise MemoryAgentError(
                "Failed to serialize JSON",
                ErrorCode.VALIDATION_ERROR,
                {"original_error": str(e)}
            )
    
    def loads(self, json_str: str) -> Any:
        """
        Securely deserialize JSON string to object with validation.
        
        Args:
            json_str: JSON string to deserialize
            
        Returns:
            Any: Validated deserialized object
            
        Raises:
            MemoryAgentError: If deserialization fails
        """
        if not isinstance(json_str, str):
            raise MemoryAgentError(
                "Input must be a string",
                ErrorCode.VALIDATION_ERROR,
                {"type": str(type(json_str))}
            )
            
        try:
            with self._lock:
                obj = json.loads(json_str)
                # Validate parsed object depth
                self._check_depth(obj)
                return obj
        except Exception as e:
            raise MemoryAgentError(
                "Failed to deserialize JSON",
                ErrorCode.VALIDATION_ERROR,
                {"original_error": str(e)}
            )