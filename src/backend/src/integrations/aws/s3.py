"""
AWS S3 integration module providing secure, versioned document storage with SSE-KMS encryption,
comprehensive telemetry, and enhanced error handling for the Memory Agent system.

External Dependencies:
- boto3==1.28+: AWS S3 SDK
- botocore==1.31+: AWS SDK core functionality
- opentelemetry-api==1.20.0: Distributed tracing

Version: 1.0.0
"""

import asyncio
from functools import wraps
import boto3
from botocore.exceptions import (
    ClientError,
    ConnectionError,
    EndpointConnectionError,
    ParamValidationError,
)
from typing import Dict, Optional, Tuple, Any

from config.settings import Settings
from core.errors import StorageError, ErrorCode
from core.telemetry import create_tracer
from config.logging import get_logger

# Initialize logger and tracer
LOGGER = get_logger(__name__)
TRACER = create_tracer('s3')

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1.0

def retry(max_attempts: int = MAX_RETRIES, delay: float = RETRY_DELAY):
    """
    Retry decorator with exponential backoff for S3 operations.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except (ConnectionError, EndpointConnectionError) as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        wait_time = delay * (2 ** attempt)
                        LOGGER.warning(
                            f"S3 operation failed, retrying in {wait_time}s",
                            extra={
                                "attempt": attempt + 1,
                                "max_attempts": max_attempts,
                                "operation": func.__name__
                            }
                        )
                        await asyncio.sleep(wait_time)
                    continue
            raise StorageError(
                f"S3 operation failed after {max_attempts} attempts: {str(last_exception)}",
                ErrorCode.STORAGE_ERROR,
                {"last_error": str(last_exception)}
            )
        return wrapper
    return decorator

class S3Client:
    """
    Asynchronous S3 client implementing secure document storage operations with
    SSE-KMS encryption, comprehensive telemetry, and enhanced error handling.
    """
    
    def __init__(self, settings: Settings):
        """
        Initialize S3 client with credentials, KMS configuration, and verify bucket accessibility.
        
        Args:
            settings: Application settings instance
            
        Raises:
            StorageError: If bucket initialization fails
        """
        try:
            # Initialize S3 client
            self._client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            
            self._bucket_name = settings.S3_BUCKET_NAME
            self._kms_key_id = settings.KMS_KEY_ID
            
            # Configure SSE-KMS encryption
            self._encryption_config = {
                'ServerSideEncryption': 'aws:kms',
                'SSEKMSKeyId': self._kms_key_id
            }
            
            # Verify bucket exists and is accessible
            self._verify_bucket()
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise StorageError(
                f"Failed to initialize S3 client: {str(e)}",
                ErrorCode.STORAGE_ERROR,
                {"error_code": error_code}
            )
    
    def _verify_bucket(self) -> None:
        """
        Verify S3 bucket exists, is accessible, and has versioning enabled.
        
        Raises:
            StorageError: If bucket verification fails
        """
        try:
            # Check bucket exists
            self._client.head_bucket(Bucket=self._bucket_name)
            
            # Verify versioning is enabled
            versioning = self._client.get_bucket_versioning(
                Bucket=self._bucket_name
            )
            if versioning.get('Status') != 'Enabled':
                raise StorageError(
                    "Bucket versioning not enabled",
                    ErrorCode.STORAGE_ERROR
                )
                
            # Verify encryption configuration
            encryption = self._client.get_bucket_encryption(
                Bucket=self._bucket_name
            )
            if not encryption.get('ServerSideEncryptionConfiguration'):
                raise StorageError(
                    "Bucket encryption not configured",
                    ErrorCode.STORAGE_ERROR
                )
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise StorageError(
                f"Bucket verification failed: {str(e)}",
                ErrorCode.STORAGE_ERROR,
                {"error_code": error_code}
            )

    @TRACER.start_as_current_span('store_document')
    @retry(max_attempts=MAX_RETRIES, delay=RETRY_DELAY)
    async def store_document(
        self,
        document_id: str,
        content: bytes,
        metadata: Dict[str, Any]
    ) -> str:
        """
        Store document in S3 with versioning and SSE-KMS encryption.
        
        Args:
            document_id: Unique document identifier
            content: Document content as bytes
            metadata: Document metadata dictionary
            
        Returns:
            str: S3 version ID of stored document
            
        Raises:
            StorageError: If document storage fails
        """
        try:
            # Generate S3 key
            s3_key = f"documents/{document_id}"
            
            # Store document with encryption and versioning
            response = await asyncio.to_thread(
                self._client.put_object,
                Bucket=self._bucket_name,
                Key=s3_key,
                Body=content,
                Metadata=metadata,
                **self._encryption_config
            )
            
            version_id = response.get('VersionId')
            if not version_id:
                raise StorageError(
                    "Version ID not returned for stored document",
                    ErrorCode.STORAGE_ERROR
                )
            
            LOGGER.info(
                "Document stored successfully",
                extra={
                    "document_id": document_id,
                    "version_id": version_id,
                    "size_bytes": len(content)
                }
            )
            
            return version_id
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise StorageError(
                f"Failed to store document: {str(e)}",
                ErrorCode.STORAGE_ERROR,
                {"error_code": error_code}
            )

    @TRACER.start_as_current_span('retrieve_document')
    @retry(max_attempts=MAX_RETRIES, delay=RETRY_DELAY)
    async def retrieve_document(
        self,
        document_id: str,
        version_id: Optional[str] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Retrieve document from S3 by ID with optional version.
        
        Args:
            document_id: Document identifier
            version_id: Optional specific version to retrieve
            
        Returns:
            Tuple containing document content and metadata
            
        Raises:
            StorageError: If document retrieval fails
        """
        try:
            # Generate S3 key
            s3_key = f"documents/{document_id}"
            
            # Configure retrieval parameters
            get_params = {
                'Bucket': self._bucket_name,
                'Key': s3_key
            }
            if version_id:
                get_params['VersionId'] = version_id
            
            # Retrieve document
            response = await asyncio.to_thread(
                self._client.get_object,
                **get_params
            )
            
            # Verify encryption
            if response.get('ServerSideEncryption') != 'aws:kms':
                raise StorageError(
                    "Retrieved document not encrypted with KMS",
                    ErrorCode.STORAGE_ERROR
                )
            
            content = await asyncio.to_thread(
                response['Body'].read
            )
            metadata = response.get('Metadata', {})
            
            LOGGER.info(
                "Document retrieved successfully",
                extra={
                    "document_id": document_id,
                    "version_id": response.get('VersionId'),
                    "size_bytes": len(content)
                }
            )
            
            return content, metadata
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'NoSuchKey':
                raise StorageError(
                    f"Document not found: {document_id}",
                    ErrorCode.DOCUMENT_NOT_FOUND,
                    {"document_id": document_id}
                )
            raise StorageError(
                f"Failed to retrieve document: {str(e)}",
                ErrorCode.STORAGE_ERROR,
                {"error_code": error_code}
            )

    @TRACER.start_as_current_span('delete_document')
    @retry(max_attempts=MAX_RETRIES, delay=RETRY_DELAY)
    async def delete_document(self, document_id: str) -> bool:
        """
        Delete document from S3 with versioning support.
        
        Args:
            document_id: Document identifier
            
        Returns:
            bool: True if deletion successful
            
        Raises:
            StorageError: If document deletion fails
        """
        try:
            # Generate S3 key
            s3_key = f"documents/{document_id}"
            
            # Delete document (creates delete marker with versioning)
            await asyncio.to_thread(
                self._client.delete_object,
                Bucket=self._bucket_name,
                Key=s3_key
            )
            
            LOGGER.info(
                "Document deleted successfully",
                extra={"document_id": document_id}
            )
            
            return True
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            raise StorageError(
                f"Failed to delete document: {str(e)}",
                ErrorCode.STORAGE_ERROR,
                {"error_code": error_code}
            )

# Export public interface
__all__ = ['S3Client']