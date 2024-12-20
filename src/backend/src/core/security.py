"""
Core security module for the Memory Agent system.
Provides centralized security services including authentication, authorization,
encryption, and secure token management with comprehensive validation and audit logging.

External Dependencies:
- ssl==builtin: TLS/mTLS configuration
- secrets==builtin: Secure random number generation
- typing==builtin: Type hints
- logging==builtin: Security audit logging

Version: 1.0.0
"""

import ssl
import secrets
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta

from core.encryption import DocumentEncryption
from core.auth import TokenPayload, create_access_token, verify_token, check_permissions
from integrations.aws.kms import KMSClient
from core.errors import SecurityError, ErrorCode

# Security configuration constants
DEFAULT_SSL_CONTEXT = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH, cafile='ca.pem')
TOKEN_LENGTH = 32  # Length for secure random tokens
MAX_AUTH_ATTEMPTS = 3  # Maximum authentication attempts before rate limiting
KEY_ROTATION_INTERVAL = timedelta(days=90)  # Key rotation interval

class SecurityManager:
    """
    Central security manager that coordinates authentication, authorization,
    encryption operations with comprehensive validation and audit logging.
    """
    
    def __init__(self, encryption_client: DocumentEncryption, kms_client: KMSClient) -> None:
        """
        Initialize security manager with required clients and validation.
        
        Args:
            encryption_client: Document encryption client
            kms_client: KMS client for key management
            
        Raises:
            ValueError: If clients are invalid
        """
        if not isinstance(encryption_client, DocumentEncryption):
            raise ValueError("Invalid encryption client")
        if not isinstance(kms_client, KMSClient):
            raise ValueError("Invalid KMS client")
            
        self._encryption_client = encryption_client
        self._kms_client = kms_client
        self._ssl_context = self._configure_ssl_context()
        self._logger = logging.getLogger(__name__)
        self._auth_attempts = 0
        
        # Initialize logging
        self._setup_logging()
        
        # Log initialization
        self._logger.info(
            "SecurityManager initialized",
            extra={"timestamp": datetime.utcnow().isoformat()}
        )

    def authenticate_request(self, token: str) -> TokenPayload:
        """
        Authenticate incoming request using JWT token with rate limiting and audit logging.
        
        Args:
            token: JWT token string
            
        Returns:
            TokenPayload: Validated token payload
            
        Raises:
            SecurityError: If authentication fails
        """
        try:
            # Check rate limiting
            if self._auth_attempts >= MAX_AUTH_ATTEMPTS:
                raise SecurityError(
                    "Too many authentication attempts",
                    ErrorCode.RATE_LIMIT_ERROR
                )
            
            # Validate token format
            if not token or not isinstance(token, str):
                raise SecurityError(
                    "Invalid token format",
                    ErrorCode.AUTHENTICATION_ERROR
                )
            
            # Verify and decode token
            payload = verify_token(token)
            
            # Reset auth attempts on success
            self._auth_attempts = 0
            
            # Log successful authentication
            self._logger.info(
                "Authentication successful",
                extra={
                    "subject": payload.sub,
                    "role": payload.role,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return payload
            
        except SecurityError:
            # Increment auth attempts on failure
            self._auth_attempts += 1
            raise
        except Exception as e:
            self._auth_attempts += 1
            raise SecurityError(
                "Authentication failed",
                ErrorCode.AUTHENTICATION_ERROR,
                {"error": str(e)}
            )

    def authorize_operation(self, role: str, operation: str) -> bool:
        """
        Check if user has permission for operation with comprehensive validation.
        
        Args:
            role: User role
            operation: Operation to check
            
        Returns:
            bool: True if authorized, False otherwise
            
        Raises:
            SecurityError: If authorization check fails
        """
        try:
            # Validate input parameters
            if not role or not operation:
                raise SecurityError(
                    "Invalid authorization parameters",
                    ErrorCode.AUTHORIZATION_ERROR
                )
            
            # Check permissions
            is_authorized = check_permissions(role, operation)
            
            # Log authorization check
            self._logger.info(
                "Authorization check",
                extra={
                    "role": role,
                    "operation": operation,
                    "authorized": is_authorized,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            return is_authorized
            
        except SecurityError:
            raise
        except Exception as e:
            raise SecurityError(
                "Authorization failed",
                ErrorCode.AUTHORIZATION_ERROR,
                {"error": str(e)}
            )

    def encrypt_content(self, content: bytes) -> Tuple[bytes, bytes]:
        """
        Encrypt document content securely with key rotation support.
        
        Args:
            content: Content to encrypt
            
        Returns:
            Tuple containing (encrypted_content, encrypted_key)
            
        Raises:
            SecurityError: If encryption fails
        """
        try:
            # Validate input
            if not content:
                raise SecurityError(
                    "Empty content for encryption",
                    ErrorCode.VALIDATION_ERROR
                )
            
            # Check key rotation
            self._check_key_rotation()
            
            # Encrypt content
            encrypted_content, encrypted_key, _ = self._encryption_client.encrypt_document(content)
            
            # Log encryption operation
            self._logger.info(
                "Content encrypted successfully",
                extra={"timestamp": datetime.utcnow().isoformat()}
            )
            
            return encrypted_content, encrypted_key
            
        except Exception as e:
            raise SecurityError(
                "Encryption failed",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def decrypt_content(self, encrypted_content: bytes, encrypted_key: bytes) -> bytes:
        """
        Decrypt encrypted document content with validation.
        
        Args:
            encrypted_content: Encrypted content
            encrypted_key: Encrypted key
            
        Returns:
            bytes: Decrypted content
            
        Raises:
            SecurityError: If decryption fails
        """
        try:
            # Validate input
            if not encrypted_content or not encrypted_key:
                raise SecurityError(
                    "Invalid encrypted data",
                    ErrorCode.VALIDATION_ERROR
                )
            
            # Decrypt content
            decrypted_content = self._encryption_client.decrypt_document(
                encrypted_content,
                encrypted_key,
                {}  # Empty metadata for now
            )
            
            # Log decryption operation
            self._logger.info(
                "Content decrypted successfully",
                extra={"timestamp": datetime.utcnow().isoformat()}
            )
            
            return decrypted_content
            
        except Exception as e:
            raise SecurityError(
                "Decryption failed",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def get_ssl_context(self) -> ssl.SSLContext:
        """
        Get configured SSL context for TLS with strong cipher suites.
        
        Returns:
            SSLContext: Configured SSL context
            
        Raises:
            SecurityError: If SSL configuration fails
        """
        try:
            return self._ssl_context
        except Exception as e:
            raise SecurityError(
                "SSL context error",
                ErrorCode.AUTHENTICATION_ERROR,
                {"error": str(e)}
            )

    def rotate_security_keys(self) -> bool:
        """
        Perform security key rotation.
        
        Returns:
            bool: Success status
            
        Raises:
            SecurityError: If key rotation fails
        """
        try:
            # Rotate KMS keys
            self._kms_client.rotate_keys()
            
            # Log key rotation
            self._logger.info(
                "Security keys rotated successfully",
                extra={"timestamp": datetime.utcnow().isoformat()}
            )
            
            return True
            
        except Exception as e:
            raise SecurityError(
                "Key rotation failed",
                ErrorCode.STORAGE_ERROR,
                {"error": str(e)}
            )

    def _configure_ssl_context(self) -> ssl.SSLContext:
        """Configure SSL context with strong security settings."""
        context = DEFAULT_SSL_CONTEXT
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        return context

    def _setup_logging(self) -> None:
        """Configure security audit logging."""
        self._logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

    def _check_key_rotation(self) -> None:
        """Check if key rotation is needed."""
        # Implementation would check last rotation timestamp
        # and trigger rotation if interval exceeded
        pass

def create_security_manager(kms_key_id: str) -> SecurityManager:
    """
    Factory function to create security manager instance with validation.
    
    Args:
        kms_key_id: KMS key ID for encryption
        
    Returns:
        SecurityManager: Configured security manager
        
    Raises:
        ValueError: If creation fails
    """
    try:
        # Create KMS client
        kms_client = KMSClient()
        
        # Create encryption client
        encryption_client = DocumentEncryption(
            kms_client=kms_client,
            key_id=kms_key_id
        )
        
        # Create and return security manager
        return SecurityManager(
            encryption_client=encryption_client,
            kms_client=kms_client
        )
        
    except Exception as e:
        raise ValueError(f"Failed to create security manager: {str(e)}")

def generate_secure_token(length: Optional[int] = None) -> str:
    """
    Generate cryptographically secure random token with validation.
    
    Args:
        length: Optional token length (defaults to TOKEN_LENGTH)
        
    Returns:
        str: Secure random token
        
    Raises:
        ValueError: If length is invalid
    """
    if length is not None and length < 16:
        raise ValueError("Token length must be at least 16 characters")
        
    token_length = length or TOKEN_LENGTH
    return secrets.token_urlsafe(token_length)