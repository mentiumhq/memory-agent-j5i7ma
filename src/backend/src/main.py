"""
Main entry point for the Memory Agent service.
Initializes and manages FastAPI server and Temporal worker processes with comprehensive
monitoring, telemetry, and graceful shutdown capabilities.

Version: 1.0.0
"""

import asyncio
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Dict, Optional
from prometheus_client import start_http_server
import uvicorn
from opentelemetry import trace

from api.server import app, lifespan
from config.settings import Settings
from config.logging import configure_logging, get_logger
from integrations.temporal.worker import TemporalWorker
from core.telemetry import setup_telemetry
from core.errors import MemoryAgentError, ErrorCode

# Initialize settings and logging
settings = Settings()
LOGGER = get_logger(__name__)

# Global state management
shutdown_event = asyncio.Event()
worker_tasks: Dict[str, asyncio.Task] = {}
temporal_workers: Dict[str, TemporalWorker] = {}

async def initialize_system() -> bool:
    """
    Initialize system components with comprehensive validation and monitoring.

    Returns:
        bool: True if initialization successful, False otherwise
    """
    try:
        # Configure logging
        configure_logging()
        LOGGER.info("Logging configured successfully")

        # Validate environment
        settings.validate_environment()
        LOGGER.info(f"Environment validated: {settings.ENVIRONMENT}")

        # Setup telemetry
        tracer_provider, meter_provider = setup_telemetry(settings)
        trace.set_tracer_provider(tracer_provider)
        LOGGER.info("Telemetry initialized successfully")

        # Start Prometheus metrics server
        start_http_server(port=8000)
        LOGGER.info("Metrics server started on port 8000")

        return True

    except Exception as e:
        LOGGER.error(f"System initialization failed: {str(e)}", exc_info=True)
        return False

async def start_temporal_workers() -> None:
    """
    Start and manage Temporal worker processes with health monitoring.
    """
    try:
        # Create worker instances based on configuration
        worker_count = settings.WORKER_COUNT
        LOGGER.info(f"Starting {worker_count} Temporal workers")

        for i in range(worker_count):
            worker = TemporalWorker(settings)
            worker_id = f"worker_{i}"
            temporal_workers[worker_id] = worker

            # Start worker with monitoring
            async with worker.start() as w:
                worker_tasks[worker_id] = asyncio.create_task(
                    monitor_worker(worker_id, worker)
                )

        LOGGER.info("All Temporal workers started successfully")

    except Exception as e:
        LOGGER.error(f"Failed to start Temporal workers: {str(e)}", exc_info=True)
        raise MemoryAgentError(
            "Worker initialization failed",
            ErrorCode.WORKFLOW_ERROR,
            {"error": str(e)}
        )

async def monitor_worker(worker_id: str, worker: TemporalWorker) -> None:
    """
    Monitor worker health and handle failures.

    Args:
        worker_id: Unique worker identifier
        worker: TemporalWorker instance to monitor
    """
    while not shutdown_event.is_set():
        try:
            # Check worker health
            health_status = await worker.health_check()
            
            if not health_status['healthy']:
                LOGGER.warning(
                    f"Worker {worker_id} health check failed",
                    extra=health_status
                )
                
                # Attempt worker recovery
                await recover_worker(worker_id, worker)
                
            await asyncio.sleep(30)  # Health check interval

        except Exception as e:
            LOGGER.error(
                f"Worker monitoring failed: {str(e)}",
                extra={"worker_id": worker_id},
                exc_info=True
            )
            await asyncio.sleep(60)  # Backoff on error

async def recover_worker(worker_id: str, worker: TemporalWorker) -> None:
    """
    Attempt to recover failed worker process.

    Args:
        worker_id: Worker identifier
        worker: TemporalWorker instance to recover
    """
    try:
        LOGGER.info(f"Attempting to recover worker {worker_id}")
        
        # Cancel existing worker task
        if worker_id in worker_tasks:
            worker_tasks[worker_id].cancel()
            
        # Restart worker
        async with worker.start() as w:
            worker_tasks[worker_id] = asyncio.create_task(
                monitor_worker(worker_id, worker)
            )
            
        LOGGER.info(f"Worker {worker_id} recovered successfully")
        
    except Exception as e:
        LOGGER.error(
            f"Worker recovery failed: {str(e)}",
            extra={"worker_id": worker_id},
            exc_info=True
        )

def shutdown(signal_number: int, frame) -> None:
    """
    Handle graceful shutdown on system signals.

    Args:
        signal_number: Signal number received
        frame: Current stack frame
    """
    LOGGER.info(f"Received shutdown signal {signal_number}")
    shutdown_event.set()

async def cleanup() -> None:
    """
    Perform graceful cleanup of system resources.
    """
    try:
        # Cancel worker tasks
        for task in worker_tasks.values():
            task.cancel()
            
        # Wait for tasks to complete
        if worker_tasks:
            await asyncio.gather(*worker_tasks.values(), return_exceptions=True)
            
        # Close any remaining connections
        for worker in temporal_workers.values():
            await worker.health_check()  # Final health check
            
        LOGGER.info("Cleanup completed successfully")
        
    except Exception as e:
        LOGGER.error(f"Cleanup failed: {str(e)}", exc_info=True)

async def main() -> None:
    """
    Main entry point for the Memory Agent service.
    Manages FastAPI server and Temporal worker lifecycle.
    """
    try:
        # Initialize system
        if not await initialize_system():
            LOGGER.error("System initialization failed")
            sys.exit(1)

        # Register signal handlers
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, shutdown)

        # Start Temporal workers
        await start_temporal_workers()

        # Configure uvicorn server
        config = uvicorn.Config(
            app=app,
            host=settings.HOST,
            port=settings.PORT,
            workers=1,  # Using multiple Temporal workers instead
            loop="asyncio",
            lifespan=lifespan
        )

        # Start server
        server = uvicorn.Server(config)
        await server.serve()

    except Exception as e:
        LOGGER.error(f"Service startup failed: {str(e)}", exc_info=True)
        sys.exit(1)
    finally:
        # Perform cleanup
        await cleanup()

if __name__ == "__main__":
    asyncio.run(main())