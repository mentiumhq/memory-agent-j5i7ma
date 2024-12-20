"""
Main entry point for the Memory Agent CLI application.
Provides command-line interface for document operations and system health checks
with comprehensive telemetry and error handling.

Version:
- click==8.1.0
- rich==13.0.0
- opentelemetry-api==1.20.0
"""

import asyncio
import signal
import sys
import atexit
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from commands.document import (
    store_document,
    retrieve_document,
    search_documents,
    delete_document
)
from commands.health import health_check
from core.telemetry import create_tracer

# Initialize tracer and console
tracer = create_tracer('cli_main')
console = Console()

# Global state for cleanup
cleanup_tasks = []

def cleanup() -> None:
    """Perform cleanup operations on program exit."""
    try:
        # Flush telemetry data
        tracer.force_flush()
        
        # Run registered cleanup tasks
        for task in cleanup_tasks:
            task()
            
        console.print("[dim]Cleanup completed successfully[/dim]")
    except Exception as e:
        console.print(f"[red]Error during cleanup: {str(e)}[/red]")

def handle_interrupt(signum: int, frame: Optional[object]) -> None:
    """
    Handle keyboard interrupts gracefully.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    console.print("\n[yellow]Operation cancelled by user[/yellow]")
    cleanup()
    sys.exit(1)

@click.group()
@click.version_option(version='1.0.0', prog_name='memory-agent')
@tracer.start_as_current_span('cli_command')
def cli() -> None:
    """Memory Agent CLI - Intelligent document storage and retrieval system."""
    pass

def register_commands() -> None:
    """Register all CLI commands with error handling."""
    try:
        # Register document commands
        cli.add_command(store_document)
        cli.add_command(retrieve_document)
        cli.add_command(search_documents)
        cli.add_command(delete_document)
        
        # Register health check command
        cli.add_command(health_check)
        
    except Exception as e:
        console.print(Panel(
            f"[red bold]Failed to register commands: {str(e)}[/]\n\n"
            f"Please ensure all required dependencies are installed.",
            title="Error",
            border_style="red"
        ))
        sys.exit(1)

def setup_signal_handlers() -> None:
    """Configure signal handlers for graceful shutdown."""
    signal.signal(signal.SIGINT, handle_interrupt)
    signal.signal(signal.SIGTERM, handle_interrupt)

def main() -> None:
    """
    Main entry point for the CLI application.
    Initializes resources, registers commands, and handles program lifecycle.
    """
    try:
        # Register cleanup handler
        atexit.register(cleanup)
        
        # Setup signal handlers
        setup_signal_handlers()
        
        # Register CLI commands
        register_commands()
        
        # Start CLI with asyncio event loop
        if sys.platform == 'win32':
            # Windows-specific event loop policy
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
        # Run CLI application
        cli(_anyio_backend='asyncio')
        
    except click.ClickException as e:
        # Handle Click-specific exceptions
        console.print(Panel(
            f"[red bold]{str(e)}[/]",
            title="Command Error",
            border_style="red"
        ))
        sys.exit(e.exit_code)
        
    except Exception as e:
        # Handle unexpected errors
        console.print(Panel(
            f"[red bold]An unexpected error occurred: {str(e)}[/]\n\n"
            f"Please report this issue to the development team.",
            title="Error",
            border_style="red"
        ))
        sys.exit(1)
        
    finally:
        # Ensure cleanup runs
        cleanup()

if __name__ == '__main__':
    main()