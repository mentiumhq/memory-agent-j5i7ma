"""
Enterprise-grade Temporal client implementation for the Memory Agent service.
Provides secure, reliable, and monitored workflow orchestration with comprehensive
connection management, retry policies, and telemetry.

External Dependencies:
- temporalio==1.0.0: Core Temporal client functionality
- opentelemetry-api==1.20.0: Distributed tracing support
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncContextManager, Callable, Dict, List, Optional

from temporalio.client import Client, TLSConfig
from temporalio.common import RetryPolicy
from temporalio.client import WorkflowHandle

from config.settings import Settings
from core.telemetry import create_tracer
from core.errors import WorkflowError, ErrorCode

# Initialize tracer for comprehensive monitoring
LOGGER = create_tracer(__name__)

# Default retry policy for workflow operations
DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=5,
    backoff_coefficient=2.0
)

# Connection timeouts and health check intervals
CONNECTION_TIMEOUT = timedelta(seconds=30)
HEALTH_CHECK_INTERVAL = timedelta(seconds=60)

class TemporalClient:
    """
    Enterprise-grade Temporal client managing secure connections, workflow operations,
    and comprehensive monitoring.
    """

    def __init__(self, settings: Settings, retry_policy: Optional[RetryPolicy] = None):
        """
        Initialize Temporal client with comprehensive configuration.

        Args:
            settings: Application settings instance
            retry_policy: Optional custom retry policy
        """
        self._settings = settings
        self._retry_policy = retry_policy or DEFAULT_RETRY_POLICY
        self._client: Optional[Client] = None
        self._tls_config: Optional[TLSConfig] = None
        self._metrics: Dict[str, Any] = {
            "connections": 0,
            "connection_errors": 0,
            "workflows_started": 0,
            "workflow_errors": 0
        }

        # Configure TLS for secure communication
        if settings.TEMPORAL_TLS_CERT_PATH and settings.TEMPORAL_TLS_KEY_PATH:
            self._tls_config = TLSConfig(
                client_cert=settings.TEMPORAL_TLS_CERT_PATH,
                client_private_key=settings.TEMPORAL_TLS_KEY_PATH
            )

    @asynccontextmanager
    async def connect(self) -> AsyncContextManager[Client]:
        """
        Establish secure connection to Temporal server with comprehensive monitoring.

        Returns:
            AsyncContextManager[Client]: Connected client instance

        Raises:
            WorkflowError: If connection fails
        """
        if self._client:
            yield self._client
            return

        try:
            with LOGGER.start_span("temporal_connect") as span:
                span.set_attribute("temporal.host", self._settings.TEMPORAL_HOST)
                span.set_attribute("temporal.namespace", self._settings.TEMPORAL_NAMESPACE)

                # Create client with secure configuration
                self._client = await Client.connect(
                    f"{self._settings.TEMPORAL_HOST}:{self._settings.TEMPORAL_PORT}",
                    namespace=self._settings.TEMPORAL_NAMESPACE,
                    tls=self._tls_config,
                    retry_policy=self._retry_policy,
                    timeout=CONNECTION_TIMEOUT
                )

                # Start health check monitoring
                asyncio.create_task(self._monitor_health())
                
                self._metrics["connections"] += 1
                span.set_attribute("temporal.connection.success", True)
                
                LOGGER.info(
                    "Connected to Temporal server",
                    extra={
                        "host": self._settings.TEMPORAL_HOST,
                        "namespace": self._settings.TEMPORAL_NAMESPACE
                    }
                )

                yield self._client

        except Exception as e:
            self._metrics["connection_errors"] += 1
            error_details = {
                "host": self._settings.TEMPORAL_HOST,
                "namespace": self._settings.TEMPORAL_NAMESPACE,
                "error": str(e)
            }
            LOGGER.error("Failed to connect to Temporal", extra=error_details)
            raise WorkflowError(
                "Failed to establish Temporal connection",
                ErrorCode.WORKFLOW_ERROR,
                error_details
            )

        finally:
            # Cleanup on context exit
            if self._client:
                await self._client.close()
                self._client = None

    async def start_workflow(
        self,
        workflow_id: str,
        workflow_fn: Callable,
        args: List[Any],
        metadata: Optional[Dict[str, str]] = None
    ) -> WorkflowHandle:
        """
        Start new workflow with comprehensive monitoring and error handling.

        Args:
            workflow_id: Unique workflow identifier
            workflow_fn: Workflow function to execute
            args: Workflow function arguments
            metadata: Optional workflow metadata

        Returns:
            WorkflowHandle: Handle to started workflow

        Raises:
            WorkflowError: If workflow start fails
        """
        if not workflow_id or not workflow_fn:
            raise ValueError("Invalid workflow parameters")

        try:
            with LOGGER.start_span("start_workflow") as span:
                span.set_attribute("workflow.id", workflow_id)
                span.set_attribute("workflow.function", workflow_fn.__name__)

                async with self.connect() as client:
                    handle = await client.start_workflow(
                        workflow_fn,
                        args,
                        id=workflow_id,
                        retry_policy=self._retry_policy,
                        metadata=metadata or {}
                    )

                    self._metrics["workflows_started"] += 1
                    span.set_attribute("workflow.start.success", True)

                    LOGGER.info(
                        "Started workflow",
                        extra={
                            "workflow_id": workflow_id,
                            "workflow_type": workflow_fn.__name__
                        }
                    )

                    return handle

        except Exception as e:
            self._metrics["workflow_errors"] += 1
            error_details = {
                "workflow_id": workflow_id,
                "workflow_type": workflow_fn.__name__,
                "error": str(e)
            }
            LOGGER.error("Failed to start workflow", extra=error_details)
            raise WorkflowError(
                "Failed to start workflow",
                ErrorCode.WORKFLOW_ERROR,
                error_details
            )

    async def get_workflow(self, workflow_id: str) -> WorkflowHandle:
        """
        Get handle to existing workflow with state validation.

        Args:
            workflow_id: Workflow identifier

        Returns:
            WorkflowHandle: Handle to existing workflow

        Raises:
            WorkflowError: If workflow not found or invalid state
        """
        if not workflow_id:
            raise ValueError("Invalid workflow ID")

        try:
            with LOGGER.start_span("get_workflow") as span:
                span.set_attribute("workflow.id", workflow_id)

                async with self.connect() as client:
                    handle = client.get_workflow_handle(workflow_id)
                    
                    # Validate workflow exists and is accessible
                    try:
                        await handle.describe()
                    except Exception as e:
                        raise WorkflowError(
                            f"Workflow not found or inaccessible: {workflow_id}",
                            ErrorCode.WORKFLOW_ERROR,
                            {"workflow_id": workflow_id, "error": str(e)}
                        )

                    span.set_attribute("workflow.get.success", True)
                    return handle

        except WorkflowError:
            raise
        except Exception as e:
            error_details = {
                "workflow_id": workflow_id,
                "error": str(e)
            }
            LOGGER.error("Failed to get workflow", extra=error_details)
            raise WorkflowError(
                "Failed to get workflow",
                ErrorCode.WORKFLOW_ERROR,
                error_details
            )

    async def _monitor_health(self) -> None:
        """
        Perform periodic health checks on Temporal connection.
        """
        while self._client:
            try:
                with LOGGER.start_span("health_check") as span:
                    # Verify connection is responsive
                    await self._client.workflow_service.get_system_info()
                    span.set_attribute("temporal.health_check.success", True)
                    LOGGER.debug("Temporal health check passed")

            except Exception as e:
                LOGGER.error(
                    "Temporal health check failed",
                    extra={"error": str(e)}
                )
                span.set_attribute("temporal.health_check.success", False)

            await asyncio.sleep(HEALTH_CHECK_INTERVAL.total_seconds())