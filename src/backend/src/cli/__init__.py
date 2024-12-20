"""
CLI package initialization module for the Memory Agent service.
Provides package-level imports, version configuration, and error handling for package initialization.

Version:
- pkg_resources==3.11+: Package version management
"""

from typing import Optional
import pkg_resources
import logging

from .main import cli

# Configure logging
logger = logging.getLogger(__name__)

def _get_version() -> str:
    """
    Safely retrieve package version with fallback handling.
    
    Returns:
        str: Package version string or 'unknown' if version cannot be determined
    """
    try:
        return pkg_resources.get_distribution('memory-agent').version
    except (pkg_resources.DistributionNotFound, ImportError) as e:
        logger.warning(f"Failed to determine package version: {str(e)}")
        return 'unknown'

# Package version
__version__ = _get_version()

# Public exports
__all__ = [
    'cli',
    '__version__'
]