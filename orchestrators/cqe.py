"""CQE Orchestrator

@module quro.orchestrators.cqe
@intent Bridge Graph Adapter + CQE Kernel + Policy for end-to-end queries
"""

from pathlib import Path
from typing import Tuple, Optional
from core.cqe import CQEKernel, CQEResult
from core.cqe.policy import CQEPolicy
from core.cqe.transforms import HubNormalizer, TopKPruner
from core.cqe.types import GraphProtocol
from io.adapters.sqlite import SQLiteGraphAdapter
from io.adapters.sqlite_tda import SQLiteTDAGraphAdapter


class CQEOrchestrator:
    """CQE orchestrator (bridges adapter, kernel, policy).

    Coordinates:
    - Graph Adapter (I/O layer - loads graph from SQLite)
    - CQE Kernel (pure computation - Max-Product Dijkstra)
    - CQE Policy (configuration - pruning thresholds)

    Invariant: Orchestration only, no business logic.

    TDA Mode:
    - When use_tda=True, uses SQLiteTDAGraphAdapter with friction-enriched weights
    - Edge weights: original_mi_weight / friction (lower friction → higher weight)
    - Enables curvature-aware traversal (prefers low-friction paths)
    """

    def __init__(
        self,
        graph_adapter: GraphProtocol,
        policy: CQEPolicy | None = None,
        use_tda: bool = False,
    ):
        """Initialize CQE orchestrator.

        Args:
            graph_adapter: Graph data adapter
            policy: CQE policy (defaults to CQEPolicy.default())
            use_tda: Whether TDA mode is enabled (for metadata tracking)
        """
        self.adapter = graph_adapter
        self.policy = policy or CQEPolicy.default()
        self.kernel = CQEKernel()
        self.use_tda = use_tda

    @classmethod
    def from_index(
        cls,
        index_path: Path,
        policy: CQEPolicy | None = None,
        use_tda: bool = False,
        tda_db_path: Optional[Path] = None,
        friction_alpha: float = 0.5,
        duckdb_path: Optional[Path] = None,
    ) -> "CQEOrchestrator":
        """Create orchestrator from SQLite index path.

        Args:
            index_path: Path to cqe_index.db
            policy: CQE policy (defaults to CQEPolicy.default())
            use_tda: Use TDA-enhanced adapter with friction costs
            tda_db_path: Path to tda_index.db (required if use_tda=True)
            friction_alpha: Curvature sensitivity for friction mapping
            duckdb_path: Path to quro_tda.duckdb (preferred over use_tda=True)

        Returns:
            CQEOrchestrator instance
        """
        if duckdb_path is not None and duckdb_path.exists():
            from adapters.graph.duckdb import DuckDBGraphAdapter
            adapter = DuckDBGraphAdapter(duckdb_path)
            return cls(adapter, policy, use_tda=True)

        if use_tda:
            if tda_db_path is None:
                tda_db_path = Path(".quro_context/tda_index.db")

            adapter = SQLiteTDAGraphAdapter(
                cqe_db_path=index_path,
                tda_db_path=tda_db_path,
                use_friction=True,
                friction_alpha=friction_alpha,
            )
        else:
            adapter = SQLiteGraphAdapter(index_path)

        return cls(adapter, policy, use_tda=use_tda)

    def query(
        self,
        entry_node: str,
        tau: float | None = None,
    ) -> CQEResult:
        """Run CQE query.

        Args:
            entry_node: Starting atom ID (e.g., 'cat::lock')
            tau: Pruning threshold (defaults to policy.prune.min_weight)

        Returns:
            CQEResult with max_weights and predecessors

        Pipeline:
            1. Load graph (adapter)
            2. Run kernel traversal (kernel)
            3. Return result
        """
        # Use policy threshold if tau not specified
        if tau is None:
            tau = self.policy.prune.min_weight

        max_category_fanout = self.policy.prune.max_category_fanout

        # Layer B: Graph Enrichment (Query Rewriting Phase)
        # Transform graph securely WITHOUT modifying the kernel state space
        transformed_graph = HubNormalizer.transform(
            self.adapter, 
            min_degree=10, 
            offset=1.0  # Log jittering barrier
        )
        transformed_graph = TopKPruner.transform(transformed_graph, max_edges=max_category_fanout)

        # Run kernel traversal (pure computation - Layer A)
        result = self.kernel.query(
            graph=transformed_graph,
            start=entry_node,
            tau=tau
        )

        return result

    def get_path(self, result: CQEResult, target: str) -> Tuple[str, ...]:
        """Extract path from entry to target node.

        Args:
            result: CQE query result
            target: Target atom ID

        Returns:
            Tuple of atom IDs from entry to target
        """
        if target not in result.predecessors:
            return ()

        path = []
        current = target

        while current is not None:
            path.append(current)
            current = result.predecessors.get(current)

        return tuple(reversed(path))

    def get_top_k(self, result: CQEResult, k: int = 10) -> Tuple[Tuple[str, float], ...]:
        """Get top-k nodes by weight.

        Args:
            result: CQE query result
            k: Number of top nodes to return

        Returns:
            Tuple of (atom_id, weight) sorted by weight descending
        """
        sorted_nodes = sorted(
            result.max_weights.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return tuple(sorted_nodes[:k])
