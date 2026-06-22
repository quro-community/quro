"""
Pass 5: Inter-Center Graph Construction (Design 99)

@module quro.tda.phase3_5.pass5_inter_center_graph
@intent Build inter-center edges from crossing edges between semantic centers,
        and compute reachability maps for navigation.

This pass adds `connected_centers` and `connections` to each SemanticCenter,
enabling LLM to understand the global topology and plan navigation across centers.

Algorithm:
  1. For each edge (src → dst): if src in center A and dst in center B, A→B is an inter-center edge
  2. Strength = count of crossing edges / total edges from source center
  3. Direction: outbound if A→B dominant, bidirectional if mutual
  4. Add connected_centers and connections to each SemanticCenter

Performance Note:
  This phase uses GraphAdapter which prioritizes adjacency_cache.pkl (fast)
  over graph_events.jsonl (slow 20GB fallback). Run Phase 2 to generate the cache.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set

from ..adapters import GraphAdapter
from . import (
    SemanticCenter,
    InterCenterEdge,
)
from .pass4_center_detection import CenterDetector

logger = logging.getLogger(__name__)


class InterCenterGraphBuilder:
    """Build inter-center graph from center assignments and graph adjacency."""

    def __init__(self, workspace_root: Optional[Path] = None):
        """Initialize inter-center graph builder.

        Args:
            workspace_root: Workspace root for loading Phase-1 events
        """
        self.workspace_root = workspace_root or Path.cwd()
        self._adjacency: Dict[str, List[str]] = defaultdict(list)
        self._in_neighbors: Dict[str, List[str]] = defaultdict(list)

    def build(
        self,
        centers: List[SemanticCenter],
        basin_map: Dict[str, int],
        field_data_path: Optional[Path] = None,
    ) -> List[SemanticCenter]:
        """Build inter-center edges and enhance centers.

        Args:
            centers: List of SemanticCenter (from Pass 4)
            basin_map: Symbol → center_id mapping
            field_data_path: Path to .quro_context/tda/ for loading adjacency

        Returns:
            Enhanced list of SemanticCenter with connections populated
        """
        field_data_path = field_data_path or self.workspace_root / ".quro_context" / "tda"

        # Load adjacency if not already loaded
        self._load_adjacency(field_data_path)

        if not self._adjacency:
            logger.warning("No adjacency loaded, inter-center graph will be empty")
            return centers

        # Build symbol → center lookup (basin_map already has "C{id}" string values)
        symbol_to_center = {k: v for k, v in basin_map.items()}
        center_by_id = {c.id: c for c in centers}

        # Count crossing edges between center pairs
        crossing_edges: Dict[tuple, int] = defaultdict(int)
        outbound_counts: Dict[str, int] = defaultdict(int)

        for src_symbol, dst_list in self._adjacency.items():
            src_center = symbol_to_center.get(src_symbol)
            if src_center is None:
                continue

            outbound_counts[src_center] += len(dst_list)

            for dst_symbol in dst_list:
                dst_center = symbol_to_center.get(dst_symbol)
                if dst_center is None:
                    continue

                if src_center != dst_center:
                    key = (src_center, dst_center)
                    crossing_edges[key] += 1

        # Build InterCenterEdge objects
        inter_edges: List[InterCenterEdge] = []
        for (from_center, to_center), count in crossing_edges.items():
            total_outbound = outbound_counts.get(from_center, 1)
            strength = count / total_outbound if total_outbound > 0 else 0.0

            # Determine direction
            reverse_count = crossing_edges.get((to_center, from_center), 0)
            if reverse_count > 0:
                # Bidirectional: both directions have edges
                direction = "bidirectional"
            else:
                direction = "outbound"

            inter_edges.append(InterCenterEdge(
                from_center=str(from_center),
                to_center=str(to_center),
                strength=round(strength, 3),
                direction=direction,
            ))

        logger.info("Built %d inter-center edges", len(inter_edges))

        # Add connections to each center
        for center in centers:
            connected = set()
            connections = []

            for edge in inter_edges:
                if edge.from_center == center.id:
                    connected.add(edge.to_center)
                    connections.append(edge)
                elif edge.to_center == center.id and edge.direction == "bidirectional":
                    connected.add(edge.from_center)
                    # Don't add reverse edge, already covered by from_center direction

            # Sort connections by strength descending
            connections.sort(key=lambda e: e.strength, reverse=True)

            # Update center topology
            center.topology.connected_centers = list(connected)
            center.topology.connections = connections

            logger.debug("Center %s: %d connected centers, %d connections",
                        center.id, len(connected), len(connections))

        return centers

    def _load_adjacency(self, field_data_path: Path) -> None:
        """Load graph adjacency using GraphAdapter.

        Uses adjacency_cache.pkl (fast) instead of graph_events.jsonl (slow).
        See pass4_center_detection.py for details.
        """
        import time

        start_time = time.time()
        logger.info("Loading graph adjacency for inter-center graph...")

        # Create graph using adapter (auto-selects best source)
        graph = GraphAdapter.create(field_data_path)

        # Populate adjacency dicts from graph interface
        for node in graph.get_all_nodes():
            self._adjacency[node] = graph.get_out_neighbors(node)
            self._in_neighbors[node] = graph.get_in_neighbors(node)

        elapsed = time.time() - start_time
        logger.info(
            "Loaded adjacency in %.2fs: %d nodes, %d edges",
            elapsed, len(self._adjacency), sum(len(v) for v in self._adjacency.values())
        )

    def compute_reachability(
        self,
        center: SemanticCenter,
        basin_map: Dict[str, int],
        max_symbols: int = 50,
    ) -> List[str]:
        """Compute reachable symbols from a center (limited BFS).

        Args:
            center: SemanticCenter to compute reachability for
            basin_map: Symbol → center_id mapping
            max_symbols: Maximum symbols to return

        Returns:
            List of reachable symbol IDs (excluding symbols within the center)
        """
        # Get symbols in this center
        center_symbols = {s for s, cid in basin_map.items() if cid == center.id}

        # BFS from entry points
        visited: Set[str] = set(center_symbols)
        reachable: List[str] = []

        for entry in center.topology.entry_points[:3]:  # Top 3 entry points
            queue = [entry.symbol]

            while queue and len(reachable) < max_symbols:
                current = queue.pop(0)

                for neighbor in self._adjacency.get(current, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        neighbor_center = basin_map.get(neighbor)
                        if neighbor_center != center.id:  # External to this center
                            reachable.append(neighbor)
                        queue.append(neighbor)

        return reachable[:max_symbols]

    def get_statistics(self) -> Dict:
        """Get graph statistics."""
        return {
            "total_nodes": len(self._adjacency),
            "total_edges": sum(len(v) for v in self._adjacency.values()),
        }
