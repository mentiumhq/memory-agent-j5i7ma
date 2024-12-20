"""
Temporal workflow definitions for document search operations implementing multiple retrieval
strategies including vector-based search, pure LLM reasoning, hybrid approaches, and RAG
with Knowledge Graphs.

Version: 1.0.0
External Dependencies:
- temporalio==1.0.0: Temporal workflow SDK
- opentelemetry-api==1.0.0: Distributed tracing
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from uuid import UUID

from temporalio import workflow
from opentelemetry import trace
from opentelemetry.trace import Span

from ..activities.llm_activities import reason_documents, select_documents
from ..activities.index_activities import (
    get_document_index_activity,
    record_document_access_activity
)
from ..core.errors import WorkflowError, ErrorCode

# Initialize logging
logger = logging.getLogger(__name__)

# Initialize tracer
tracer = trace.get_tracer("search_workflows")

# Workflow retry configuration
WORKFLOW_RETRY_POLICY = {
    "initial_interval": 1,
    "backoff_coefficient": 2,
    "maximum_attempts": 5,
    "maximum_interval": 30
}

# Search strategy constants
SEARCH_STRATEGIES = {
    "VECTOR": "vector",
    "LLM": "llm",
    "HYBRID": "hybrid",
    "RAG_KG": "rag_kg"
}

# Performance thresholds in milliseconds
PERFORMANCE_THRESHOLDS = {
    "VECTOR_SEARCH_MS": 500,
    "LLM_SEARCH_MS": 3000,
    "HYBRID_SEARCH_MS": 3500,
    "RAG_KG_SEARCH_MS": 4000
}

@workflow.defn(name="vector_search_workflow")
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
class VectorSearchWorkflow:
    """Workflow for vector-based document search using embeddings."""

    @workflow.run
    async def run(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: Optional[int] = 10
    ) -> List[Dict]:
        """
        Execute vector-based document search with performance monitoring.

        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum number of results

        Returns:
            List of relevant documents with confidence scores
        """
        with tracer.start_as_current_span("vector_search") as span:
            try:
                start_time = datetime.now(timezone.utc)

                # Get candidate documents using vector search
                candidates = await workflow.execute_activity(
                    get_document_index_activity,
                    query,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["VECTOR_SEARCH_MS"]
                )

                # Record access patterns for retrieved documents
                for doc in candidates:
                    await workflow.execute_activity(
                        record_document_access_activity,
                        UUID(doc["id"])
                    )

                # Track performance metrics
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                span.set_attribute("duration_seconds", duration)
                span.set_attribute("document_count", len(candidates))

                return candidates[:limit] if limit else candidates

            except Exception as e:
                logger.error(f"Vector search workflow failed: {str(e)}")
                span.set_attribute("error", str(e))
                raise WorkflowError(
                    "Vector search failed",
                    ErrorCode.WORKFLOW_ERROR,
                    {"error": str(e)}
                )

@workflow.defn(name="llm_search_workflow")
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
class LLMSearchWorkflow:
    """Workflow for pure LLM-based document search using reasoning."""

    @workflow.run
    async def run(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: Optional[int] = 10
    ) -> List[Dict]:
        """
        Execute LLM-based document search with reasoning.

        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum number of results

        Returns:
            List of relevant documents with reasoning context
        """
        with tracer.start_as_current_span("llm_search") as span:
            try:
                start_time = datetime.now(timezone.utc)

                # Get candidate documents
                candidates = await workflow.execute_activity(
                    get_document_index_activity,
                    query,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["LLM_SEARCH_MS"]
                )

                # Perform LLM reasoning on candidates
                reasoning_results = await workflow.execute_activity(
                    reason_documents,
                    query,
                    candidates,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["LLM_SEARCH_MS"]
                )

                # Select most relevant documents based on reasoning
                selected_docs = await workflow.execute_activity(
                    select_documents,
                    query,
                    reasoning_results,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["LLM_SEARCH_MS"]
                )

                # Record access patterns
                for doc in selected_docs:
                    await workflow.execute_activity(
                        record_document_access_activity,
                        UUID(doc["id"])
                    )

                # Track performance metrics
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                span.set_attribute("duration_seconds", duration)
                span.set_attribute("document_count", len(selected_docs))

                return selected_docs[:limit] if limit else selected_docs

            except Exception as e:
                logger.error(f"LLM search workflow failed: {str(e)}")
                span.set_attribute("error", str(e))
                raise WorkflowError(
                    "LLM search failed",
                    ErrorCode.WORKFLOW_ERROR,
                    {"error": str(e)}
                )

@workflow.defn(name="hybrid_search_workflow")
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
class HybridSearchWorkflow:
    """Workflow combining vector and LLM-based search approaches."""

    @workflow.run
    async def run(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: Optional[int] = 10
    ) -> List[Dict]:
        """
        Execute hybrid document search combining multiple strategies.

        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum number of results

        Returns:
            List of relevant documents using hybrid approach
        """
        with tracer.start_as_current_span("hybrid_search") as span:
            try:
                start_time = datetime.now(timezone.utc)

                # Get initial candidates using vector search
                vector_candidates = await workflow.execute_activity(
                    get_document_index_activity,
                    query,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["VECTOR_SEARCH_MS"]
                )

                # Perform LLM reasoning on vector candidates
                reasoning_results = await workflow.execute_activity(
                    reason_documents,
                    query,
                    vector_candidates,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["LLM_SEARCH_MS"]
                )

                # Final selection combining both approaches
                selected_docs = await workflow.execute_activity(
                    select_documents,
                    query,
                    reasoning_results,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["HYBRID_SEARCH_MS"]
                )

                # Record access patterns
                for doc in selected_docs:
                    await workflow.execute_activity(
                        record_document_access_activity,
                        UUID(doc["id"])
                    )

                # Track performance metrics
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                span.set_attribute("duration_seconds", duration)
                span.set_attribute("document_count", len(selected_docs))

                return selected_docs[:limit] if limit else selected_docs

            except Exception as e:
                logger.error(f"Hybrid search workflow failed: {str(e)}")
                span.set_attribute("error", str(e))
                raise WorkflowError(
                    "Hybrid search failed",
                    ErrorCode.WORKFLOW_ERROR,
                    {"error": str(e)}
                )

@workflow.defn(name="rag_kg_search_workflow")
@workflow.retry_policy(WORKFLOW_RETRY_POLICY)
class RAGKGSearchWorkflow:
    """Workflow for RAG with Knowledge Graph based document search."""

    @workflow.run
    async def run(
        self,
        query: str,
        filters: Optional[Dict] = None,
        limit: Optional[int] = 10
    ) -> List[Dict]:
        """
        Execute RAG+KG document search with relationship context.

        Args:
            query: Search query string
            filters: Optional search filters
            limit: Maximum number of results

        Returns:
            List of relevant documents using RAG+KG approach
        """
        with tracer.start_as_current_span("rag_kg_search") as span:
            try:
                start_time = datetime.now(timezone.utc)

                # Get documents from knowledge graph
                kg_candidates = await workflow.execute_activity(
                    get_document_index_activity,
                    query,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["RAG_KG_SEARCH_MS"]
                )

                # Perform LLM reasoning with graph context
                reasoning_results = await workflow.execute_activity(
                    reason_documents,
                    query,
                    kg_candidates,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["RAG_KG_SEARCH_MS"]
                )

                # Select documents using graph relationships
                selected_docs = await workflow.execute_activity(
                    select_documents,
                    query,
                    reasoning_results,
                    start_to_close_timeout=PERFORMANCE_THRESHOLDS["RAG_KG_SEARCH_MS"]
                )

                # Record access patterns
                for doc in selected_docs:
                    await workflow.execute_activity(
                        record_document_access_activity,
                        UUID(doc["id"])
                    )

                # Track performance metrics
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()
                span.set_attribute("duration_seconds", duration)
                span.set_attribute("document_count", len(selected_docs))

                return selected_docs[:limit] if limit else selected_docs

            except Exception as e:
                logger.error(f"RAG+KG search workflow failed: {str(e)}")
                span.set_attribute("error", str(e))
                raise WorkflowError(
                    "RAG+KG search failed",
                    ErrorCode.WORKFLOW_ERROR,
                    {"error": str(e)}
                )

# Export workflow classes
__all__ = [
    "VectorSearchWorkflow",
    "LLMSearchWorkflow", 
    "HybridSearchWorkflow",
    "RAGKGSearchWorkflow"
]