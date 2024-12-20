"""
Root initialization module for the Memory Agent's integration packages.
Provides centralized access to external service integrations including AWS services (S3, KMS),
LLM services (OpenAI), and Temporal workflow orchestration.

External Dependencies:
- boto3==1.28.0: AWS SDK for Python
- openai==1.0.0: OpenAI API client
- temporalio==1.0.0: Temporal workflow orchestration
"""

from typing import Dict, Any

# Import AWS integrations
from .aws import S3Client, KMSClient

# Import LLM integrations
from .llm import OpenAIClient, DEFAULT_MODEL, MAX_TOKENS_GPT4, MAX_TOKENS_GPT35

# Import Temporal integrations
from .temporal import TemporalClient, TemporalWorker

# Package version
__version__ = "1.0.0"

# Package maintainers
__maintainers__ = ["Memory Agent Team"]

# Package documentation
__doc__ = """
Memory Agent Integration Package
==============================

Provides enterprise-grade integrations with external services:

AWS Services:
- S3: Document storage with versioning and encryption
- KMS: Key management and encryption services

LLM Services:
- OpenAI: Document processing and embedding generation
- Token management for GPT-3.5 and GPT-4 models

Workflow Orchestration:
- Temporal: Fault-tolerant workflow execution
- Activity management and monitoring

Usage:
    from integrations import S3Client, OpenAIClient, TemporalClient
    
    # Initialize clients
    s3_client = S3Client(settings)
    openai_client = OpenAIClient(settings)
    temporal_client = TemporalClient(settings)
"""

# Public exports
__all__ = [
    # AWS Services
    "S3Client",
    "KMSClient",
    
    # LLM Services
    "OpenAIClient",
    "DEFAULT_MODEL",
    "MAX_TOKENS_GPT4",
    "MAX_TOKENS_GPT35",
    
    # Temporal Services
    "TemporalClient",
    "TemporalWorker",
    
    # Package Info
    "__version__",
    "__maintainers__",
    "__doc__"
]

def get_client_metrics() -> Dict[str, Any]:
    """
    Retrieve comprehensive metrics from all integration clients.
    
    Returns:
        Dict containing metrics from all services
        
    Example:
        {
            "aws": {
                "s3": {...},
                "kms": {...}
            },
            "llm": {...},
            "temporal": {...}
        }
    """
    metrics = {
        "aws": {
            "s3": S3Client.get_metrics() if hasattr(S3Client, 'get_metrics') else {},
            "kms": KMSClient.get_metrics() if hasattr(KMSClient, 'get_metrics') else {}
        },
        "llm": OpenAIClient.get_metrics() if hasattr(OpenAIClient, 'get_metrics') else {},
        "temporal": TemporalClient.get_metrics() if hasattr(TemporalClient, 'get_metrics') else {}
    }
    
    return metrics