"""
Command-line interface implementation for document operations providing robust,
user-friendly commands for storing, retrieving, searching and deleting documents.

Version:
- click==8.1.0
- rich==13.0.0
- asyncio==3.11+
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table

from ...services.document import DocumentService
from ...api.models.request import RetrievalStrategy
from ...core.errors import StorageError, ErrorCode

# Initialize rich console for formatted output
console = Console()

# Constants for CLI operation
DEFAULT_FORMAT = "markdown"
DEFAULT_STRATEGY = RetrievalStrategy.VECTOR
DEFAULT_LIMIT = 10

def format_error(error: StorageError) -> Panel:
    """Format error message with rich styling."""
    return Panel(
        f"[red bold]{error.message}[/]\n\n"
        f"Error Code: {error.error_code.value}\n"
        f"Details: {json.dumps(error.details, indent=2)}",
        title="Error",
        border_style="red"
    )

@click.command()
@click.option('--file', '-f', required=True, help='Path to document file')
@click.option('--format', default=DEFAULT_FORMAT, help='Document format (markdown, text, json)')
@click.option('--metadata', type=json.loads, default='{}', help='Document metadata as JSON string')
async def store_document(file: str, format: str, metadata: Dict) -> None:
    """
    Store a new document with progress indication and validation.

    Args:
        file: Path to document file
        format: Document format
        metadata: Document metadata as JSON
    """
    try:
        # Validate file exists and is readable
        file_path = Path(file)
        if not file_path.exists():
            raise click.BadParameter(f"File not found: {file}")
        if not file_path.is_file():
            raise click.BadParameter(f"Not a file: {file}")
        if not os.access(file_path, os.R_OK):
            raise click.BadParameter(f"File not readable: {file}")

        # Show progress during file reading
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Reading document...", total=None)
            content = file_path.read_text(encoding='utf-8')

        # Show progress during storage
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Storing document...", total=None)
            
            # Store document
            document_service = DocumentService()
            document_id = await document_service.store_document(
                content=content,
                metadata={
                    "format": format,
                    **metadata
                }
            )

        # Show success message
        console.print(Panel(
            f"[green]Document stored successfully[/]\n\n"
            f"Document ID: {document_id}\n"
            f"Format: {format}\n"
            f"Size: {len(content)} bytes",
            title="Success",
            border_style="green"
        ))

    except StorageError as e:
        console.print(format_error(e))
        raise click.Abort()
    except Exception as e:
        console.print(Panel(
            f"[red bold]Unexpected error: {str(e)}[/]",
            title="Error",
            border_style="red"
        ))
        raise click.Abort()

@click.command()
@click.argument('document_id')
@click.option('--format', default='rich', help='Output format (rich, json, text)')
async def retrieve_document(document_id: str, format: str) -> None:
    """
    Retrieve and display a document with formatted output.

    Args:
        document_id: Document identifier
        format: Output format preference
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Retrieving document...", total=None)
            
            # Retrieve document
            document_service = DocumentService()
            document = await document_service.retrieve_document(document_id)

        if format == 'json':
            # JSON output
            console.print_json(json.dumps(document.to_dict()))
        elif format == 'text':
            # Plain text output
            console.print(document.content)
        else:
            # Rich formatted output
            console.print(Panel(
                Syntax(
                    document.content,
                    document.format,
                    theme="monokai",
                    line_numbers=True
                ),
                title=f"Document {document_id}",
                subtitle=f"Format: {document.format}"
            ))
            
            # Show metadata table
            metadata_table = Table(title="Document Metadata")
            metadata_table.add_column("Key", style="cyan")
            metadata_table.add_column("Value", style="green")
            
            for key, value in document.metadata.items():
                metadata_table.add_row(key, str(value))
            
            console.print(metadata_table)

    except StorageError as e:
        console.print(format_error(e))
        raise click.Abort()
    except Exception as e:
        console.print(Panel(
            f"[red bold]Unexpected error: {str(e)}[/]",
            title="Error",
            border_style="red"
        ))
        raise click.Abort()

@click.command()
@click.argument('query')
@click.option('--strategy', type=click.Choice(['vector', 'llm', 'hybrid', 'rag_kg']), default='vector')
@click.option('--filters', type=json.loads, default='{}', help='Search filters as JSON')
@click.option('--limit', type=int, default=DEFAULT_LIMIT, help='Maximum number of results')
async def search_documents(query: str, strategy: str, filters: Dict, limit: int) -> None:
    """
    Search documents with multiple strategies and filtering.

    Args:
        query: Search query string
        strategy: Search strategy to use
        filters: Search filters
        limit: Maximum number of results
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Searching documents...", total=None)
            
            # Convert strategy string to enum
            retrieval_strategy = RetrievalStrategy(strategy)
            
            # Perform search
            document_service = DocumentService()
            results = await document_service.search_documents(
                query=query,
                strategy=retrieval_strategy,
                filters=filters,
                limit=limit
            )

        # Display results table
        table = Table(title=f"Search Results ({len(results)} found)")
        table.add_column("ID", style="cyan")
        table.add_column("Content Preview", style="green")
        table.add_column("Format", style="blue")
        table.add_column("Score", style="yellow")

        for result in results:
            # Truncate content preview
            preview = result['content'][:100] + "..." if len(result['content']) > 100 else result['content']
            table.add_row(
                str(result['id']),
                preview,
                result['format'],
                f"{result['relevance_score']:.3f}"
            )

        console.print(table)

    except StorageError as e:
        console.print(format_error(e))
        raise click.Abort()
    except Exception as e:
        console.print(Panel(
            f"[red bold]Unexpected error: {str(e)}[/]",
            title="Error",
            border_style="red"
        ))
        raise click.Abort()

@click.command()
@click.argument('document_id')
@click.confirmation_option(prompt='Are you sure you want to delete this document?')
async def delete_document(document_id: str) -> None:
    """
    Delete a document with confirmation and status display.

    Args:
        document_id: Document identifier
    """
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            progress.add_task("Deleting document...", total=None)
            
            # Delete document
            document_service = DocumentService()
            success = await document_service.delete_document(document_id)

        if success:
            console.print(Panel(
                f"[green]Document {document_id} deleted successfully[/]",
                title="Success",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[yellow]Document {document_id} not found[/]",
                title="Warning",
                border_style="yellow"
            ))

    except StorageError as e:
        console.print(format_error(e))
        raise click.Abort()
    except Exception as e:
        console.print(Panel(
            f"[red bold]Unexpected error: {str(e)}[/]",
            title="Error",
            border_style="red"
        ))
        raise click.Abort()