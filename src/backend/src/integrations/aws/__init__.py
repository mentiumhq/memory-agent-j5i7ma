"""
AWS integration package initialization module for the Memory Agent service.
Provides centralized access to AWS services with comprehensive security monitoring.

External Dependencies:
- boto3==1.28.0: AWS SDK for Python
- botocore==1.31.0: AWS SDK core functionality

Version: 1.0.0
"""

from typing import Dict, Any, Optional

from .s3 import S3Client
from .kms import KMSClient, create_kms_client

# Package version
__version__ = "1.0.0"

# Export public interface
__all__ = [
    "S3Client",
    "KMSClient", 
    "create_kms_client",
    "initialize_aws_clients",
    "get_aws_metrics"
]

# Global client instances
_s3_client: Optional[S3Client] = None
_kms_client: Optional[KMSClient] = None

def initialize_aws_clients(settings: Any) -> Dict[str, Any]:
    """
    Initialize AWS service clients with proper configuration and monitoring.
    
    Args:
        settings: Application settings instance containing AWS credentials
        
    Returns:
        Dict containing initialized AWS clients
        
    Raises:
        ValueError: If client initialization fails
        RuntimeError: If AWS credentials are invalid
    """
    global _s3_client, _kms_client
    
    try:
        # Initialize KMS client first for encryption support
        _kms_client = create_kms_client()
        
        # Initialize S3 client with KMS integration
        _s3_client = S3Client(settings)
        
        return {
            "s3": _s3_client,
            "kms": _kms_client
        }
        
    except Exception as e:
        # Clean up any partially initialized clients
        _cleanup_clients()
        raise RuntimeError(f"Failed to initialize AWS clients: {str(e)}")

def get_aws_metrics() -> Dict[str, Any]:
    """
    Retrieve comprehensive metrics from AWS service clients.
    
    Returns:
        Dict containing metrics from all AWS services
        
    Raises:
        RuntimeError: If clients are not initialized
    """
    if not all([_s3_client, _kms_client]):
        raise RuntimeError("AWS clients not initialized")
        
    try:
        metrics = {
            "s3": {
                "operations": {
                    "store": _s3_client._metrics.get("store_document", {}),
                    "retrieve": _s3_client._metrics.get("retrieve_document", {}),
                    "delete": _s3_client._metrics.get("delete_document", {})
                }
            },
            "kms": _kms_client.get_metrics()
        }
        
        return metrics
        
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve AWS metrics: {str(e)}")

def _cleanup_clients() -> None:
    """Clean up AWS client instances on initialization failure."""
    global _s3_client, _kms_client
    
    _s3_client = None
    _kms_client = None