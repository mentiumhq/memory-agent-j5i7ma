"""
CLI module for checking Memory Agent service health status.
Implements comprehensive health checks with detailed component status reporting.

External Dependencies:
- click==8.1.0: CLI framework for command creation
- rich==13.0.0: Enhanced terminal output formatting
- httpx==0.24.0: Async HTTP client for health checks
"""

import asyncio
from typing import Dict, Any
import time

import click
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
import httpx
from httpx import AsyncClient, TimeoutException

from core.telemetry import create_tracer

# Initialize tracer and console
tracer = create_tracer('health_command')
console = Console()

# Component endpoints for health checks
COMPONENT_ENDPOINTS = {
    'api': '/api/v1/health',
    'temporal': '/health',
    'storage': '/api/v1/storage/health',
    'retrieval': '/api/v1/retrieval/health'
}

async def check_component_health(
    client: AsyncClient,
    component_name: str,
    endpoint: str
) -> Dict[str, Any]:
    """
    Check health status of individual system components.

    Args:
        client: Async HTTP client instance
        component_name: Name of the component to check
        endpoint: Health check endpoint for the component

    Returns:
        Dict containing component health status and metrics
    """
    with tracer.start_as_current_span('check_component_health') as span:
        span.set_attribute('component.name', component_name)
        span.set_attribute('component.endpoint', endpoint)
        
        start_time = time.time()
        try:
            response = await client.get(endpoint, timeout=5.0)
            latency = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            status = {
                'name': component_name,
                'status': 'healthy' if response.status_code == 200 else 'degraded',
                'latency_ms': round(latency, 2),
                'code': response.status_code
            }
            
            # Add detailed metrics if available
            if response.status_code == 200:
                try:
                    metrics = response.json()
                    status.update({
                        'metrics': metrics.get('metrics', {}),
                        'version': metrics.get('version', 'unknown')
                    })
                except Exception:
                    status['metrics'] = {}
            
            span.set_attribute('health.status', status['status'])
            span.set_attribute('health.latency_ms', status['latency_ms'])
            return status
            
        except TimeoutException:
            span.set_attribute('health.status', 'unhealthy')
            span.set_attribute('error.type', 'timeout')
            return {
                'name': component_name,
                'status': 'unhealthy',
                'error': 'timeout',
                'latency_ms': 5000  # Timeout threshold
            }
        except Exception as e:
            span.set_attribute('health.status', 'unhealthy')
            span.set_attribute('error.type', str(type(e).__name__))
            return {
                'name': component_name,
                'status': 'unhealthy',
                'error': str(e),
                'latency_ms': (time.time() - start_time) * 1000
            }

def format_health_output(health_status: Dict[str, Any], verbose: bool) -> Panel:
    """
    Format health check results for console output.

    Args:
        health_status: Dictionary containing health check results
        verbose: Flag for detailed output

    Returns:
        Rich panel containing formatted health status
    """
    # Create status text
    status_text = Text()
    
    # Add overall status
    overall_status = health_status.get('overall_status', 'unknown')
    status_color = {
        'healthy': 'green',
        'degraded': 'yellow',
        'unhealthy': 'red',
        'unknown': 'grey'
    }.get(overall_status, 'grey')
    
    status_text.append(
        f"Overall Status: ",
        style="bold"
    )
    status_text.append(
        f"{overall_status.upper()}\n\n",
        style=f"bold {status_color}"
    )

    # Add component details if verbose
    if verbose and 'components' in health_status:
        status_text.append("Component Status:\n", style="bold")
        for component in health_status['components']:
            # Component name and status
            status_text.append(
                f"• {component['name']}: ",
                style="bold"
            )
            status_text.append(
                f"{component['status'].upper()}",
                style=f"bold {status_color}"
            )
            
            # Latency information
            status_text.append(
                f" (Latency: {component['latency_ms']}ms)\n"
            )
            
            # Add metrics if available
            if 'metrics' in component and component['metrics']:
                for metric, value in component['metrics'].items():
                    status_text.append(
                        f"  - {metric}: {value}\n",
                        style="dim"
                    )
            
            # Add errors if present
            if 'error' in component:
                status_text.append(
                    f"  - Error: {component['error']}\n",
                    style="red"
                )
            
            status_text.append("\n")

    return Panel(
        status_text,
        title="Memory Agent Health Status",
        border_style=status_color,
        padding=(1, 2)
    )

@click.command('health')
@click.option(
    '--verbose',
    '-v',
    is_flag=True,
    help='Show detailed component status'
)
@tracer.start_as_current_span('cli_health_check')
async def health_check(verbose: bool) -> None:
    """Check the health status of the Memory Agent service."""
    try:
        async with AsyncClient() as client:
            # Check core service health
            core_health = await check_component_health(
                client,
                'core',
                COMPONENT_ENDPOINTS['api']
            )
            
            health_status = {
                'overall_status': core_health['status'],
                'components': [core_health]
            }

            # Check component health if verbose
            if verbose:
                component_checks = []
                for name, endpoint in COMPONENT_ENDPOINTS.items():
                    if name != 'api':  # Skip core API as already checked
                        component_checks.append(
                            check_component_health(client, name, endpoint)
                        )
                
                # Run component checks concurrently
                component_results = await asyncio.gather(
                    *component_checks,
                    return_exceptions=True
                )
                
                # Add component results
                health_status['components'].extend([
                    result if not isinstance(result, Exception) else {
                        'name': 'unknown',
                        'status': 'unhealthy',
                        'error': str(result)
                    }
                    for result in component_results
                ])
                
                # Update overall status based on components
                statuses = [comp['status'] for comp in health_status['components']]
                if any(status == 'unhealthy' for status in statuses):
                    health_status['overall_status'] = 'unhealthy'
                elif any(status == 'degraded' for status in statuses):
                    health_status['overall_status'] = 'degraded'

            # Format and display results
            status_panel = format_health_output(health_status, verbose)
            console.print(status_panel)

    except Exception as e:
        console.print(
            f"[red bold]Error checking service health: {str(e)}[/red bold]"
        )
        raise click.Abort()

if __name__ == '__main__':
    health_check(_anyio_backend='asyncio')