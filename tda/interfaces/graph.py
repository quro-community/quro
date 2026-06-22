"""
Graph Abstraction Layer for TDA Pipeline

This module provides a clean separation between graph data storage and graph algorithms.
All TDA phases should use GraphInterface instead of directly loading files.

Architecture:
  Raw Data → Adapters → GraphInterface → TDA Algorithms
                 ↑
    Multiple implementations: File, SQLite, Memory, Streaming
"""

from abc import ABC, abstractmethod
from collections import deque
from typing import List, Set, Tuple, Optional, Dict, Any
from dataclasses import dataclass


class GraphInterface(ABC):
    """Abstract interface for graph data access.

    This decouples graph storage (file, DB, memory) from graph algorithms.
    Implement this interface to provide custom graph sources.

    Example:
        # All TDA phases use this interface
        class CenterDetector:
            def __init__(self, graph: GraphInterface):
                self.graph = graph

            def detect_centers(self):
                for node in self.graph.get_all_nodes():
                    neighbors = self.graph.get_out_neighbors(node)
                    # ... algorithm
    """

    @abstractmethod
    def get_out_neighbors(self, node: str) -> List[str]:
        """Get all nodes that this node points to (outgoing edges)."""
        pass

    @abstractmethod
    def get_in_neighbors(self, node: str) -> List[str]:
        """Get all nodes that point to this node (incoming edges)."""
        pass

    @abstractmethod
    def get_all_nodes(self) -> List[str]:
        """Get all nodes in the graph."""
        pass

    @abstractmethod
    def has_node(self, node: str) -> bool:
        """Check if a node exists in the graph."""
        pass

    @abstractmethod
    def num_nodes(self) -> int:
        """Get total number of nodes."""
        pass

    @abstractmethod
    def num_edges(self) -> int:
        """Get total number of edges."""
        pass

    @abstractmethod
    def get_edge_weight(self, src: str, dst: str) -> Optional[float]:
        """Get weight of edge from src to dst, or None if not exists."""
        pass

    def out_degree(self, node: str) -> int:
        """Get number of outgoing edges."""
        return len(self.get_out_neighbors(node))

    def in_degree(self, node: str) -> int:
        """Get number of incoming edges."""
        return len(self.get_in_neighbors(node))

    def degree(self, node: str) -> int:
        """Get total degree (in + out)."""
        return self.out_degree(node) + self.in_degree(node)

    def bfs(
        self,
        start: str,
        max_depth: int = 10,
        direction: str = "out"
    ) -> List[Tuple[str, int]]:
        """BFS traversal returning (node, depth) pairs.

        Args:
            start: Starting node
            max_depth: Maximum traversal depth
            direction: "out" for outgoing, "in" for incoming, "both" for undirected

        Returns:
            List of (node, depth) tuples in BFS order
        """
        neighbors_fn = {
            "out": self.get_out_neighbors,
            "in": self.get_in_neighbors,
            "both": lambda n: self.get_out_neighbors(n) + self.get_in_neighbors(n),
        }[direction]

        queue = deque([(start, 0)])
        visited: Set[str] = {start}
        result: List[Tuple[str, int]] = []

        while queue:
            node, depth = queue.popleft()
            result.append((node, depth))
            if depth < max_depth:
                for neighbor in neighbors_fn(node):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, depth + 1))

        return result

    def find_path(
        self,
        src: str,
        dst: str,
        max_depth: int = 10,
        direction: str = "out"
    ) -> Optional[List[str]]:
        """Find path from src to dst using BFS.

        Args:
            src: Source node
            dst: Target node
            max_depth: Maximum search depth
            direction: "out", "in", or "both"

        Returns:
            Path as list of nodes, or None if no path found
        """
        if src == dst:
            return [src]

        neighbors_fn = {
            "out": self.get_out_neighbors,
            "in": self.get_in_neighbors,
            "both": lambda n: self.get_out_neighbors(n) + self.get_in_neighbors(n),
        }[direction]

        queue = deque([(src, [src])])
        visited: Set[str] = {src}

        while queue:
            node, path = queue.popleft()
            if len(path) > max_depth:
                continue
            for neighbor in neighbors_fn(node):
                if neighbor == dst:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def subgraph(self, nodes: Set[str]) -> "GraphInterface":
        """Return subgraph containing only the specified nodes."""
        return SubgraphView(self, nodes)


@dataclass
class GraphMetadata:
    """Metadata about a graph source."""
    num_nodes: int
    num_edges: int
    created_at: str
    source: str  # "adjacency_cache.pkl", "registry.db", "graph_events.jsonl"
    phase: str   # "phase2", "phase4", etc.
    version: str = "1.0"


class SubgraphView(GraphInterface):
    """Read-only view of a subgraph."""

    def __init__(self, parent: GraphInterface, nodes: Set[str]):
        self._parent = parent
        self._nodes = nodes

    def get_out_neighbors(self, node: str) -> List[str]:
        if node not in self._nodes:
            return []
        return [
            n for n in self._parent.get_out_neighbors(node)
            if n in self._nodes
        ]

    def get_in_neighbors(self, node: str) -> List[str]:
        if node not in self._nodes:
            return []
        return [
            n for n in self._parent.get_in_neighbors(node)
            if n in self._nodes
        ]

    def get_all_nodes(self) -> List[str]:
        return list(self._nodes)

    def has_node(self, node: str) -> bool:
        return node in self._nodes

    def num_nodes(self) -> int:
        return len(self._nodes)

    def num_edges(self) -> int:
        count = 0
        for node in self._nodes:
            count += len(self.get_out_neighbors(node))
        return count

    def get_edge_weight(self, src: str, dst: str) -> Optional[float]:
        if src not in self._nodes or dst not in self._nodes:
            return None
        return self._parent.get_edge_weight(src, dst)


__all__ = ["GraphInterface", "GraphMetadata", "SubgraphView"]
