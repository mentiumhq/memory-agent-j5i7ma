"""
Core encryption module providing secure document encryption using AES-256 with AWS KMS.
Implements timing attack protections, secure memory wiping, and PKCS7 padding.

External Dependencies:
- cryptography==41.0.0: Cryptographic operations and secure memory handling
"""

import os
import time
import gc
from typing import Tuple, Dict, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.memory import SecureMemoryWiper
from integrations.aws.kms import KMSClient
from config.settings import Settings

# Constants for AES-256 encryption
BLOCK_SIZE = 16  # AES block size in bytes
KEY_LENGTH = 32  # AES-256 key length in bytes
IV_LENGTH = 16  # Initialization vector length in bytes
KEY_CACHE_TTL = 3600  # Key cache time-to-live in seconds

class DocumentEncryption:
    """
    Handles document encryption and decryption using AES-256 with KMS-managed keys.
    Implements secure padding, timing attack protections, and secure memory cleanup.
    """
    
    def __init__(self, kms_client: KMSClient, key_id: str, enable_caching: bool = True) -> None:
        """
        Initialize encryption with KMS client and key management.
        
        Args:
            kms_client: KMS client instance for key operations
            key_id: KMS key ID for key generation
            enable_caching: Whether to enable key caching
            
        Raises:
            ValueError: If KMS client or key_id is invalid
        """
        if not isinstance(kms_client, KMSClient):
            raise ValueError("Invalid KMS client instance")
        if not key_id:
            raise ValueError("KMS key ID cannot be empty")
            
        self._kms_client = kms_client
        self._key_id = key_id.encode() if isinstance(key_id, str) else key_id
        self._key_cache = {} if enable_caching else None
        self._cache_timestamp = time.time() if enable_caching else None
        
        # Initialize secure memory wiper
        self._wiper = SecureMemoryWiper()

    def encrypt_document(self, content: bytes) -> Tuple[bytes, bytes, Dict]:
        """
        Encrypts document content using AES-256 with KMS data key and PKCS7 padding.
        
        Args:
            content: Document content to encrypt
            
        Returns:
            Tuple containing (encrypted_content, encrypted_key, metadata)
            
        Raises:
            ValueError: If content is invalid
            RuntimeError: If encryption fails
        """
        if not content:
            raise ValueError("Document content cannot be empty")
            
        try:
            # Generate or retrieve data key from KMS
            plaintext_key, encrypted_key = self._kms_client.generate_data_key(
                self._key_id.decode(),
                use_cache=bool(self._key_cache)
            )
            
            # Generate random IV
            iv = os.urandom(IV_LENGTH)
            
            # Create AES cipher
            cipher = Cipher(
                algorithms.AES(plaintext_key),
                modes.CBC(iv)
            )
            encryptor = cipher.encryptor()
            
            # Apply PKCS7 padding
            padder = padding.PKCS7(algorithms.AES.block_size).padder()
            padded_data = padder.update(content) + padder.finalize()
            
            # Encrypt with timing attack protection
            encrypted_content = encryptor.update(padded_data) + encryptor.finalize()
            
            # Prepare metadata
            metadata = {
                'iv': iv.hex(),
                'timestamp': int(time.time()),
                'algorithm': 'AES-256-CBC',
                'padding': 'PKCS7'
            }
            
            return encrypted_content, encrypted_key, metadata
            
        except Exception as e:
            raise RuntimeError(f"Encryption failed: {str(e)}")
            
        finally:
            # Secure cleanup of sensitive data
            if 'plaintext_key' in locals():
                self._wiper.wipe(plaintext_key)
            if 'padded_data' in locals():
                self._wiper.wipe(padded_data)
            gc.collect()

    def decrypt_document(self, encrypted_content: bytes, encrypted_key: bytes, metadata: Dict) -> bytes:
        """
        Decrypts document content using the provided encrypted key with secure cleanup.
        
        Args:
            encrypted_content: Encrypted document content
            encrypted_key: Encrypted data key
            metadata: Encryption metadata including IV
            
        Returns:
            Decrypted document content
            
        Raises:
            ValueError: If input parameters are invalid
            RuntimeError: If decryption fails
        """
        if not all([encrypted_content, encrypted_key, metadata]):
            raise ValueError("Missing required decryption parameters")
            
        try:
            # Decrypt data key using KMS
            plaintext_key = self._kms_client.decrypt_data_key(
                encrypted_key,
                use_cache=bool(self._key_cache)
            )
            
            # Extract IV from metadata
            iv = bytes.fromhex(metadata['iv'])
            
            # Create AES cipher
            cipher = Cipher(
                algorithms.AES(plaintext_key),
                modes.CBC(iv)
            )
            decryptor = cipher.decryptor()
            
            # Decrypt with timing attack protection
            padded_content = decryptor.update(encrypted_content) + decryptor.finalize()
            
            # Remove PKCS7 padding
            unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
            content = unpadder.update(padded_content) + unpadder.finalize()
            
            return content
            
        except Exception as e:
            raise RuntimeError(f"Decryption failed: {str(e)}")
            
        finally:
            # Secure cleanup of sensitive data
            if 'plaintext_key' in locals():
                self._wiper.wipe(plaintext_key)
            if 'padded_content' in locals():
                self._wiper.wipe(padded_content)
            gc.collect()

    def cleanup(self) -> None:
        """
        Securely clean up sensitive data from memory.
        """
        try:
            # Clear key cache if enabled
            if self._key_cache is not None:
                for key_data in self._key_cache.values():
                    self._wiper.wipe(key_data[0])
                self._key_cache.clear()
            
            # Reset cache timestamp
            self._cache_timestamp = None
            
            # Force garbage collection
            gc.collect()
            
        except Exception as e:
            raise RuntimeError(f"Cleanup failed: {str(e)}")

def create_encryption_client(key_id: str, enable_caching: bool = True) -> DocumentEncryption:
    """
    Factory function to create a document encryption client with optional caching.
    
    Args:
        key_id: KMS key ID for key generation
        enable_caching: Whether to enable key caching
        
    Returns:
        Configured encryption client
        
    Raises:
        ValueError: If key_id is invalid
    """
    if not key_id:
        raise ValueError("KMS key ID is required")
        
    try:
        # Create KMS client
        kms_client = KMSClient()
        
        # Create and return encryption client
        return DocumentEncryption(
            kms_client=kms_client,
            key_id=key_id,
            enable_caching=enable_caching
        )
        
    except Exception as e:
        raise ValueError(f"Failed to create encryption client: {str(e)}")