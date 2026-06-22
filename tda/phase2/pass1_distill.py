"""
Pass 1: Atomic Feature Distillation

Scans Phase-1 event stream and builds in-memory statistical structures.
"""

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Set
from collections import defaultdict
from tqdm import tqdm


class SparseAdjacencyMatrix:
    """Sparse adjacency matrix: src → dst → weight_sum.

    Maintains both forward (matrix) and reverse (in_matrix) indices
    for O(1) in-neighbor lookup.
    """

    def __init__(self):
        self.matrix: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.in_matrix: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def add_edge(self, src: str, dst: str, weight: float):
        """Add edge weight to matrix (maintains both forward and reverse indices)."""
        self.matrix[src][dst] += weight
        self.in_matrix[dst][src] += weight  # Reverse index

    def get_weight(self, src: str, dst: str) -> float:
        """Get edge weight (0 if not exists)."""
        return self.matrix.get(src, {}).get(dst, 0.0)

    def get_neighbors(self, node: str) -> Dict[str, float]:
        """Get all neighbors and weights for a node."""
        return dict(self.matrix.get(node, {}))

    def get_in_neighbors(self, node: str) -> Dict[str, float]:
        """Get all nodes that point to this node (O(1) lookup via reverse index)."""
        return dict(self.in_matrix.get(node, {}))

    def get_out_degree(self, node: str) -> int:
        """Get out-degree (number of outgoing edges)."""
        return len(self.matrix.get(node, {}))

    def get_weighted_out_degree(self, node: str) -> float:
        """Get weighted out-degree (sum of outgoing weights)."""
        return sum(self.matrix.get(node, {}).values())

    def all_nodes(self) -> Set[str]:
        """Get all nodes in graph (union of forward and reverse indices)."""
        nodes = set(self.matrix.keys())
        nodes.update(self.in_matrix.keys())
        return nodes


class SymbolFrequencyMap:
    """Symbol visit frequency tracker."""

    def __init__(self):
        self.frequency: Dict[str, int] = defaultdict(int)
        self.first_seen: Dict[str, int] = {}
        self.last_seen: Dict[str, int] = {}

    def record_visit(self, symbol: str, timestamp: int):
        """Record a symbol visit."""
        self.frequency[symbol] += 1
        if symbol not in self.first_seen:
            self.first_seen[symbol] = timestamp
        self.last_seen[symbol] = timestamp

    def get_frequency(self, symbol: str) -> int:
        """Get visit frequency."""
        return self.frequency.get(symbol, 0)

    def get_burstiness(self, symbol: str) -> float:
        """Compute burstiness coefficient [0,1]."""
        freq = self.frequency.get(symbol, 0)
        if freq <= 1:
            return 0.0

        first = self.first_seen.get(symbol, 0)
        last = self.last_seen.get(symbol, 0)
        duration = last - first

        if duration == 0:
            return 1.0  # All visits in same instant = max burstiness

        # Burstiness = variance / mean of inter-arrival times
        # Simplified: high freq in short duration = high burstiness
        avg_interval = duration / freq
        # Normalize to [0,1]: shorter intervals = higher burstiness
        return min(1.0, 1.0 / (1.0 + avg_interval / 1e6))  # 1e6 = 1 second in microseconds


class TauSurvivalTable:
    """Tracks edge survival across tau thresholds."""

    def __init__(self):
        # (src, dst) → list of (tau, passed_gate) tuples
        self.survival: Dict[Tuple[str, str], List[Tuple[float, bool]]] = defaultdict(list)

    def record_traversal(self, src: str, dst: str, tau: float, passed_gate: bool):
        """Record edge traversal attempt."""
        self.survival[(src, dst)].append((tau, passed_gate))

    def get_persistence(self, src: str, dst: str) -> float:
        """Get tau persistence rate [0,1]."""
        records = self.survival.get((src, dst), [])
        if not records:
            return 0.0

        passed = sum(1 for _, passed in records if passed)
        return passed / len(records)

    def get_symbol_persistence(self, symbol: str) -> float:
        """Get average persistence for all edges from symbol."""
        edges = [edge for edge in self.survival.keys() if edge[0] == symbol]
        if not edges:
            return 0.0

        total_persistence = sum(self.get_persistence(src, dst) for src, dst in edges)
        return total_persistence / len(edges)


class EdgeTypeDistribution:
    """Tracks edge type distribution per symbol."""

    def __init__(self):
        # symbol → edge_type → count
        self.distribution: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    def record_edge(self, symbol: str, edge_type: str):
        """Record edge type for symbol."""
        self.distribution[symbol][edge_type] += 1

    def get_distribution(self, symbol: str) -> Dict[str, int]:
        """Get edge type distribution for symbol."""
        return dict(self.distribution.get(symbol, {}))

    def get_dominant_type(self, symbol: str) -> str:
        """Get most common edge type for symbol."""
        dist = self.distribution.get(symbol, {})
        if not dist:
            return "unknown"
        return max(dist.items(), key=lambda x: x[1])[0]


class AtomicFeatureDistiller:
    """Pass 1: Distill atomic features from event stream."""

    def __init__(self, events_path: Path):
        self.events_path = events_path
        self.adjacency = SparseAdjacencyMatrix()
        self.frequency = SymbolFrequencyMap()
        self.tau_survival = TauSurvivalTable()
        self.edge_types = EdgeTypeDistribution()

        # Query metadata cache
        self.query_metadata: Dict[str, Dict] = {}

    def distill(self) -> None:
        """Scan event stream and build statistical structures."""
        print("[Phase-2 Pass-1] Scanning event stream...")

        # Count total lines for progress bar
        with open(self.events_path) as f:
            total_lines = sum(1 for _ in f)

        with open(self.events_path) as f:
            for line in tqdm(f, total=total_lines, desc="Distilling features"):
                event = json.loads(line)
                self._process_event(event)

        print(f"[Phase-2 Pass-1] Distilled {len(self.adjacency.all_nodes())} nodes")

    def _process_event(self, event: Dict) -> None:
        """Process a single event."""
        record_type = event.get("record_type")
        event_type = event.get("event_type")

        if record_type == "QUERY_METADATA":
            # Cache query metadata
            query_id = event["query_id"]
            self.query_metadata[query_id] = event

        elif event_type == "NODE_VISIT":
            # Record node visit
            node_id = event["node"]["id"]
            timestamp = event["timestamp"]
            self.frequency.record_visit(node_id, timestamp)

        elif event_type == "EDGE_TRAVERSE":
            # Record edge traversal
            edge = event["edge"]
            src = edge["src"]
            dst = edge["dst"]
            weight = edge["weight"]
            edge_type = edge["edge_type"]

            # Add to adjacency matrix
            self.adjacency.add_edge(src, dst, weight)

            # Record edge type
            self.edge_types.record_edge(src, edge_type)

            # Record tau survival
            query_id = event["query_id"]
            query_meta = self.query_metadata.get(query_id, {})
            tau = query_meta.get("query_params", {}).get("tau", 0.1)
            passed_gate = event["traverse_context"]["passed_gate"]
            self.tau_survival.record_traversal(src, dst, tau, passed_gate)

    def distill_from_events(self, events: Iterable[Dict]) -> None:
        """Scan event stream from an iterable and build statistical structures.

        Args:
            events: Iterable of event dicts (from DuckDB, JSONL, or memory).
        """
        print("[Phase-2 Pass-1] Scanning event stream from iterable...")
        for event in events:
            self._process_event(event)

        print(f"[Phase-2 Pass-1] Distilled {len(self.adjacency.all_nodes())} nodes")

    def get_statistics(self) -> Dict:
        """Get distillation statistics."""
        all_nodes = self.adjacency.all_nodes()
        return {
            "total_nodes": len(all_nodes),
            "total_edges": sum(len(dsts) for dsts in self.adjacency.matrix.values()),
            "avg_out_degree": sum(self.adjacency.get_out_degree(n) for n in all_nodes) / len(all_nodes) if all_nodes else 0,
            "max_out_degree": max((self.adjacency.get_out_degree(n) for n in all_nodes), default=0),
        }
