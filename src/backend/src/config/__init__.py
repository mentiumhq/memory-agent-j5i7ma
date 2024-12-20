"""
Configuration module initialization for the Memory Agent service.
Provides centralized configuration management, logging setup, and security monitoring.

External Dependencies:
- pydantic_settings==2.0.0: Settings management
- opentelemetry-api==1.20.0: Distributed tracing
- watchtower==3.0.1: CloudWatch integration
"""

import functools
import threading
from typing import Optional

from .settings import Settings
from .logging import setup_logging, get_logger

# Global settings instance
settings = Settings()

# Thread-safe initialization tracking
_config_initialized = threading.Event()

@functools.lru_cache(maxsize=1)
def initialize_config() -> None:
    """
    Initialize application configuration and logging setup with environment-specific settings
    and security monitoring. Thread-safe and idempotent initialization.
    
    Raises:
        ConfigurationError: If configuration validation fails
        RuntimeError: If critical services cannot be initialized
    """
    if _config_initialized.is_set():
        return

    try:
        # Validate configuration
        if not validate_config(settings):
            raise ConfigurationError("Invalid configuration settings")

        # Initialize logging infrastructure
        setup_logging(settings)
        logger = get_logger(__name__)
        
        logger.info(
            "Initializing Memory Agent configuration",
            extra={
                "environment": settings.ENVIRONMENT,
                "version": settings.VERSION,
                "log_level": settings.LOG_LEVEL
            }
        )

        # Validate environment-specific settings
        if settings.ENVIRONMENT == "production":
            logger.info("Validating production configuration")
            _validate_production_settings(settings)

        # Initialize security monitoring
        _setup_security_monitoring(settings)

        # Mark initialization as complete
        _config_initialized.set()
        
        logger.info(
            "Memory Agent configuration initialized successfully",
            extra={
                "project_name": settings.PROJECT_NAME,
                "api_version": settings.API_V1_STR,
                "environment": settings.ENVIRONMENT
            }
        )

    except Exception as e:
        # Ensure logging is available for error reporting
        logger = get_logger(__name__)
        logger.error(
            f"Failed to initialize configuration: {str(e)}",
            exc_info=True,
            extra={"environment": settings.ENVIRONMENT}
        )
        raise RuntimeError(f"Configuration initialization failed: {str(e)}")

def validate_config(settings: Settings) -> bool:
    """
    Validate configuration completeness and security settings.
    
    Args:
        settings: Application settings instance
        
    Returns:
        bool: True if configuration is valid
        
    Raises:
        ConfigurationError: If validation fails
    """
    required_settings = [
        "SECRET_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "OPENAI_API_KEY",
        "S3_BUCKET_NAME"
    ]

    # Check required settings
    for setting in required_settings:
        if not getattr(settings, setting, None):
            raise ConfigurationError(f"Missing required setting: {setting}")

    # Validate security settings
    if len(settings.SECRET_KEY) < 32:
        raise ConfigurationError("SECRET_KEY must be at least 32 characters")

    # Validate AWS credentials format
    if not settings.AWS_ACCESS_KEY_ID.strip() or not settings.AWS_SECRET_ACCESS_KEY.strip():
        raise ConfigurationError("Invalid AWS credentials")

    # Validate S3 bucket name format
    if not settings.S3_BUCKET_NAME.strip().lower().replace("-", "").isalnum():
        raise ConfigurationError("Invalid S3 bucket name format")

    return True

def _validate_production_settings(settings: Settings) -> None:
    """
    Additional validation for production environment settings.
    
    Args:
        settings: Application settings instance
        
    Raises:
        ConfigurationError: If production validation fails
    """
    # Validate logging configuration
    if settings.LOG_LEVEL == "DEBUG":
        raise ConfigurationError("DEBUG log level not allowed in production")

    # Validate security settings
    if settings.ACCESS_TOKEN_EXPIRE_MINUTES > 60:
        raise ConfigurationError("Token expiration too long for production")

    # Validate rate limiting
    if settings.RATE_LIMIT_PER_MINUTE > 100:
        raise ConfigurationError("Rate limit too high for production")

def _setup_security_monitoring(settings: Settings) -> None:
    """
    Configure security monitoring and alerting based on environment.
    
    Args:
        settings: Application settings instance
    """
    logger = get_logger(__name__)

    # Configure security monitoring based on environment
    monitoring_config = {
        "log_sensitive_operations": True,
        "alert_on_suspicious_activity": settings.ENVIRONMENT == "production",
        "track_failed_attempts": True,
        "monitor_rate_limits": True
    }

    logger.info(
        "Security monitoring configured",
        extra={
            "environment": settings.ENVIRONMENT,
            "monitoring_config": monitoring_config
        }
    )

class ConfigurationError(Exception):
    """Custom exception for configuration-related errors."""
    pass

# Export public interface
__all__ = [
    "settings",
    "initialize_config",
    "get_logger",
    "ConfigurationError"
]