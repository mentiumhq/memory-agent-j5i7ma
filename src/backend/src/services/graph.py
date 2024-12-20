"""
Knowledge Graph service implementation for document relationships and retrieval.
Provides optimized graph-based document search with weighted relationships,
entity extraction, and caching capabilities.

Version:
- networkx==3.1+
- numpy==1.24+
"""

import logging
import json
from typing import Optional, List, Dict, Any, Tuple
import threading
import time
from collections import defaultdict

import networkx as nx
import numpy as np

from db.models.document import Document
from db.models.document_chunk import DocumentChunk
from repositories.document import DocumentRepository
from core.errors import StorageError, ErrorCode

# Configure logging
logger = logging.getLogger(__name__)

# Constants for graph operations
SIMILARITY_THRESHOLD = 0.7
MAX_GRAPH_DEPTH = 3
CACHE_TTL = 3600  # Cache TTL in seconds
MIN_RELATIONSHIP_WEIGHT = 0.1

class GraphService:
    """
    Enhanced service for managing document relationships in a knowledge graph structure
    with optimized performance and concurrent access support.
    """

    def __init__(self, document_repository: DocumentRepository) -> None:
        """
        Initialize graph service with document repository and thread-safe access.

        Args:
            document_repository: Repository for document operations
        """
        # Initialize NetworkX graph with metadata
        self._graph = nx.Graph(
            created_at=time.time(),
            last_modified=time.time(),
            document_count=0,
            relationship_count=0
        )
        
        self._document_repository = document_repository
        self._graph_lock = threading.Lock()
        self._cache: Dict[str, Tuple[float, Any]] = {}  # (timestamp, data)

    def add_document(self, document_id: str) -> bool:
        """
        Add document to knowledge graph with extracted entities and weighted relationships.

        Args:
            document_id: Unique identifier of document to add

        Returns:
            bool: Success status of graph update

        Raises:
            StorageError: If document retrieval or graph operation fails
        """
        try:
            with self._graph_lock:
                # Retrieve document with chunks
                document = self._document_repository.get_with_chunks(document_id)
                if not document:
                    raise StorageError(
                        "Document not found",
                        ErrorCode.DOCUMENT_NOT_FOUND,
                        {"document_id": document_id}
                    )

                # Extract entities from document content
                entities = self._extract_entities(document)

                # Create document node with metadata
                self._graph.add_node(
                    document_id,
                    type="document",
                    format=document.format,
                    metadata=document.metadata,
                    entities=entities,
                    added_at=time.time()
                )

                # Create entity nodes and relationships
                for entity, weight in entities.items():
                    entity_id = f"entity:{entity}"
                    if not self._graph.has_node(entity_id):
                        self._graph.add_node(
                            entity_id,
                            type="entity",
                            name=entity,
                            document_count=1
                        )
                    self._graph.add_edge(
                        document_id,
                        entity_id,
                        weight=weight,
                        type="contains"
                    )

                # Update graph metadata
                self._graph.graph["document_count"] += 1
                self._graph.graph["last_modified"] = time.time()
                self._graph.graph["relationship_count"] = self._graph.number_of_edges()

                # Clear affected cache entries
                self._clear_related_cache(document_id)

                return True

        except Exception as e:
            logger.error(f"Error adding document to graph: {str(e)}")
            raise StorageError(
                "Failed to add document to graph",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

    def find_related_documents(
        self,
        document_id: str,
        max_depth: Optional[int] = None,
        min_similarity: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Find documents related to given document through weighted graph traversal.

        Args:
            document_id: Source document identifier
            max_depth: Maximum traversal depth (default: MAX_GRAPH_DEPTH)
            min_similarity: Minimum similarity threshold (default: SIMILARITY_THRESHOLD)

        Returns:
            List of related documents with relevance scores and relationship metadata

        Raises:
            StorageError: If graph traversal fails
        """
        # Use default values if not specified
        max_depth = max_depth or MAX_GRAPH_DEPTH
        min_similarity = min_similarity or SIMILARITY_THRESHOLD

        # Check cache first
        cache_key = f"related:{document_id}:{max_depth}:{min_similarity}"
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result

        try:
            with self._graph_lock:
                if not self._graph.has_node(document_id):
                    raise StorageError(
                        "Document not found in graph",
                        ErrorCode.DOCUMENT_NOT_FOUND,
                        {"document_id": document_id}
                    )

                # Perform weighted breadth-first traversal
                related_docs = []
                visited = {document_id}
                queue = [(document_id, 0, 1.0)]  # (node, depth, strength)

                while queue and len(related_docs) < 100:  # Limit results
                    current_id, depth, strength = queue.pop(0)

                    if depth > max_depth:
                        continue

                    # Get neighbors through entities
                    for _, entity_id in self._graph.edges(current_id):
                        if self._graph.nodes[entity_id]["type"] != "entity":
                            continue

                        # Find documents connected to this entity
                        for doc_id in self._graph.neighbors(entity_id):
                            if (
                                self._graph.nodes[doc_id]["type"] == "document"
                                and doc_id not in visited
                            ):
                                edge_weight = self._graph.edges[entity_id, doc_id]["weight"]
                                path_strength = strength * edge_weight

                                if path_strength >= min_similarity:
                                    visited.add(doc_id)
                                    queue.append((doc_id, depth + 1, path_strength))
                                    
                                    # Add to results with metadata
                                    doc_node = self._graph.nodes[doc_id]
                                    related_docs.append({
                                        "document_id": doc_id,
                                        "relevance_score": path_strength,
                                        "depth": depth + 1,
                                        "metadata": doc_node.get("metadata", {}),
                                        "common_entities": self._get_common_entities(
                                            document_id, doc_id
                                        )
                                    })

                # Sort by relevance score
                related_docs.sort(key=lambda x: x["relevance_score"], reverse=True)

                # Cache results
                self._add_to_cache(cache_key, related_docs)

                return related_docs

        except Exception as e:
            logger.error(f"Error finding related documents: {str(e)}")
            raise StorageError(
                "Failed to find related documents",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

    def update_relationships(self, document_id: str, force_update: Optional[bool] = False) -> bool:
        """
        Update document relationships with optimized weight recalculation.

        Args:
            document_id: Document identifier
            force_update: Force full relationship update

        Returns:
            bool: Success status of update

        Raises:
            StorageError: If relationship update fails
        """
        try:
            with self._graph_lock:
                if not self._graph.has_node(document_id):
                    raise StorageError(
                        "Document not found in graph",
                        ErrorCode.DOCUMENT_NOT_FOUND,
                        {"document_id": document_id}
                    )

                # Get current document node
                doc_node = self._graph.nodes[document_id]

                # Remove existing relationships if forced
                if force_update:
                    edges_to_remove = list(self._graph.edges(document_id))
                    self._graph.remove_edges_from(edges_to_remove)

                # Get updated document content
                document = self._document_repository.get_with_chunks(document_id)
                if not document:
                    raise StorageError(
                        "Document not found in repository",
                        ErrorCode.DOCUMENT_NOT_FOUND,
                        {"document_id": document_id}
                    )

                # Extract updated entities
                new_entities = self._extract_entities(document)

                # Update node metadata
                doc_node["entities"] = new_entities
                doc_node["metadata"] = document.metadata
                doc_node["updated_at"] = time.time()

                # Update relationships
                for entity, weight in new_entities.items():
                    entity_id = f"entity:{entity}"
                    if not self._graph.has_node(entity_id):
                        self._graph.add_node(
                            entity_id,
                            type="entity",
                            name=entity,
                            document_count=1
                        )
                    self._graph.add_edge(
                        document_id,
                        entity_id,
                        weight=weight,
                        type="contains"
                    )

                # Update graph metadata
                self._graph.graph["last_modified"] = time.time()
                self._graph.graph["relationship_count"] = self._graph.number_of_edges()

                # Clear affected cache
                self._clear_related_cache(document_id)

                return True

        except Exception as e:
            logger.error(f"Error updating relationships: {str(e)}")
            raise StorageError(
                "Failed to update relationships",
                ErrorCode.STORAGE_ERROR,
                {"document_id": document_id, "error": str(e)}
            )

    def _extract_entities(self, document: Document) -> Dict[str, float]:
        """
        Extract weighted entities from document content using NLP processing.

        Args:
            document: Document instance with content

        Returns:
            Dictionary of entity-weight pairs
        """
        entities = defaultdict(float)
        
        # Process main document content
        main_entities = self._process_content(document.content)
        for entity, weight in main_entities.items():
            entities[entity] += weight * 0.6  # Main content weight

        # Process chunks for additional context
        for chunk in document.chunks:
            chunk_entities = self._process_content(chunk.content)
            for entity, weight in chunk_entities.items():
                entities[entity] += weight * 0.4  # Chunk weight

        # Normalize weights
        max_weight = max(entities.values()) if entities else 1.0
        return {
            entity: max(weight / max_weight, MIN_RELATIONSHIP_WEIGHT)
            for entity, weight in entities.items()
        }

    def _process_content(self, content: str) -> Dict[str, float]:
        """
        Process text content to extract weighted entities.

        Args:
            content: Text content to process

        Returns:
            Dictionary of entity-weight pairs
        """
        # Placeholder for NLP processing
        # In production, this would use spaCy or similar NLP library
        entities = {}
        words = content.lower().split()
        word_count = len(words)
        
        for word in words:
            if len(word) > 3:  # Simple filtering
                entities[word] = entities.get(word, 0) + 1

        # Convert counts to weights
        return {
            entity: count / word_count
            for entity, count in entities.items()
        }

    def _get_common_entities(self, doc_id1: str, doc_id2: str) -> List[Dict[str, Any]]:
        """
        Get common entities between two documents with weights.

        Args:
            doc_id1: First document ID
            doc_id2: Second document ID

        Returns:
            List of common entities with weights
        """
        entities1 = set(
            neighbor for neighbor in self._graph.neighbors(doc_id1)
            if self._graph.nodes[neighbor]["type"] == "entity"
        )
        entities2 = set(
            neighbor for neighbor in self._graph.neighbors(doc_id2)
            if self._graph.nodes[neighbor]["type"] == "entity"
        )

        common_entities = []
        for entity_id in entities1 & entities2:
            weight1 = self._graph.edges[doc_id1, entity_id]["weight"]
            weight2 = self._graph.edges[doc_id2, entity_id]["weight"]
            common_entities.append({
                "entity": self._graph.nodes[entity_id]["name"],
                "weight": (weight1 + weight2) / 2
            })

        return sorted(common_entities, key=lambda x: x["weight"], reverse=True)

    def _add_to_cache(self, key: str, value: Any) -> None:
        """Add value to cache with timestamp."""
        self._cache[key] = (time.time(), value)

    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < CACHE_TTL:
                return value
            del self._cache[key]
        return None

    def _clear_related_cache(self, document_id: str) -> None:
        """Clear cache entries related to document."""
        keys_to_remove = [
            key for key in self._cache
            if document_id in key
        ]
        for key in keys_to_remove:
            del self._cache[key]