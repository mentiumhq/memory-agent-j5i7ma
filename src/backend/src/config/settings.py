"""
Core configuration settings module for the Memory Agent system.
Provides centralized configuration management with comprehensive validation.

External Dependencies:
- pydantic_settings==2.0.0: Type-safe settings management
- pydantic==2.0.0: Data validation and settings management
- python-dotenv==1.0.0: Environment variable management
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
import os
from typing import Optional
from enum import Enum

# Load environment variables at module initialization
load_dotenv()

class EnvironmentType(str, Enum):
    """Valid environment types for the application."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

class LogLevel(str, Enum):
    """Valid logging levels."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class Settings(BaseSettings):
    """
    Comprehensive configuration settings for the Memory Agent system.
    Provides type-safe access to all configuration parameters with validation.
    """

    # Application Information
    PROJECT_NAME: str = Field(
        default="Memory Agent",
        description="Name of the project"
    )
    VERSION: str = Field(
        default="1.0.0",
        description="API version"
    )
    API_V1_STR: str = Field(
        default="/api/v1",
        description="API version prefix"
    )

    # Security Settings
    SECRET_KEY: str = Field(
        ...,  # Required field
        description="JWT secret key for token signing",
        min_length=32
    )
    ALGORITHM: str = Field(
        default="HS256",
        description="JWT signing algorithm"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="JWT token expiration time in minutes",
        gt=0
    )

    # Environment Configuration
    ENVIRONMENT: EnvironmentType = Field(
        default=EnvironmentType.DEVELOPMENT,
        description="Application environment"
    )

    # AWS Configuration
    AWS_ACCESS_KEY_ID: str = Field(
        ...,
        description="AWS access key ID for S3 access"
    )
    AWS_SECRET_ACCESS_KEY: str = Field(
        ...,
        description="AWS secret access key for S3 access"
    )
    AWS_REGION: str = Field(
        default="us-east-1",
        description="AWS region for services"
    )
    S3_BUCKET_NAME: str = Field(
        ...,
        description="S3 bucket name for document storage"
    )

    # Database Configuration
    SQLITE_URL: str = Field(
        default="sqlite:///./memory_agent.db",
        description="SQLite database URL"
    )

    # External Service Configuration
    OPENAI_API_KEY: str = Field(
        ...,
        description="OpenAI API key for LLM services"
    )

    # Temporal Configuration
    TEMPORAL_HOST: str = Field(
        default="localhost",
        description="Temporal server host"
    )
    TEMPORAL_PORT: int = Field(
        default=7233,
        description="Temporal server port"
    )
    TEMPORAL_NAMESPACE: str = Field(
        default="memory-agent",
        description="Temporal namespace for workflows"
    )

    # Performance Settings
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=100,
        description="API rate limit per minute per client",
        gt=0
    )
    CACHE_TTL_SECONDS: int = Field(
        default=3600,
        description="Cache TTL in seconds",
        gt=0
    )
    MAX_DOCUMENT_SIZE_MB: int = Field(
        default=10,
        description="Maximum document size in MB",
        gt=0
    )
    CHUNK_SIZE_TOKENS: int = Field(
        default=4000,
        description="Document chunk size in tokens",
        gt=0
    )

    # Logging Configuration
    LOG_LEVEL: LogLevel = Field(
        default=LogLevel.INFO,
        description="Application log level"
    )

    class Config:
        """Pydantic model configuration."""
        case_sensitive = True
        env_prefix = "MEMORY_AGENT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        frozen = True  # Make settings immutable
        validate_assignment = True
        
        # Mask sensitive fields in string representation
        secrets_dir = None
        sensitive_fields = {
            "SECRET_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "OPENAI_API_KEY"
        }

    def __init__(self, **kwargs):
        """Initialize settings with validation and environment-specific configurations."""
        super().__init__(**kwargs)
        
        # Validate environment-specific configurations
        if self.ENVIRONMENT == EnvironmentType.PRODUCTION:
            assert self.LOG_LEVEL != LogLevel.DEBUG, "Debug logging not allowed in production"
            assert self.SQLITE_URL.startswith("sqlite:///"), "Production requires absolute SQLite path"
        
        # Validate storage configurations
        if not os.path.dirname(self.SQLITE_URL.replace("sqlite:///", "")):
            os.makedirs(os.path.dirname(self.SQLITE_URL.replace("sqlite:///", "")), exist_ok=True)

# Create a global settings instance
settings = Settings()

# Export settings instance and important constants
__all__ = [
    "settings",
    "EnvironmentType",
    "LogLevel"
]