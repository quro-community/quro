"""Index Builder v3 - Core Converter

@module quro.index_builder.core.converter
@intent Convert SymbolInfo to GraphNode/GraphEdge
@constraint Pure functions, no I/O
"""

from typing import List, Tuple, Any
from dataclasses import dataclass
from scanner.types import SymbolInfo
from index_builder.types import GraphNode, GraphEdge, EnrichedSymbol, EdgeWeightConfig

class SymbolConverter:
    """Convert SymbolInfo to graph structures.

    Pure converter - no I/O, no side effects.
    Uses an injected EdgeWeightConfig for edge generation.
    """

    def __init__(self, edge_config: EdgeWeightConfig = None):
        self.edge_config = edge_config or EdgeWeightConfig()

    @staticmethod
    def to_graph_node(enriched: EnrichedSymbol) -> GraphNode:
        """Convert EnrichedSymbol to GraphNode.

        Pure function: EnrichedSymbol → GraphNode

        Args:
            enriched: Enriched symbol information

        Returns:
            GraphNode for CQE
        """
        symbol_info = enriched.base
        
        # Create node ID
        node_id = f"sym::{symbol_info.symbol.name}"

        # Combine semantic tags from enrichment
        all_tags = enriched.semantic_tags

        # Create metadata
        metadata = {
            "file_path": symbol_info.symbol.file_path,
            "line": symbol_info.symbol.line,
            "kind": symbol_info.symbol.kind,
            "fingerprint": symbol_info.fingerprint,
            "intent": enriched.intent,
            "is_noisy": enriched.is_noisy,
        }

        if symbol_info.symbol.signature:
            metadata["signature"] = symbol_info.symbol.signature

        return GraphNode(
            id=node_id,
            type="symbol",
            tags=all_tags,
            metadata=metadata,
        )

    @staticmethod
    def create_category_nodes(enriched: EnrichedSymbol) -> List[GraphNode]:
        """Create category nodes from semantic tags.

        Pure function: EnrichedSymbol → List[GraphNode]

        Args:
            enriched: Enriched symbol information

        Returns:
            List of category nodes
        """
        category_nodes = []

        # Create category nodes for all semantic tags assigned during enrichment
        for tag in enriched.semantic_tags:
            node = GraphNode(
                id=f"cat::{tag}",
                type="category",
                tags=(tag,),
                metadata={"category_type": "semantic"},
            )
            category_nodes.append(node)

        return category_nodes

    def create_category_edges(
        self, symbol_node: GraphNode, category_nodes: List[GraphNode]
    ) -> List[GraphEdge]:
        """Create edges from symbol to categories.

        Pure function: (GraphNode, List[GraphNode]) → List[GraphEdge]

        Args:
            symbol_node: Symbol node
            category_nodes: Category nodes

        Returns:
            List of edges
        """
        edges = []

        for cat_node in category_nodes:
            # symbol -> category
            edge = GraphEdge(
                src=symbol_node.id,
                dst=cat_node.id,
                weight=self.edge_config.CATEGORY_FORWARD,
                kind="category",
                metadata={
                    "category_type": cat_node.metadata.get("category_type"),
                    "layer": "semantic"
                },
            )
            edges.append(edge)

            # category -> symbol
            # This is the "enrichment" that turns category-hopping into semantic similarity
            # This ensures structural edges (calls, imports, inherit) rank correctly against category hops.
            reverse_edge = GraphEdge(
                src=cat_node.id,
                dst=symbol_node.id,
                weight=self.edge_config.CATEGORY_REVERSE,
                kind="semantic_similarity",
                metadata={
                    "category_type": cat_node.metadata.get("category_type"),
                    "layer": "semantic"
                },
            )
            edges.append(reverse_edge)

        return edges

    def create_call_edges(
        self, enriched: EnrichedSymbol, symbol_node: GraphNode, all_symbols: List[EnrichedSymbol] = None
    ) -> List[GraphEdge]:
        """Create edges for function calls with same-file priority matching.

        Resolves bare method names (e.g., "_extract_atoms") to full symbol IDs
        using a two-strategy approach:
        1. Strategy 1: Prioritize same-file symbols (internal method calls)
        2. Strategy 2: Fall back to global search if not found in same file

        This fixes the Edge Vacuum issue where internal method calls were not
        creating edges because bare names couldn't be matched to qualified symbols.

        Args:
            enriched: Enriched symbol information
            symbol_node: Source symbol node
            all_symbols: Optional list of all symbols for same-file matching

        Returns:
            List of call edges
        """
        edges = []
        source_file = enriched.base.symbol.file_path

        for called_name in enriched.filtered_refs.calls:
            # Strategy 1: Try same-file match first (prioritize internal calls)
            target_id = None
            if all_symbols:
                for candidate in all_symbols:
                    if (candidate.base.symbol.name == called_name and
                        candidate.base.symbol.file_path == source_file):
                        target_id = f"sym::{candidate.base.symbol.name}"
                        break

            # Strategy 2: Fall back to bare name (global match)
            if not target_id:
                target_id = f"sym::{called_name}"

            edge = GraphEdge(
                src=symbol_node.id,
                dst=target_id,
                weight=self.edge_config.CALL,
                kind="calls",
                metadata={"call_type": "direct", "layer": "structural"},
            )
            edges.append(edge)
        return edges

    def create_import_edges(
        self, enriched: EnrichedSymbol, symbol_node: GraphNode
    ) -> List[GraphEdge]:
        """Create edges for imports."""
        edges = []
        for import_name in enriched.filtered_refs.imports:
            edge = GraphEdge(
                src=symbol_node.id,
                dst=f"sym::{import_name}",
                weight=self.edge_config.IMPORT,
                kind="imports",
                metadata={"import_type": "direct", "layer": "structural"},
            )
            edges.append(edge)
        return edges

    def create_inheritance_edges(
        self, enriched: EnrichedSymbol, symbol_node: GraphNode
    ) -> List[GraphEdge]:
        """Create edges for class inheritance."""
        edges = []
        for parent_class in enriched.filtered_refs.inherits:
            edge = GraphEdge(
                src=symbol_node.id,
                dst=f"sym::{parent_class}",
                weight=self.edge_config.INHERITANCE,
                kind="inherits",
                metadata={"inheritance_type": "direct", "layer": "structural"},
            )
            edges.append(edge)
        return edges

    def create_attr_access_edges(
        self, enriched: EnrichedSymbol, symbol_node: GraphNode
    ) -> List[GraphEdge]:
        """Create edges for attribute accesses."""
        edges = []
        for attr in enriched.filtered_refs.attributes:
            edge = GraphEdge(
                src=symbol_node.id,
                dst=f"sym::{attr}",
                weight=self.edge_config.ATTR_ACCESS,
                kind="attr_access",
                metadata={"access_type": "unknown", "layer": "noisy"},
            )
            edges.append(edge)
        return edges
