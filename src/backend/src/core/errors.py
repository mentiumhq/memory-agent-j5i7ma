"""
Core error handling module for the Memory Agent system.

This module implements a comprehensive hierarchy of error classes with standardized error codes,
sanitized error messages, and detailed error tracking capabilities. It ensures system reliability
through proper error handling while preventing sensitive information disclosure.

Version: 1.0.0
"""

from enum import Enum, unique
from typing import Dict, Any
import uuid

# Default error constants
DEFAULT_ERROR_CODE = 1000
DEFAULT_ERROR_MESSAGE = "An unexpected error occurred"

@unique
class ErrorCode(Enum):
    """
    Enumeration of error codes organized by domain.
    
    Error code ranges:
    1000-1999: General/Validation errors
    2000-2999: Document-related errors
    3000-3999: Storage-related errors
    4000-4999: LLM-related errors
    5000-5999: Workflow-related errors
    6000-6999: Security-related errors
    """
    # General errors (1000-1999)
    UNKNOWN_ERROR = 1000
    VALIDATION_ERROR = 1001
    
    # Document errors (2000-2999)
    DOCUMENT_NOT_FOUND = 2000
    DOCUMENT_ALREADY_EXISTS = 2001
    
    # Storage errors (3000-3999)
    STORAGE_ERROR = 3000
    
    # LLM errors (4000-4999)
    LLM_ERROR = 4000
    EMBEDDING_ERROR = 4001
    
    # Workflow errors (5000-5999)
    WORKFLOW_ERROR = 5000
    
    # Security errors (6000-6999)
    AUTHENTICATION_ERROR = 6000
    AUTHORIZATION_ERROR = 6001
    RATE_LIMIT_ERROR = 6002


class MemoryAgentError(Exception):
    """
    Base exception class for Memory Agent errors.
    
    Provides core error handling functionality with standardized error details
    and sanitized error responses.
    """
    
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.UNKNOWN_ERROR, 
                 details: Dict[str, Any] = None) -> None:
        """
        Initialize the base error with message, code and sanitized details.
        
        Args:
            message: Human-readable error message
            error_code: Specific error code from ErrorCode enum
            details: Additional error details (will be sanitized)
        """
        super().__init__(message)
        
        # Validate error code
        if not isinstance(error_code, ErrorCode):
            error_code = ErrorCode.UNKNOWN_ERROR
            
        self.message = message
        self.error_code = error_code
        self.details = self._sanitize_details(details or {})
        self.correlation_id = str(uuid.uuid4())
    
    def _sanitize_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize error details to remove sensitive information.
        
        Args:
            details: Raw error details dictionary
            
        Returns:
            Sanitized dictionary with sensitive information removed
        """
        # Remove sensitive keys
        sensitive_keys = {'password', 'token', 'secret', 'key', 'credential'}
        return {k: v for k, v in details.items() 
                if not any(s in k.lower() for s in sensitive_keys)}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert error to sanitized dictionary format for API responses.
        
        Returns:
            Dictionary containing sanitized error details
        """
        return {
            'error': {
                'code': self.error_code.value,
                'message': self.message,
                'details': self.details,
                'correlation_id': self.correlation_id
            }
        }


class DocumentError(MemoryAgentError):
    """Exception class for document-related errors."""
    
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.DOCUMENT_NOT_FOUND,
                 details: Dict[str, Any] = None) -> None:
        """
        Initialize document error with domain validation.
        
        Args:
            message: Error message
            error_code: Document domain error code (2000-2999)
            details: Additional error details
        
        Raises:
            ValueError: If error code is not in document domain range
        """
        if not (2000 <= error_code.value < 3000):
            raise ValueError(f"Invalid document error code: {error_code}")
        super().__init__(message, error_code, details)


class StorageError(MemoryAgentError):
    """Exception class for storage-related errors."""
    
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.STORAGE_ERROR,
                 details: Dict[str, Any] = None) -> None:
        """
        Initialize storage error with domain validation.
        
        Args:
            message: Error message
            error_code: Storage domain error code (3000-3999)
            details: Additional error details
            
        Raises:
            ValueError: If error code is not in storage domain range
        """
        if not (3000 <= error_code.value < 4000):
            raise ValueError(f"Invalid storage error code: {error_code}")
        super().__init__(message, error_code, details)


class LLMError(MemoryAgentError):
    """Exception class for LLM-related errors."""
    
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.LLM_ERROR,
                 details: Dict[str, Any] = None) -> None:
        """
        Initialize LLM error with domain validation.
        
        Args:
            message: Error message
            error_code: LLM domain error code (4000-4999)
            details: Additional error details
            
        Raises:
            ValueError: If error code is not in LLM domain range
        """
        if not (4000 <= error_code.value < 5000):
            raise ValueError(f"Invalid LLM error code: {error_code}")
        super().__init__(message, error_code, details)


class WorkflowError(MemoryAgentError):
    """Exception class for workflow-related errors."""
    
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.WORKFLOW_ERROR,
                 details: Dict[str, Any] = None) -> None:
        """
        Initialize workflow error with domain validation.
        
        Args:
            message: Error message
            error_code: Workflow domain error code (5000-5999)
            details: Additional error details
            
        Raises:
            ValueError: If error code is not in workflow domain range
        """
        if not (5000 <= error_code.value < 6000):
            raise ValueError(f"Invalid workflow error code: {error_code}")
        super().__init__(message, error_code, details)


class SecurityError(MemoryAgentError):
    """Exception class for security-related errors."""
    
    def __init__(self, message: str, error_code: ErrorCode = ErrorCode.AUTHENTICATION_ERROR,
                 details: Dict[str, Any] = None) -> None:
        """
        Initialize security error with domain validation.
        
        Args:
            message: Error message
            error_code: Security domain error code (6000-6999)
            details: Additional error details
            
        Raises:
            ValueError: If error code is not in security domain range
        """
        if not (6000 <= error_code.value < 7000):
            raise ValueError(f"Invalid security error code: {error_code}")
        
        # Apply additional sanitization for security errors
        if details:
            details = self._sanitize_security_details(details)
            
        super().__init__(message, error_code, details)
    
    def _sanitize_security_details(self, details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply additional sanitization for security-related details.
        
        Args:
            details: Raw security error details
            
        Returns:
            Heavily sanitized dictionary for security errors
        """
        # Only allow specific keys for security errors
        allowed_keys = {'request_id', 'timestamp', 'source'}
        return {k: v for k, v in details.items() if k in allowed_keys}