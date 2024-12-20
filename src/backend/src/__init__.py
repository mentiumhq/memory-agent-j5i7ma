"""
Memory Agent Backend Service
---------------------------
A Temporal workflow-based document storage and retrieval service for LLM agents.

This module initializes core components, telemetry, and exposes package metadata.
Provides enterprise-grade monitoring and observability setup for production use.

External Dependencies:
- opentelemetry-api==1.20.0: Core OpenTelemetry API
- opentelemetry-sdk==1.20.0: OpenTelemetry implementation
"""

from config.settings import Settings
from core.telemetry import setup_telemetry
from config.logging import setup_logging, get_logger

# Package metadata
__version__ = Settings().VERSION
__project__ = Settings().PROJECT_NAME
__author__ = 'Memory Agent Team'
__description__ = 'Temporal workflow-based document storage and retrieval service for LLM agents'

# Initialize logger for this module
logger = get_logger(__name__)

def initialize_app() -> None:
    """
    Initialize core components of the Memory Agent application.
    Sets up telemetry, logging, and core configuration.
    
    This function should be called at application startup to ensure proper
    initialization of all system components.
    
    Raises:
        Exception: If initialization of any component fails
    """
    try:
        logger.info(
            "Initializing Memory Agent application",
            extra={
                "version": __version__,
                "environment": Settings().ENVIRONMENT
            }
        )

        # Create settings instance
        settings = Settings()
        
        # Initialize logging first for proper observability
        setup_logging(settings)
        logger.info("Logging system initialized")
        
        # Setup telemetry (tracing and metrics)
        tracer_provider, meter_provider = setup_telemetry(settings)
        logger.info(
            "Telemetry system initialized",
            extra={
                "tracer_provider": str(tracer_provider),
                "meter_provider": str(meter_provider)
            }
        )
        
        logger.info(
            "Memory Agent initialization complete",
            extra={
                "project": __project__,
                "version": __version__
            }
        )
    except Exception as e:
        logger.error(
            f"Failed to initialize Memory Agent: {str(e)}",
            exc_info=True,
            extra={"initialization_stage": "app_init"}
        )
        raise

# Export public interface
__all__ = [
    '__version__',
    '__project__',
    '__author__',
    '__description__',
    'initialize_app'
]