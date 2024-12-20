"""
AWS KMS integration module providing secure key management operations.
Implements encryption, decryption, and key rotation with comprehensive monitoring and audit capabilities.

External Dependencies:
- boto3==1.28.0: AWS SDK for Python
- botocore==1.31.0: AWS SDK exceptions handling
"""

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from typing import Tuple, Dict, Optional
import time
import logging
from datetime import datetime, timedelta
from config.settings import Settings

# Constants
DEFAULT_KEY_SPEC = "AES_256"
CACHE_TTL = 3600  # 1 hour in seconds
MAX_RETRY_ATTEMPTS = 3
METRICS_WINDOW = 300  # 5 minutes in seconds

class KMSClient:
    """
    Client for AWS KMS operations with enhanced security features including
    key rotation, monitoring, and audit logging.
    """
    
    def __init__(self) -> None:
        """
        Initialize KMS client with AWS credentials and setup monitoring.
        Raises:
            ClientError: If KMS client initialization fails
            ValueError: If required AWS credentials are missing
        """
        self._settings = Settings()
        self._validate_credentials()
        
        # Initialize KMS client
        self._client = boto3.client(
            'kms',
            aws_access_key_id=self._settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=self._settings.AWS_SECRET_ACCESS_KEY,
            region_name=self._settings.AWS_REGION
        )
        
        # Initialize caching and metrics
        self._key_cache: Dict[str, Tuple[bytes, float]] = {}
        self._metrics: Dict[str, Dict] = {
            'generate_key': {'count': 0, 'errors': 0, 'latency': []},
            'decrypt_key': {'count': 0, 'errors': 0, 'latency': []},
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Setup logging
        self._logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Verify KMS access
        self._verify_kms_access()

    def generate_data_key(self, key_id: str, use_cache: bool = True) -> Tuple[bytes, bytes]:
        """
        Generate a new data key using KMS with monitoring and audit logging.
        
        Args:
            key_id: KMS key ID or ARN
            use_cache: Whether to use key caching
            
        Returns:
            Tuple containing (plaintext_key, encrypted_key)
            
        Raises:
            ClientError: If KMS operation fails
            ValueError: If key_id is invalid
        """
        start_time = time.time()
        
        try:
            # Check cache if enabled
            if use_cache and key_id in self._key_cache:
                key_data, cache_time = self._key_cache[key_id]
                if time.time() - cache_time < CACHE_TTL:
                    self._metrics['cache_hits'] += 1
                    return key_data, b''
            
            self._metrics['cache_misses'] += 1
            
            # Generate new data key
            response = self._client.generate_data_key(
                KeyId=key_id,
                KeySpec=DEFAULT_KEY_SPEC
            )
            
            plaintext_key = response['Plaintext']
            encrypted_key = response['CiphertextBlob']
            
            # Update cache if enabled
            if use_cache:
                self._key_cache[key_id] = (plaintext_key, time.time())
            
            # Update metrics
            self._update_metrics('generate_key', start_time)
            
            # Audit logging
            self._log_operation('generate_data_key', key_id, success=True)
            
            return plaintext_key, encrypted_key
            
        except (ClientError, BotoCoreError) as e:
            self._handle_error('generate_data_key', e, key_id)
            raise
        finally:
            # Secure cleanup of sensitive data
            del start_time
            
    def decrypt_data_key(self, encrypted_key: bytes, use_cache: bool = True) -> bytes:
        """
        Decrypt an encrypted data key using KMS with monitoring.
        
        Args:
            encrypted_key: The encrypted key to decrypt
            use_cache: Whether to use key caching
            
        Returns:
            Decrypted data key
            
        Raises:
            ClientError: If KMS operation fails
            ValueError: If encrypted_key is invalid
        """
        start_time = time.time()
        
        try:
            # Input validation
            if not encrypted_key:
                raise ValueError("Encrypted key cannot be empty")
            
            # Check cache if enabled
            cache_key = encrypted_key.hex()
            if use_cache and cache_key in self._key_cache:
                key_data, cache_time = self._key_cache[cache_key]
                if time.time() - cache_time < CACHE_TTL:
                    self._metrics['cache_hits'] += 1
                    return key_data
                    
            self._metrics['cache_misses'] += 1
            
            # Decrypt key
            response = self._client.decrypt(
                CiphertextBlob=encrypted_key
            )
            
            plaintext_key = response['Plaintext']
            
            # Update cache if enabled
            if use_cache:
                self._key_cache[cache_key] = (plaintext_key, time.time())
            
            # Update metrics
            self._update_metrics('decrypt_key', start_time)
            
            # Audit logging
            self._log_operation('decrypt_data_key', response['KeyId'], success=True)
            
            return plaintext_key
            
        except (ClientError, BotoCoreError) as e:
            self._handle_error('decrypt_data_key', e)
            raise
        finally:
            # Secure cleanup
            del start_time
            
    def rotate_keys(self) -> bool:
        """
        Implement key rotation for enhanced security.
        
        Returns:
            bool: Success status
            
        Raises:
            ClientError: If key rotation fails
        """
        try:
            # Get list of customer managed keys
            keys = self._client.list_keys()['Keys']
            
            for key in keys:
                key_id = key['KeyId']
                try:
                    # Enable automatic key rotation
                    self._client.enable_key_rotation(KeyId=key_id)
                    
                    # Clear cache for rotated keys
                    self._key_cache.clear()
                    
                    # Audit logging
                    self._log_operation('rotate_keys', key_id, success=True)
                    
                except ClientError as e:
                    if e.response['Error']['Code'] != 'AlreadyExistsException':
                        raise
                        
            return True
            
        except (ClientError, BotoCoreError) as e:
            self._handle_error('rotate_keys', e)
            raise
            
    def get_metrics(self) -> Dict:
        """
        Retrieve KMS operation metrics.
        
        Returns:
            Dict containing operation metrics
        """
        metrics = {
            'operations': {
                'generate_key': {
                    'success_rate': self._calculate_success_rate('generate_key'),
                    'average_latency': self._calculate_average_latency('generate_key')
                },
                'decrypt_key': {
                    'success_rate': self._calculate_success_rate('decrypt_key'),
                    'average_latency': self._calculate_average_latency('decrypt_key')
                }
            },
            'cache': {
                'hit_rate': self._calculate_cache_hit_rate(),
                'size': len(self._key_cache)
            }
        }
        
        return metrics
        
    def _validate_credentials(self) -> None:
        """Validate AWS credentials are present."""
        if not all([
            self._settings.AWS_ACCESS_KEY_ID,
            self._settings.AWS_SECRET_ACCESS_KEY,
            self._settings.AWS_REGION
        ]):
            raise ValueError("Missing required AWS credentials")
            
    def _verify_kms_access(self) -> None:
        """Verify KMS access and permissions."""
        try:
            self._client.list_keys(Limit=1)
        except ClientError as e:
            raise ValueError(f"KMS access verification failed: {str(e)}")
            
    def _setup_logging(self) -> None:
        """Configure audit logging."""
        self._logger.setLevel(logging.INFO)
        
    def _log_operation(self, operation: str, key_id: str, success: bool) -> None:
        """Log KMS operations for audit purposes."""
        self._logger.info(
            f"KMS operation: {operation}, KeyId: {key_id}, Success: {success}, "
            f"Timestamp: {datetime.utcnow().isoformat()}"
        )
        
    def _update_metrics(self, operation: str, start_time: float) -> None:
        """Update operation metrics."""
        latency = time.time() - start_time
        self._metrics[operation]['count'] += 1
        self._metrics[operation]['latency'].append(latency)
        
        # Trim old metrics
        cutoff_time = time.time() - METRICS_WINDOW
        self._metrics[operation]['latency'] = [
            l for l in self._metrics[operation]['latency']
            if l > cutoff_time
        ]
        
    def _handle_error(self, operation: str, error: Exception, key_id: str = None) -> None:
        """Handle and log KMS operation errors."""
        self._metrics[operation]['errors'] += 1
        self._logger.error(
            f"KMS operation failed: {operation}, Error: {str(error)}, "
            f"KeyId: {key_id}, Timestamp: {datetime.utcnow().isoformat()}"
        )
        
    def _calculate_success_rate(self, operation: str) -> float:
        """Calculate operation success rate."""
        total = self._metrics[operation]['count']
        if total == 0:
            return 100.0
        return ((total - self._metrics[operation]['errors']) / total) * 100
        
    def _calculate_average_latency(self, operation: str) -> float:
        """Calculate average operation latency."""
        latencies = self._metrics[operation]['latency']
        return sum(latencies) / len(latencies) if latencies else 0.0
        
    def _calculate_cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self._metrics['cache_hits'] + self._metrics['cache_misses']
        if total == 0:
            return 0.0
        return (self._metrics['cache_hits'] / total) * 100

def create_kms_client() -> KMSClient:
    """
    Factory function to create a KMS client instance with monitoring.
    
    Returns:
        Configured KMS client
        
    Raises:
        ValueError: If client creation fails
    """
    try:
        client = KMSClient()
        return client
    except Exception as e:
        logging.error(f"Failed to create KMS client: {str(e)}")
        raise ValueError(f"KMS client creation failed: {str(e)}")