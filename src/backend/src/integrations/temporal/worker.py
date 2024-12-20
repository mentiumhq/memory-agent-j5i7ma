"""
Production-grade Temporal worker implementation for the Memory Agent service.
Provides comprehensive telemetry, error handling, resource management, and health monitoring.

Version:
- temporalio==1.0.0
- opentelemetry-api==1.20.0
- psutil==5.9.0
"""

import asyncio
import logging
import psutil
from datetime import timedelta
from typing import Dict, List, Optional, Callable
from contextlib import asynccontextmanager

from temporalio.worker import Worker
from temporalio.client import Client, TLSConfig
from temporalio.common import RetryPolicy

from config.settings import Settings
from core.telemetry import create_tracer
from activities.document_activities import (
    store_document_activity,
    retrieve_document_activity,
    search_documents_activity,
    update_document_activity,
    delete_document_activity
)

# Initialize logging and tracing
LOGGER = create_tracer(__name__)

# Default retry policy for activities
DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=3
)

class TemporalWorker:
    """
    Production-grade Temporal worker implementation with comprehensive monitoring,
    error handling, and resource management capabilities.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initialize Temporal worker with configuration and monitoring setup.

        Args:
            settings: Application settings instance
        """
        self._settings = settings
        self._worker: Optional[Worker] = None
        self._client: Optional[Client] = None
        
        # Initialize monitoring metrics
        self._activity_metrics: Dict[str, Dict] = {
            'store_document': {'success': 0, 'failure': 0},
            'retrieve_document': {'success': 0, 'failure': 0},
            'search_documents': {'success': 0, 'failure': 0},
            'update_document': {'success': 0, 'failure': 0},
            'delete_document': {'success': 0, 'failure': 0}
        }
        
        # Initialize resource tracking
        self._resource_usage: Dict[str, float] = {
            'cpu_percent': 0.0,
            'memory_percent': 0.0,
            'disk_io': 0.0
        }
        
        # Initialize health status
        self._healthy = True

    @asynccontextmanager
    async def start(self):
        """
        Start the Temporal worker with comprehensive monitoring and error handling.

        Yields:
            Running worker context
        """
        try:
            # Validate configuration
            if not self._settings.TEMPORAL_NAMESPACE:
                raise ValueError("Temporal namespace not configured")

            # Configure TLS if enabled
            tls_config = None
            if self._settings.TEMPORAL_TLS_ENABLED:
                tls_config = TLSConfig(
                    server_root_ca_cert=self._settings.TEMPORAL_CA_CERT,
                    client_cert=self._settings.TEMPORAL_CLIENT_CERT,
                    client_private_key=self._settings.TEMPORAL_CLIENT_KEY
                )

            # Create Temporal client
            self._client = await Client.connect(
                f"{self._settings.TEMPORAL_HOST}:{self._settings.TEMPORAL_PORT}",
                namespace=self._settings.TEMPORAL_NAMESPACE,
                tls=tls_config
            )

            # Register activities with retry policies
            activities = self.register_activities()

            # Create worker with resource limits
            self._worker = Worker(
                self._client,
                task_queue=self._settings.TEMPORAL_TASK_QUEUE,
                activities=activities,
                max_concurrent_activities=50,
                max_cached_workflows=1000,
                rate_limit_per_second=100
            )

            # Start resource monitoring
            monitor_task = asyncio.create_task(self.monitor_resources())

            # Start worker
            worker_task = asyncio.create_task(self._worker.run())

            LOGGER.info(
                "Temporal worker started",
                extra={
                    "namespace": self._settings.TEMPORAL_NAMESPACE,
                    "task_queue": self._settings.TEMPORAL_TASK_QUEUE
                }
            )

            try:
                yield self._worker
            finally:
                # Graceful shutdown
                self._healthy = False
                monitor_task.cancel()
                worker_task.cancel()
                
                try:
                    await asyncio.gather(monitor_task, worker_task)
                except asyncio.CancelledError:
                    pass

                if self._client:
                    await self._client.close()

                LOGGER.info("Temporal worker shutdown complete")

        except Exception as e:
            self._healthy = False
            LOGGER.error(f"Failed to start Temporal worker: {str(e)}", exc_info=True)
            raise

    def register_activities(self) -> List[Callable]:
        """
        Register document processing activities with retry policies.

        Returns:
            List of registered activities
        """
        # Configure activity-specific retry policies
        store_retry = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            maximum_interval=timedelta(minutes=5),
            maximum_attempts=5  # More retries for storage
        )

        search_retry = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            maximum_interval=timedelta(minutes=10),
            maximum_attempts=3
        )

        # Register activities with monitoring wrappers
        activities = [
            self._wrap_activity(store_document_activity, "store_document", store_retry),
            self._wrap_activity(retrieve_document_activity, "retrieve_document", DEFAULT_RETRY_POLICY),
            self._wrap_activity(search_documents_activity, "search_documents", search_retry),
            self._wrap_activity(update_document_activity, "update_document", store_retry),
            self._wrap_activity(delete_document_activity, "delete_document", DEFAULT_RETRY_POLICY)
        ]

        return activities

    def _wrap_activity(
        self,
        activity: Callable,
        name: str,
        retry_policy: RetryPolicy
    ) -> Callable:
        """
        Wrap activity with monitoring and retry policy.

        Args:
            activity: Activity function to wrap
            name: Activity name for metrics
            retry_policy: Retry policy for activity

        Returns:
            Wrapped activity function
        """
        async def wrapped(*args, **kwargs):
            try:
                with LOGGER.start_as_current_span(f"activity.{name}") as span:
                    span.set_attribute("activity.name", name)
                    result = await activity(*args, **kwargs)
                    self._activity_metrics[name]['success'] += 1
                    return result
            except Exception as e:
                self._activity_metrics[name]['failure'] += 1
                LOGGER.error(
                    f"Activity {name} failed: {str(e)}",
                    exc_info=True,
                    extra={"activity": name}
                )
                raise

        # Set retry policy
        wrapped.__temporal_retry_policy__ = retry_policy
        return wrapped

    async def monitor_resources(self) -> None:
        """Monitor worker resource usage and health."""
        while self._healthy:
            try:
                # Update CPU usage
                self._resource_usage['cpu_percent'] = psutil.cpu_percent(interval=1)

                # Update memory usage
                memory = psutil.virtual_memory()
                self._resource_usage['memory_percent'] = memory.percent

                # Update disk I/O
                disk_io = psutil.disk_io_counters()
                self._resource_usage['disk_io'] = disk_io.read_bytes + disk_io.write_bytes

                # Log resource status
                if any(usage > 90 for usage in [
                    self._resource_usage['cpu_percent'],
                    self._resource_usage['memory_percent']
                ]):
                    LOGGER.warning(
                        "High resource usage detected",
                        extra=self._resource_usage
                    )

                await asyncio.sleep(60)  # Monitor every minute

            except Exception as e:
                LOGGER.error(f"Resource monitoring failed: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Continue monitoring despite errors

    async def health_check(self) -> Dict:
        """
        Check worker health status.

        Returns:
            Dict containing health status information
        """
        return {
            'healthy': self._healthy,
            'client_connected': self._client is not None,
            'resource_usage': self._resource_usage,
            'activity_metrics': self._activity_metrics
        }