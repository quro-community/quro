"""Graph Detox Scanner

@module quro.pipeline.cqe.detox
@intent Offline scanner for graph quality issues (god nodes, aliases, weight decay)
"""

from typing import List, Optional
import statistics
from adapters.graph import GraphAdapter
from .types import DetoxReport, FixPlanAction, GraphEntropyMetrics, GraphManifest


class GraphDetoxScanner:
    """Graph Detox Scanner - Data Quality Guard.

    An offline scanner that analyzes the static graph and symbol table
    to detect structural pollution, alias conflicts, and weight inflation.

    CRITICAL: This module NEVER mutates the graph at runtime. It only
    outputs diagnostics to feedback into the offline Indexer.

    Pure function interface:
        scan(atoms, morphisms) -> DetoxReport
    """

    def __init__(
        self,
        graph: GraphAdapter,
        symbols: List[str],
        manifest: Optional[GraphManifest] = None,
    ):
        """Initialize detox scanner.

        Args:
            graph: Graph adapter for traversal
            symbols: List of all symbol IDs in graph
            manifest: Optional graph version metadata
        """
        self.graph = graph
        self.symbols = symbols
        self.manifest = manifest

    def scan(
        self,
        god_node_threshold: int = 50,
        max_edit_distance: int = 1,
    ) -> DetoxReport:
        """Run full suite of detox scans and generate fix plan.

        Args:
            god_node_threshold: Max out-degree before flagging as god node
            max_edit_distance: Max Levenshtein distance for alias detection

        Returns:
            DetoxReport with diagnostics and fix plan

        Pipeline:
            1. Validate manifest (version check)
            2. Compute entropy metrics (density, hub ratio, weight variance)
            3. Scan for god nodes (excessive out-degree)
            4. Scan for alias conflicts (similar symbol names)
            5. Validate weight decay (weights <= 1.0)
            6. Generate fix plan (actionable fixes)
        """
        report = DetoxReport(manifest=self.manifest)

        # 0. Validate Manifest
        self._validate_manifest(report)

        # 1. Compute Entropy Metrics
        self._compute_entropy(report, god_node_threshold)

        # 2. Scan for God Nodes
        self._scan_god_nodes(report, god_node_threshold)

        # 3. Scan for Alias Conflicts
        self._scan_alias_conflicts(report, max_edit_distance)

        # 4. Scan for Weight Decay Issues
        self._validate_weight_decay(report)

        # 5. Generate Fix Plan
        self._generate_fix_plan(report)

        return report

    def _compute_entropy(self, report: DetoxReport, hub_threshold: int) -> None:
        """Compute Graph Entropy Metrics (Density, Hub Ratio, Weight Variance)."""
        total_nodes = len(self.symbols)
        if total_nodes == 0:
            return

        total_edges = 0
        hub_count = 0
        all_weights = []

        for sym in self.symbols:
            try:
                neighbors = list(self.graph.neighbors(sym))
                out_degree = len(neighbors)
                total_edges += out_degree

                if out_degree > hub_threshold:
                    hub_count += 1

                for _, weight in neighbors:
                    all_weights.append(weight)
            except Exception:
                pass

        avg_out_degree = total_edges / total_nodes
        hub_ratio = hub_count / total_nodes
        weight_variance = statistics.variance(all_weights) if len(all_weights) > 1 else 0.0

        # H ≈ α * avg_out_degree + β * hub_ratio + γ * weight_variance
        # Simple structural approximation
        entropy_score = (0.1 * avg_out_degree) + (100 * hub_ratio) + (10 * weight_variance)

        report.entropy = GraphEntropyMetrics(
            avg_out_degree=avg_out_degree,
            hub_ratio=hub_ratio,
            weight_variance=weight_variance,
            entropy_score=entropy_score,
        )

    def _validate_manifest(self, report: DetoxReport) -> None:
        """Validate that graph state matches provided manifest."""
        if not self.manifest:
            report.manifest_errors.append({
                "issue": "missing_manifest",
                "severity": "critical",
                "message": "No GraphManifest provided. Version tracking is disabled.",
            })
            return

        actual_symbol_count = len(self.symbols)
        if actual_symbol_count != self.manifest.symbol_count:
            report.manifest_errors.append({
                "issue": "symbol_count_mismatch",
                "severity": "critical",
                "expected": self.manifest.symbol_count,
                "actual": actual_symbol_count,
                "message": f"Graph index is out of sync with manifest (branch: {self.manifest.branch}, commit: {self.manifest.commit_hash})",
            })

    def _scan_god_nodes(self, report: DetoxReport, threshold: int) -> None:
        """Detect nodes with excessively high out-degree.

        These act as 'wormholes' and destroy semantic isolation.
        """
        for sym in self.symbols:
            try:
                neighbors = list(self.graph.neighbors(sym))
                out_degree = len(neighbors)
                if out_degree > threshold:
                    report.god_nodes.append({
                        "node": sym,
                        "issue": "god_node",
                        "out_degree": out_degree,
                        "severity": "critical" if out_degree > threshold * 2 else "high",
                    })
            except Exception:
                pass  # Node might not exist in graph yet

    def _scan_alias_conflicts(self, report: DetoxReport, max_dist: int) -> None:
        """Detect symbols that are too similar to each other.

        This causes the CanonicalLayer to frequently return 'ambiguous'.
        """
        # O(N^2) behavior mitigated by sorting by length and early-breakout
        symbols_list = sorted(list(self.symbols), key=lambda x: (len(x), x))
        n = len(symbols_list)
        for i in range(n):
            node_a = symbols_list[i]
            len_a = len(node_a)
            for j in range(i + 1, n):
                node_b = symbols_list[j]
                if len(node_b) - len_a > max_dist:
                    break
                if self._edit_distance_leq(node_a, node_b, max_dist):
                    report.alias_conflicts.append({
                        "node_a": node_a,
                        "node_b": node_b,
                        "issue": "alias_conflict",
                        "distance": max_dist,
                    })

    def _validate_weight_decay(self, report: DetoxReport) -> None:
        """Validate that edge weights are strictly <= 1.0.

        A more advanced version would simulate random walks to ensure
        paths decay below tau within a reasonable depth.
        """
        for sym in self.symbols:
            try:
                for neighbor, weight in self.graph.neighbors(sym):
                    if weight > 1.0:
                        report.decay_warnings.append({
                            "node": sym,
                            "neighbor": neighbor,
                            "issue": "weight_inflation",
                            "weight": weight,
                            "severity": "critical",
                        })
            except Exception:
                pass

    def _generate_fix_plan(self, report: DetoxReport) -> None:
        """Translate detected issues into actionable FixPlanActions for Indexer."""
        # Fix God Nodes -> Downweight
        for god_node in report.god_nodes:
            report.fix_plan.append(FixPlanAction(
                action_type="downweight_edges",
                target=god_node["node"],
                details={
                    "factor": 0.3,
                    "reason": f"Out degree {god_node['out_degree']} exceeds threshold",
                },
            ))

        # Fix Alias Conflicts -> Merge
        for conflict in report.alias_conflicts:
            node_a = conflict["node_a"]
            node_b = conflict["node_b"]
            # Deterministic choice: shorter name is canonical, or alphabetically first
            if len(node_a) < len(node_b) or (len(node_a) == len(node_b) and node_a < node_b):
                canonical, alias = node_a, node_b
            else:
                canonical, alias = node_b, node_a

            report.fix_plan.append(FixPlanAction(
                action_type="merge_alias",
                target=canonical,
                details={
                    "aliases": [alias],
                    "reason": f"Edit distance {conflict['distance']} conflict",
                },
            ))

        # Fix Weight Inflation -> Adjust
        for warning in report.decay_warnings:
            report.fix_plan.append(FixPlanAction(
                action_type="adjust_weight",
                target=warning["node"],
                details={
                    "neighbor": warning["neighbor"],
                    "new_weight": 1.0,
                    "reason": "Weight > 1.0 violates monotonicity",
                },
            ))

    def _edit_distance_leq(self, a: str, b: str, k: int) -> bool:
        """Check if Levenshtein distance between a and b is <= k.

        Optimized early-exit version from CanonicalLayer.
        """
        if abs(len(a) - len(b)) > k:
            return False
        prev = list(range(len(b) + 1))
        for i in range(1, len(a) + 1):
            curr = [i] + [0] * len(b)
            min_row = curr[0]
            for j in range(1, len(b) + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
                min_row = min(min_row, curr[j])
            if min_row > k:
                return False
            prev = curr
        return prev[-1] <= k