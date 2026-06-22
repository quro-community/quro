"""
Pass 3: Semantic Projection

Generates Symbol Manifold State (SMS) for each symbol.
"""

import json
from pathlib import Path
from typing import Dict, List
import numpy as np
from tqdm import tqdm

from .schema import (
    SymbolManifoldState,
    ManifoldPosition,
    TopologyMetrics,
    StabilityMetrics,
    RoleInfo,
    TemporalSignature,
)
from .pass1_distill import (
    SparseAdjacencyMatrix,
    SymbolFrequencyMap,
    TauSurvivalTable,
    EdgeTypeDistribution,
)
from .pass2_topology import TopologyInferenceEngine


class SemanticProjector:
    """Pass 3: Project symbols into manifold state."""

    def __init__(
        self,
        adjacency: SparseAdjacencyMatrix,
        frequency: SymbolFrequencyMap,
        tau_survival: TauSurvivalTable,
        edge_types: EdgeTypeDistribution,
        topology: TopologyInferenceEngine,
    ):
        self.adjacency = adjacency
        self.frequency = frequency
        self.tau_survival = tau_survival
        self.edge_types = edge_types
        self.topology = topology

        # Output
        self.manifold_states: Dict[str, SymbolManifoldState] = {}

    def project(self, output_path: Path) -> None:
        """Generate SMS for all symbols and write to file."""
        print("[Phase-2 Pass-3] Projecting to manifold space...")

        all_nodes = self.adjacency.all_nodes()

        # Compute percentiles for ranking
        percentiles = self._compute_percentiles(all_nodes)

        # Generate SMS for each symbol
        for node in tqdm(all_nodes, desc="Generating SMS"):
            sms = self._generate_sms(node, percentiles)
            self.manifold_states[node] = sms

        # Write to JSONL
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            for sms in self.manifold_states.values():
                f.write(sms.model_dump_json() + '\n')

        print(f"[Phase-2 Pass-3] Wrote {len(self.manifold_states)} SMS records to {output_path}")

    def _compute_percentiles(self, nodes: List[str]) -> Dict[str, Dict[str, float]]:
        """Compute percentile rankings for all metrics."""
        metrics = {
            "centrality": [self.topology.centrality.get(n, 0.0) for n in nodes],
            "betweenness": [self.topology.betweenness.get(n, 0.0) for n in nodes],
            "clustering": [self.topology.clustering.get(n, 0.0) for n in nodes],
            "frequency": [self.frequency.get_frequency(n) for n in nodes],
            "tau_persistence": [self.tau_survival.get_symbol_persistence(n) for n in nodes],
        }

        percentiles = {}
        for node in nodes:
            percentiles[node] = {}
            for metric_name, values in metrics.items():
                node_value = {
                    "centrality": self.topology.centrality.get(node, 0.0),
                    "betweenness": self.topology.betweenness.get(node, 0.0),
                    "clustering": self.topology.clustering.get(node, 0.0),
                    "frequency": self.frequency.get_frequency(node),
                    "tau_persistence": self.tau_survival.get_symbol_persistence(node),
                }[metric_name]

                # Compute percentile
                percentile = sum(1 for v in values if v <= node_value) / len(values) if values else 0.0
                percentiles[node][metric_name] = percentile

        return percentiles

    def _generate_sms(self, symbol: str, percentiles: Dict[str, Dict[str, float]]) -> SymbolManifoldState:
        """Generate Symbol Manifold State for a symbol."""
        # Topology metrics
        topology = TopologyMetrics(
            centrality=self.topology.centrality.get(symbol, 0.0),
            betweenness=self.topology.betweenness.get(symbol, 0.0),
            clustering_coeff=self.topology.clustering.get(symbol, 0.0),
        )

        # Stability metrics
        tau_persistence = self.tau_survival.get_symbol_persistence(symbol)
        entry_variance = self._compute_entry_variance(symbol)
        structural_noise = self._compute_structural_noise(symbol)

        stability = StabilityMetrics(
            tau_persistence=tau_persistence,
            entry_variance=entry_variance,
            structural_noise=structural_noise,
        )

        # Role
        role = RoleInfo(
            type=self.topology.roles.get(symbol, "unknown"),
            confidence=self.topology.role_confidence.get(symbol, 0.0),
        )

        # Temporal signature
        freq = self.frequency.get_frequency(symbol)
        first_seen = self.frequency.first_seen.get(symbol, 0)
        burstiness = self.frequency.get_burstiness(symbol)

        temporal = TemporalSignature(
            first_seen=first_seen,
            frequency=freq,
            burstiness=burstiness,
        )

        # Category coupling (simplified: edge type distribution)
        category_coupling = self._compute_category_coupling(symbol)

        # Manifold position (simplified embedding)
        manifold_position = self._compute_manifold_position(symbol)

        return SymbolManifoldState(
            symbol=symbol,
            manifold_position=manifold_position,
            topology=topology,
            stability=stability,
            role=role,
            category_coupling=category_coupling,
            temporal_signature=temporal,
            percentiles=percentiles.get(symbol, {}),
        )

    def _compute_entry_variance(self, symbol: str) -> float:
        """Compute variance across entry points.

        Measures how consistently a symbol is reached from different entry points.
        High variance = reached via many different paths.
        """
        in_neighbors = self.adjacency.get_in_neighbors(symbol)
        if len(in_neighbors) < 2:
            return 0.0

        weights = list(in_neighbors.values())
        mean_weight = sum(weights) / len(weights)
        variance = sum((w - mean_weight) ** 2 for w in weights) / len(weights)

        # Normalize to [0,1]
        return min(1.0, variance / (mean_weight ** 2) if mean_weight > 0 else 0.0)

    def _compute_structural_noise(self, symbol: str) -> float:
        """Compute noise in edge weights.

        Measures inconsistency in edge weights (high noise = unstable structure).
        """
        neighbors = self.adjacency.get_neighbors(symbol)
        if len(neighbors) < 2:
            return 0.0

        weights = list(neighbors.values())
        mean_weight = sum(weights) / len(weights)
        std_dev = (sum((w - mean_weight) ** 2 for w in weights) / len(weights)) ** 0.5

        # Coefficient of variation (normalized)
        return min(1.0, std_dev / mean_weight if mean_weight > 0 else 0.0)

    def _compute_category_coupling(self, symbol: str) -> Dict[str, float]:
        """Compute category coupling strengths.

        Simplified: edge type distribution as proxy for category coupling.
        """
        edge_dist = self.edge_types.get_distribution(symbol)
        total = sum(edge_dist.values())

        if total == 0:
            return {}

        # Normalize to [0,1]
        return {edge_type: count / total for edge_type, count in edge_dist.items()}

    def _compute_manifold_position(self, symbol: str) -> ManifoldPosition:
        """Compute manifold position (simplified embedding).

        Uses topology metrics as embedding dimensions.
        """
        embedding = [
            self.topology.centrality.get(symbol, 0.0),
            self.topology.betweenness.get(symbol, 0.0),
            self.topology.clustering.get(symbol, 0.0),
            self.tau_survival.get_symbol_persistence(symbol),
            float(self.frequency.get_frequency(symbol)) / 100.0,  # Normalize frequency
        ]

        norm = (sum(x ** 2 for x in embedding)) ** 0.5

        return ManifoldPosition(
            embedding=embedding,
            norm=norm,
        )

    def get_statistics(self) -> Dict:
        """Get projection statistics."""
        return {
            "total_symbols": len(self.manifold_states),
            "avg_centrality_percentile": sum(
                sms.percentiles.get("centrality", 0.0) for sms in self.manifold_states.values()
            ) / len(self.manifold_states) if self.manifold_states else 0,
        }
