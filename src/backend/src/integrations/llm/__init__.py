"""
LLM integration initialization module for Memory Agent system.
Provides OpenAI client and related components for document processing and embedding generation.

Version: 1.0.0
External Dependencies:
- openai==1.0.0: OpenAI API client for LLM operations
"""

from .openai import OpenAIClient
from core.errors import LLMError, ErrorCode

# Token management constants based on model specifications
DEFAULT_MODEL = "gpt-4"  # Default to GPT-4 for highest capability
MAX_TOKENS_GPT4 = 32000  # 32K context window for GPT-4
MAX_TOKENS_GPT35 = 16000  # 16K context window for GPT-3.5
DEFAULT_TIMEOUT = 3000  # 3000ms timeout per technical spec requirement

# Export public interface
__all__ = [
    'OpenAIClient',  # Primary client for LLM operations
    'LLMError',  # Error handling for LLM operations
    'DEFAULT_MODEL',  # Default GPT-4 model configuration
    'MAX_TOKENS_GPT4',  # GPT-4 token limit
    'MAX_TOKENS_GPT35',  # GPT-3.5 token limit
    'DEFAULT_TIMEOUT'  # Default operation timeout
]

# Version information
__version__ = '1.0.0'
__author__ = 'Memory Agent Team'
__license__ = 'Proprietary'

# Module level docstring
__doc__ = """
LLM Integration Package
======================

This package provides enterprise-grade integration with OpenAI's LLM services
for document processing and embedding generation. It includes:

- Comprehensive token management for GPT-3.5 and GPT-4 models
- Error handling with proper timeout mechanisms
- Response time monitoring and validation
- Security-focused error sanitization

Key Components:
--------------
- OpenAIClient: Main client for LLM operations
- LLMError: Specialized error handling
- Token Management Constants: Model-specific limits

Usage:
------
from integrations.llm import OpenAIClient, DEFAULT_MODEL, MAX_TOKENS_GPT4

client = OpenAIClient(settings)
try:
    result = await client.process_document(...)
except LLMError as e:
    # Handle error with proper context
    pass
"""