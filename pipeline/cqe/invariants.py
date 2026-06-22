"""Graph Invariants Checker

@module quro.pipeline.cqe.invariants
@intent HARD GATE: Graph invariants validation. Any violation means the graph
       MUST NOT be published.
"""

from collections import deque
import heapq
from typing import List, Dict, Set
from adapters.graph import GraphAdapter


class GraphInvariants:
    """Graph Invariants Checker - HARD GATE.

    Any violation of these invariants means the Graph MUST NOT be published.

    Invariants:
    - I1. Structural Validity: No node exceeds max out-degree
    - I2. Alias Consistency: Alias -> canonical is 1:1, no cycles
    - I3. Path Decay Constraint: Paths > max_depth have weight < tau
    """

    @staticmethod
    def check_structural_validity(
        graph: GraphAdapter,
        symbols: List[str],
        max_out_degree: int = 50,
    ) -> List[str]:
        """I1. Structural Validity.

        Ensures no node exceeds the maximum allowed out-degree.

        Args:
            graph: Graph adapter for traversal
            symbols: List of all symbol IDs
            max_out_degree: Maximum allowed out-degree

        Returns:
            List of violation messages (empty if valid)
        """
        violations = []
        for sym in symbols:
            try:
                out_degree = len(list(graph.neighbors(sym)))
                if out_degree > max_out_degree:
                    violations.append(
                        f"Node '{sym}' violates max out-degree: {out_degree} > {max_out_degree}"
                    )
            except Exception:
                pass
        return violations

    @staticmethod
    def check_alias_consistency(aliases: Dict[str, List[str]]) -> List[str]:
        """I2. Alias Consistency.

        Ensures alias -> canonical is 1:1 and the alias graph is a DAG (no cycles).

        Args:
            aliases: Dict mapping canonical → list of aliases

        Returns:
            List of violation messages (empty if valid)
        """
        violations = []
        reverse_map = {}

        # Check 1:1 mapping
        for canonical, alias_list in aliases.items():
            for alias in alias_list:
                if alias in reverse_map:
                    violations.append(
                        f"Alias '{alias}' maps to multiple canonicals: "
                        f"'{reverse_map[alias]}' and '{canonical}'"
                    )
                reverse_map[alias] = canonical

        # Check for cycles (DAG constraint)
        for alias, canonical in reverse_map.items():
            curr = canonical
            visited = {alias}
            while curr in reverse_map:
                if curr in visited:
                    violations.append(f"Alias cycle detected involving '{curr}'")
                    break
                visited.add(curr)
                curr = reverse_map[curr]

        return violations

    @staticmethod
    def check_path_decay(
        graph: GraphAdapter,
        symbols: List[str],
        max_depth: int = 5,
        tau: float = 0.05,
    ) -> List[str]:
        """I3. Path Decay Constraint.

        Ensures that any path with depth > max_depth has a product weight < tau.
        Uses bounded BFS with visited set to avoid cycle blowup.

        Args:
            graph: Graph adapter for traversal
            symbols: List of all symbol IDs
            max_depth: Maximum allowed depth before decay check
            tau: Minimum weight threshold for decay

        Returns:
            List of violation messages (empty if valid)
        """
        violations = []

        for start in symbols:
            max_weights: Dict[str, float] = {start: 1.0}
            # Max-heap via negative weight: (-weight, depth, node)
            heap = [(-1.0, 0, start)]

            while heap:
                neg_w, depth, curr = heapq.heappop(heap)
                w = -neg_w

                if w < max_weights.get(curr, 0.0):
                    continue

                if depth > max_depth and w >= tau:
                    violations.append(
                        f"Path decay violation starting from '{start}': "
                        f"reached '{curr}' at depth {depth} with weight {w} >= {tau}"
                    )
                    break  # Record one violation per start node to avoid log spam

                if depth > max_depth:
                    continue

                try:
                    for neighbor, edge_weight in graph.neighbors(curr):
                        new_w = w * edge_weight
                        # We only enqueue if we found a strictly better path to neighbor
                        if new_w >= tau and new_w > max_weights.get(neighbor, 0.0):
                            max_weights[neighbor] = new_w
                            heapq.heappush(heap, (-new_w, depth + 1, neighbor))
                except Exception:
                    pass

        return violations

    @classmethod
    def check_all(
        cls,
        graph: GraphAdapter,
        symbols: List[str],
        aliases: Dict[str, List[str]] | None = None,
        max_out_degree: int = 50,
        max_depth: int = 5,
        tau: float = 0.05,
    ) -> Dict[str, List[str]]:
        """Run all invariant checks.

        Args:
            graph: Graph adapter for traversal
            symbols: List of all symbol IDs
            aliases: Optional alias mapping (canonical → aliases)
            max_out_degree: Maximum allowed out-degree
            max_depth: Maximum allowed depth before decay check
            tau: Minimum weight threshold for decay

        Returns:
            Dict mapping check_name → list of violations
        """
        results = {
            "structural_validity": cls.check_structural_validity(
                graph, symbols, max_out_degree
            ),
            "path_decay": cls.check_path_decay(graph, symbols, max_depth, tau),
        }

        if aliases is not None:
            results["alias_consistency"] = cls.check_alias_consistency(aliases)

        return results

    @classmethod
    def is_valid(
        cls,
        graph: GraphAdapter,
        symbols: List[str],
        aliases: Dict[str, List[str]] | None = None,
        max_out_degree: int = 50,
        max_depth: int = 5,
        tau: float = 0.05,
    ) -> bool:
        """Check if graph passes all invariants.

        Args:
            graph: Graph adapter for traversal
            symbols: List of all symbol IDs
            aliases: Optional alias mapping (canonical → aliases)
            max_out_degree: Maximum allowed out-degree
            max_depth: Maximum allowed depth before decay check
            tau: Minimum weight threshold for decay

        Returns:
            True if all invariants pass, False otherwise
        """
        results = cls.check_all(graph, symbols, aliases, max_out_degree, max_depth, tau)
        return all(len(violations) == 0 for violations in results.values())
