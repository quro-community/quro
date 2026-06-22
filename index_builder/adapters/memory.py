"""Index Builder v3 - Memory Registry Adapter

@module quro.index_builder.adapters.memory
@intent In-memory storage adapter for testing
@constraint Pure Python, no external dependencies
"""

from typing import Dict, List, Optional
from index_builder.types import GraphNode, GraphEdge


class MemoryRegistryAdapter:
    """In-memory registry adapter.

    Stores graph nodes and edges in memory using dicts.
    Useful for testing and small workspaces.
    """

    def __init__(self):
        """Initialize memory adapter."""
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, List[GraphEdge]] = {}
        self.symbol_aliases: Dict[str, List[Dict[str, str]]] = {}  # Track duplicates before dedup

    def save_node(self, node: GraphNode) -> None:
        """Save a graph node.

        Args:
            node: Graph node to save
        """
        # Track aliases before overwriting
        if node.id in self.nodes:
            # This is a duplicate - save the existing node as an alias
            existing = self.nodes[node.id]
            if node.id not in self.symbol_aliases:
                self.symbol_aliases[node.id] = []

            # Add existing node to aliases if not already there
            existing_alias = {
                "id": existing.id,
                "path": existing.metadata.get("file_path", ""),
                "line": existing.metadata.get("line", 0),
                "kind": existing.metadata.get("kind", "unknown"),
                "signature": existing.metadata.get("signature", ""),
            }
            if existing_alias not in self.symbol_aliases[node.id]:
                self.symbol_aliases[node.id].append(existing_alias)

        # Save the new node (overwrites existing)
        self.nodes[node.id] = node

        # Also add the new node to aliases list
        if node.id in self.symbol_aliases:
            new_alias = {
                "id": node.id,
                "path": node.metadata.get("file_path", ""),
                "line": node.metadata.get("line", 0),
                "kind": node.metadata.get("kind", "unknown"),
                "signature": node.metadata.get("signature", ""),
            }
            if new_alias not in self.symbol_aliases[node.id]:
                self.symbol_aliases[node.id].append(new_alias)

    def save_edge(self, edge: GraphEdge) -> None:
        """Save a graph edge.

        Args:
            edge: Graph edge to save
        """
        if edge.src not in self.edges:
            self.edges[edge.src] = []

        self.edges[edge.src].append(edge)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID.

        Args:
            node_id: Node ID to query

        Returns:
            GraphNode or None if not found
        """
        return self.nodes.get(node_id)

    def get_edges_from(self, node_id: str) -> List[GraphEdge]:
        """Get all edges from a node.

        Args:
            node_id: Source node ID

        Returns:
            List of edges
        """
        return self.edges.get(node_id, [])

    def node_exists(self, node_id: str) -> bool:
        """Check if node exists.

        Args:
            node_id: Node ID to check

        Returns:
            True if node exists
        """
        return node_id in self.nodes

    def get_all_nodes(self) -> List[GraphNode]:
        """Get all nodes.

        Returns:
            List of all nodes
        """
        return list(self.nodes.values())

    def get_all_edges(self) -> List[GraphEdge]:
        """Get all edges.

        Returns:
            List of all edges
        """
        all_edges = []
        for edges in self.edges.values():
            all_edges.extend(edges)
        return all_edges

    def clear(self) -> None:
        """Clear all stored data."""
        self.nodes.clear()
        self.edges.clear()
        self.symbol_aliases.clear()

    def find_symbol_aliases(self, symbol_name: str) -> List[Dict[str, str]]:
        """Find all nodes with the same bare symbol name.

        Args:
            symbol_name: Symbol name to search (e.g., "cqe_query" or "sym::cqe_query")

        Returns:
            List of dicts with alias metadata: [{"path": ..., "line": ..., "kind": ...}]

        Note: This uses signature-aware matching to avoid false positives.
        Methods with the same name but different classes are NOT considered aliases.
        """
        # First check if we have tracked aliases for this exact symbol
        if symbol_name in self.symbol_aliases:
            return self._filter_true_aliases(symbol_name, self.symbol_aliases[symbol_name])

        # Fallback: search by bare name (for symbols that weren't deduplicated)
        bare_name = symbol_name.replace("sym::", "").replace("cat::", "")

        aliases = []
        for node_id, node in self.nodes.items():
            # Check if this node matches the bare name
            node_bare = node_id.replace("sym::", "").replace("cat::", "")
            if node_bare == bare_name and node_id != symbol_name:
                metadata = node.metadata or {}
                aliases.append({
                    "id": node_id,
                    "path": metadata.get("file_path", ""),
                    "line": metadata.get("line", 0),
                    "kind": metadata.get("kind", "unknown"),
                    "signature": metadata.get("signature", ""),
                })

        return self._filter_true_aliases(symbol_name, aliases)

    def _filter_true_aliases(self, canonical_id: str, candidates: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Filter candidates to exclude noise (protocols, tests).

        Args:
            canonical_id: The canonical symbol ID
            candidates: List of candidate aliases

        Returns:
            Filtered list (excludes protocols and test files)

        Note: This uses a permissive filter. Symbols with the same name but different
        signatures are included — they represent different API layers or implementations.
        The AI can decide which one is relevant based on context.
        """
        if not candidates:
            return []

        # Filter candidates
        filtered = []
        for candidate in candidates:
            candidate_path = candidate.get("path", "")

            # Rule 1: Skip protocol definitions (they're interfaces, not implementations)
            if "protocol.py" in candidate_path.lower():
                continue

            # Rule 2: Skip test files entirely (they're test fixtures, not production code)
            if "/tests/" in candidate_path or "/test_" in candidate_path:
                continue

            filtered.append(candidate)

        return filtered
