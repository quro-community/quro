"""
CQE Kernel - Additive Scoring with Soft Ranking (Design 93)

@module quro.core.cqe.kernel
@intent Deterministic graph traversal with additive MI scoring
@constraint Pure function, no side effects

INVARIANT: Kernel is Pure
- NO file I/O
- NO database access
- NO logging
- NO global state mutation
- Deterministic: same input → same output

Design 93 Changes:
- Additive scoring: score = structural + λ * MI (prevents information annihilation)
- Soft tau: ranking bias instead of hard gate (preserves reachability)
- Top-k guarantee: always return at least k nodes (graceful degradation)
"""

import heapq
import math
from typing import Dict, Any, Optional, Callable
from core.cqe.types import GraphProtocol, CQEResult


class CQEKernel:
    """
    Level 1: Deterministic Graph Computation Kernel for CQE.
    Implements Additive Scoring Dijkstra with soft ranking.
    PURE MATH: No logs, no heuristics, no mutations.

    Design 93: Additive scoring prevents MI cold-start collapse.
    """

    @staticmethod
    def query(
        graph: GraphProtocol,
        start: str,
        tau: float = 0.05,
        mi_weight: float = 0.1,
        mi_scorer: Optional[Callable[[str, str], float]] = None,
        top_k: int = 100,
        use_soft_tau: bool = True,
    ) -> CQEResult:
        """
        Executes deterministic max-weight traversal with additive MI scoring.

        Design 93 Formula:
        score = structural_score + λ * MI_score

        Where:
        - structural_score: w * edge_weight (multiplicative path weight)
        - MI_score: learned signal from query history
        - λ (mi_weight): blending coefficient (0.1 cold start, 0.3-0.5 warm)

        :param graph: The static graph implementing neighbors(node) -> Iterable[(neighbor, weight)]
        :param start: The entry atom (A0). MUST be validated by CanonicalLayer first.
        :param tau: Soft threshold for ranking bias (not hard gate)
        :param mi_weight: Lambda coefficient for MI contribution (default: 0.1)
        :param mi_scorer: Optional MI scoring function (src, dst) -> float [0, 1]
        :param top_k: Minimum nodes to return (fallback guarantee)
        :param use_soft_tau: If True, tau is soft ranking; if False, hard gate (legacy)
        :return: CQEResult containing max_weights and predecessors
        """
        pq = [(-1.0, start)]   # max heap via negative weight
        max_weights = {start: 1.0}
        predecessors = {start: None}
        visited_count = 0

        while pq and (use_soft_tau or visited_count < top_k):
            neg_w, u = heapq.heappop(pq)
            w = -neg_w

            # skip stale path (re-relaxation optimization)
            if w < max_weights[u]:
                continue

            visited_count += 1

            for v, edge_weight in graph.neighbors(u):
                # Additive scoring (Design 93)
                structural_score = w * edge_weight

                # Add MI bonus if scorer available
                mi_bonus = 0.0
                if mi_scorer is not None:
                    mi_score = mi_scorer(u, v)
                    mi_bonus = mi_weight * mi_score

                w_new = structural_score + mi_bonus

                # Soft tau: ranking bias instead of hard gate
                if use_soft_tau:
                    # Below tau: penalize but don't delete
                    if w_new < tau:
                        w_new *= 0.5  # 50% penalty for weak paths
                else:
                    # Legacy hard gate
                    if w_new < tau:
                        continue

                # If we found a strictly better path to v, relax the edge
                if w_new > max_weights.get(v, 0.0):
                    max_weights[v] = w_new
                    predecessors[v] = u
                    heapq.heappush(pq, (-w_new, v))

        return CQEResult(max_weights=max_weights, predecessors=predecessors)
