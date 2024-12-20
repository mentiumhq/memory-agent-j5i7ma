"""
Temporal integration initialization module providing enterprise-grade client and worker
management capabilities for workflow orchestration.

Implements fault-tolerant workflow management with comprehensive security, monitoring,
and operational features.

Version: 1.0.0
External Dependencies:
- temporalio==1.0.0: Core Temporal workflow functionality
- opentelemetry-api==1.20.0: Distributed tracing support
"""

from .client import TemporalClient
from .worker import TemporalWorker

# Package version
__version__ = "1.0.0"

# Package maintainers
__maintainers__ = ["Memory Agent Team"]

# Package documentation
__doc__ = """
Memory Agent Temporal Integration Package

Provides enterprise-grade workflow orchestration with:
- Fault-tolerant workflow execution
- Comprehensive security features
- Extensive monitoring and telemetry
- Production-ready operational capabilities

Components:
- TemporalClient: Manages workflow operations and monitoring
- TemporalWorker: Handles activity execution and task queues

Configuration:
- Supports TLS/mTLS security
- Configurable retry policies
- Customizable monitoring
- Resource management controls

Usage:
    from integrations.temporal import TemporalClient, TemporalWorker
    
    # Initialize client
    client = TemporalClient(settings)
    
    # Initialize worker
    worker = TemporalWorker(settings)
    
    # Start worker
    async with worker.start():
        # Worker is running
        pass
"""

# Public exports
__all__ = [
    "TemporalClient",
    "TemporalWorker",
    "__version__",
    "__maintainers__",
    "__doc__"
]