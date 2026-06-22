"""
Graph Adapters - Data source implementations for GraphInterface.

Each adapter provides a different data source:
  - FileGraphAdapter: reads adjacency_cache.pkl (Phase 2 output)
  - FieldDataGraphAdapter: reads field_data_cache.pkl (Phase 4 output)
  - SQLiteGraphAdapter: reads registry.db directly
  - StreamingGraphAdapter: reads graph_events.jsonl (slow fallback)
  - MemoryGraphAdapter: in-memory graph (for testing)
"""

import pickle
import logging
from pathlib import Path
from typing import List, Optional, Set, Dict, Any
from collections import defaultdict

from ..interfaces.graph import GraphInterface, GraphMetadata

logger = logging.getLogger(__name__)


class FileGraphAdapter(GraphInterface):
    """Adapter for adjacency_cache.pkl (Phase 2 output).

    This is the PREFERRED adapter - it reads the pre-computed adjacency
    created by Phase 2, avoiding re-parsing graph_events.jsonl.

    Format:
        {
            "adjacency": {"sym::A": ["sym::B", "sym::C"], ...},
            "in_matrix": {"sym::B": ["sym::A"], ...},
            "metadata": {...}
        }
    """

    def __init__(self, cache_path: Path):
        """Initialize from adjacency_cache.pkl.

        Args:
            cache_path: Path to adjacency_cache.pkl
        """
        self._cache_path = cache_path
        self._adjacency: Dict[str, List[str]] = {}
        self._in_matrix: Dict[str, List[str]] = {}
        self._metadata: Optional[GraphMetadata] = None
        self._nodes: Optional[Set[str]] = None
        self._num_edges: Optional[int] = None
        self._loaded = False

    def _ensure_loaded(self):
        """Lazy load the cache file."""
        if self._loaded:
            return

        logger.info("Loading graph from %s", self._cache_path)
        with open(self._cache_path, 'rb') as f:
            data = pickle.load(f)

        self._adjacency = data.get("adjacency", {})
        self._in_matrix = data.get("in_matrix", {})

        # Build node set
        self._nodes = set(self._adjacency.keys()) | set(self._in_matrix.keys())

        # Count edges
        self._num_edges = sum(len(v) for v in self._adjacency.values())

        # Parse metadata
        meta = data.get("metadata", {})
        self._metadata = GraphMetadata(
            num_nodes=len(self._nodes),
            num_edges=self._num_edges,
            created_at=meta.get("created_at", ""),
            source=meta.get("source", "adjacency_cache.pkl"),
            phase=meta.get("phase", "unknown"),
            version=meta.get("version", "1.0"),
        )

        logger.info(
            "Loaded graph: %d nodes, %d edges",
            self._metadata.num_nodes, self._metadata.num_edges
        )
        self._loaded = True

    def get_out_neighbors(self, node: str) -> List[str]:
        self._ensure_loaded()
        return self._adjacency.get(node, [])

    def get_in_neighbors(self, node: str) -> List[str]:
        self._ensure_loaded()
        return self._in_matrix.get(node, [])

    def get_all_nodes(self) -> List[str]:
        self._ensure_loaded()
        return list(self._nodes)

    def has_node(self, node: str) -> bool:
        self._ensure_loaded()
        return node in self._nodes

    def num_nodes(self) -> int:
        self._ensure_loaded()
        return len(self._nodes)

    def num_edges(self) -> int:
        self._ensure_loaded()
        return self._num_edges

    def get_edge_weight(self, src: str, dst: str) -> Optional[float]:
        # adjacency_cache.pkl doesn't store weights
        return 1.0 if dst in self.get_out_neighbors(src) else None

    @property
    def metadata(self) -> Optional[GraphMetadata]:
        self._ensure_loaded()
        return self._metadata


class FieldDataGraphAdapter(GraphInterface):
    """Adapter for field_data_cache.pkl (Phase 4 output).

    This reads the field data cache created by Phase 4. It contains
    both field states and forward adjacency.
    """

    def __init__(self, cache_path: Path):
        self._cache_path = cache_path
        self._adjacency: Dict[str, List[str]] = {}
        self._in_matrix: Dict[str, List[str]] = defaultdict(list)
        self._nodes: Optional[Set[str]] = None
        self._num_edges: Optional[int] = None
        self._loaded = False

    def _ensure_loaded(self):
        if self._loaded:
            return

        logger.info("Loading graph from field_data_cache.pkl: %s", self._cache_path)
        with open(self._cache_path, 'rb') as f:
            data = pickle.load(f)

        # Extract adjacency from cache
        self._adjacency = data.get("adjacency", {})

        # Build reverse index
        for src, dsts in self._adjacency.items():
            for dst in dsts:
                self._in_matrix[dst].append(src)

        # Build node set
        self._nodes = set(self._adjacency.keys()) | set(self._in_matrix.keys())
        self._num_edges = sum(len(v) for v in self._adjacency.values())

        logger.info("Loaded graph: %d nodes, %d edges", len(self._nodes), self._num_edges)
        self._loaded = True

    def get_out_neighbors(self, node: str) -> List[str]:
        self._ensure_loaded()
        return self._adjacency.get(node, [])

    def get_in_neighbors(self, node: str) -> List[str]:
        self._ensure_loaded()
        return self._in_matrix.get(node, [])

    def get_all_nodes(self) -> List[str]:
        self._ensure_loaded()
        return list(self._nodes)

    def has_node(self, node: str) -> bool:
        self._ensure_loaded()
        return node in self._nodes

    def num_nodes(self) -> int:
        self._ensure_loaded()
        return len(self._nodes)

    def num_edges(self) -> int:
        self._ensure_loaded()
        return self._num_edges

    def get_edge_weight(self, src: str, dst: str) -> Optional[float]:
        return 1.0 if dst in self.get_out_neighbors(src) else None

    @property
    def metadata(self) -> Optional[GraphMetadata]:
        self._ensure_loaded()
        return GraphMetadata(
            num_nodes=len(self._nodes),
            num_edges=self._num_edges,
            created_at="unknown",
            source="field_data_cache.pkl",
            phase="phase4",
            version="1.0",
        )


class MemoryGraphAdapter(GraphInterface):
    """In-memory graph adapter for testing.

    Allows building a graph programmatically for unit tests.
    """

    def __init__(self):
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._in_matrix: Dict[str, List[str]] = defaultdict(list)
        self._edge_weights: Dict[tuple, float] = {}
        self._nodes: Optional[Set[str]] = None

    def add_edge(self, src: str, dst: str, weight: float = 1.0):
        """Add an edge to the graph."""
        if dst not in self._adjacency[src]:
            self._adjacency[src].append(dst)
            self._in_matrix[dst].append(src)
            self._edge_weights[(src, dst)] = weight
        self._nodes = None  # Invalidate cache

    def add_node(self, node: str):
        """Add a node with no edges."""
        if node not in self._adjacency:
            self._adjacency[node] = []
        if node not in self._in_matrix:
            self._in_matrix[node] = []
        self._nodes = None

    def _ensure_nodes(self):
        if self._nodes is None:
            self._nodes = set(self._adjacency.keys()) | set(self._in_matrix.keys())

    def get_out_neighbors(self, node: str) -> List[str]:
        return self._adjacency.get(node, [])

    def get_in_neighbors(self, node: str) -> List[str]:
        return self._in_matrix.get(node, [])

    def get_all_nodes(self) -> List[str]:
        self._ensure_nodes()
        return list(self._nodes)

    def has_node(self, node: str) -> bool:
        self._ensure_nodes()
        return node in self._nodes

    def num_nodes(self) -> int:
        self._ensure_nodes()
        return len(self._nodes)

    def num_edges(self) -> int:
        return len(self._edge_weights)

    def get_edge_weight(self, src: str, dst: str) -> Optional[float]:
        return self._edge_weights.get((src, dst))


class StreamingGraphAdapter(GraphInterface):
    """Adapter for graph_events.jsonl (slow fallback).

    This parses graph_events.jsonl line by line. Use only as last resort
    when no cache is available.
    """

    def __init__(self, events_path: Path):
        self._events_path = events_path
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._in_matrix: Dict[str, List[str]] = defaultdict(list)
        self._nodes: Optional[Set[str]] = None
        self._num_edges: Optional[int] = None
        self._loaded = False

    def _ensure_loaded(self):
        """Load and index the entire file."""
        import json
        import time

        if self._loaded:
            return

        logger.warning(
            "Using slow StreamingGraphAdapter for %s. "
            "Run Phase 2 to create adjacency_cache.pkl for faster access.",
            self._events_path
        )

        start_time = time.time()
        last_log = start_time
        line_count = 0
        edge_count = 0

        with open(self._events_path, 'r') as f:
            for line in f:
                line_count += 1
                current_time = time.time()

                # Progress every 1M lines or 5 seconds
                if line_count % 1_000_000 == 0 or (current_time - last_log) > 5:
                    elapsed = current_time - start_time
                    rate = line_count / elapsed / 1_000_000
                    logger.info(
                        "Parsing graph_events.jsonl: %dM lines, %d edges (%.1fM lines/s)",
                        line_count // 1_000_000, edge_count, rate
                    )
                    last_log = current_time

                if not line.strip():
                    continue

                try:
                    event = json.loads(line)
                    event_type = event.get("event_type")

                    if event_type == "EDGE_TRAVERSE":
                        edge = event.get("edge", {})
                        src = edge.get("src")
                        dst = edge.get("dst")
                        if src and dst:
                            self._adjacency[src].append(dst)
                            self._in_matrix[dst].append(src)
                            edge_count += 1
                    elif "dst" in event:  # Legacy format
                        src = event.get("src")
                        dst = event.get("dst")
                        if src and dst:
                            self._adjacency[src].append(dst)
                            self._in_matrix[dst].append(src)
                            edge_count += 1

                except json.JSONDecodeError:
                    continue

        self._nodes = set(self._adjacency.keys()) | set(self._in_matrix.keys())
        self._num_edges = edge_count

        elapsed = time.time() - start_time
        logger.info(
            "Loaded graph from JSONL: %d nodes, %d edges in %.1fs",
            len(self._nodes), self._num_edges, elapsed
        )
        self._loaded = True

    def get_out_neighbors(self, node: str) -> List[str]:
        self._ensure_loaded()
        return self._adjacency.get(node, [])

    def get_in_neighbors(self, node: str) -> List[str]:
        self._ensure_loaded()
        return self._in_matrix.get(node, [])

    def get_all_nodes(self) -> List[str]:
        self._ensure_loaded()
        return list(self._nodes)

    def has_node(self, node: str) -> bool:
        self._ensure_loaded()
        return node in self._nodes

    def num_nodes(self) -> int:
        self._ensure_loaded()
        return len(self._nodes)

    def num_edges(self) -> int:
        self._ensure_loaded()
        return self._num_edges

    def get_edge_weight(self, src: str, dst: str) -> Optional[float]:
        return 1.0 if dst in self.get_out_neighbors(src) else None

    @property
    def metadata(self) -> Optional[GraphMetadata]:
        self._ensure_loaded()
        return GraphMetadata(
            num_nodes=len(self._nodes),
            num_edges=self._num_edges,
            created_at="unknown",
            source="field_data_cache.pkl",
            phase="phase4",
            version="1.0",
        )


__all__ = [
    "FileGraphAdapter",
    "FieldDataGraphAdapter",
    "MemoryGraphAdapter",
    "StreamingGraphAdapter",
]
