"""
CQE Orchestrator - Full pipeline coordination

@module quro.runtime.orchestrator
@intent Coordinate CQE pipeline: canonical → kernel → result
@constraint Orchestration only, delegates to pure components

Pipeline:
1. Load index (I/O boundary)
2. Canonicalize entry token (pure logic)
3. Run kernel (pure logic)
4. Return result

This is the integration point between layers.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
from core.cqe import CQEKernel, CanonicalLayer, CQEResult, CanonicalResult
from core.cqe.policy import CQEPolicy
from io.adapters.sqlite import SQLiteIndexLoader


class CQEOrchestrator:
    """
    CQE pipeline orchestrator.

    Coordinates the full CQE query pipeline:
    - I/O layer (index loading)
    - Pure logic (canonical + kernel)
    - Result formatting

    INVARIANT: Orchestration only
    - Does NOT contain business logic
    - Delegates to pure components
    - Handles layer coordination
    """

    def __init__(self, index_path: Path | str, policy: Optional[CQEPolicy] = None):
        """
        Initialize orchestrator.

        Args:
            index_path: Path to SQLite index
            policy: CQE policy (defaults to CQEPolicy.default())
        """
        self.index_path = Path(index_path)
        self.policy = policy or CQEPolicy.default()
        self.loader = SQLiteIndexLoader(self.index_path)

        # Load components (I/O happens here)
        self.graph = self.loader.as_graph_protocol()
        symbol_table = self.loader.get_symbol_table()
        aliases = self.loader.get_aliases()

        # Initialize canonical layer (pure logic)
        self.canonical = CanonicalLayer(
            symbol_table=symbol_table,
            aliases=aliases,
            max_edit_distance=1
        )

    def query(
        self,
        query: str,
        entry_token: str,
        tau: Optional[float] = None,
        top_k: int = 50
    ) -> Dict[str, Any]:
        """
        Execute full CQE query pipeline.

        Pipeline:
        1. Canonicalize entry token
        2. Run kernel (if canonical succeeds)
        3. Format result

        Args:
            query: Natural language query (for context)
            entry_token: Entry atom name
            tau: Pruning threshold (overrides policy if provided)
            top_k: Maximum results to return

        Returns:
            Dict with status, result, and metadata
        """
        # Use policy tau if not overridden
        if tau is None:
            tau = self.policy.prune.min_weight

        # Step 1: Canonicalize entry token (pure logic)
        canonical_result = self.canonical.resolve(entry_token)

        # Handle canonicalization failures
        if canonical_result.status == "not_found":
            return {
                "status": "error",
                "error": f"Entry token not found: {entry_token}",
                "query": query,
                "entry": entry_token,
                "result": [],
            }

        if canonical_result.status == "ambiguous":
            return {
                "status": "ambiguous",
                "candidates": canonical_result.candidates,
                "query": query,
                "entry": entry_token,
                "result": [],
            }

        # Get canonical token
        canonical_token = canonical_result.token

        # Step 2: Layer B - Graph Transforms (Query Rewriting Phase)
        from core.cqe.transforms import HubNormalizer, TopKPruner
        transformed_graph = HubNormalizer.transform(self.graph)
        
        max_category_fanout = self.policy.prune.max_category_fanout
        transformed_graph = TopKPruner.transform(transformed_graph, max_edges=max_category_fanout)

        # Step 3: Run kernel (pure logic - Layer A)
        kernel_result = CQEKernel.query(
            transformed_graph, 
            canonical_token, 
            tau=tau
        )

        # Step 4: Refine result to prevent context explosion
        from core.cqe.refiner import DefaultCQERefiner
        import dataclasses

        def _fetch_node_metadata(node_id: str) -> Dict[str, Any]:
            # SQLite loader doesn't provide node metadata API yet
            # In real runtime, this would call graph.get_node(node_id)
            return {}

        refiner = DefaultCQERefiner(node_metadata_fetcher=_fetch_node_metadata)
        refined_result = refiner.refine(kernel_result, canonical_token)

        return {
            "status": "success",
            "query": query,
            "entry": canonical_token,
            "refined": dataclasses.asdict(refined_result),
            "metadata": {
                "canonical_status": canonical_result.status,
                "nodes_visited": len(kernel_result.max_weights),
                "tau": tau,
                "policy_version": self.policy.version,
            }
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get index statistics.

        Returns:
            Dict with index stats
        """
        return self.loader.get_index_stats()


class QueryResult:
    """
    Structured query result.

    Provides convenient access to query results.
    """

    def __init__(self, response: Dict[str, Any]):
        """
        Initialize from orchestrator response.

        Args:
            response: Response dict from orchestrator.query()
        """
        self.status = response["status"]
        self.query = response.get("query", "")
        self.entry = response.get("entry", "")
        self.atoms = [item["id"] for item in response.get("result", [])]
        self.weights = {
            item["id"]: item["weight"]
            for item in response.get("result", [])
        }
        self.metadata = response.get("metadata", {})
        self.error = response.get("error")
        self.candidates = response.get("candidates", [])

    @property
    def success(self) -> bool:
        """Check if query succeeded"""
        return self.status == "success"

    @property
    def top_atoms(self) -> List[str]:
        """Get top atoms (ordered by weight)"""
        return self.atoms

    def get_weight(self, atom_id: str) -> float:
        """Get weight for specific atom"""
        return self.weights.get(atom_id, 0.0)

    def __repr__(self) -> str:
        if self.success:
            return f"QueryResult(status={self.status}, atoms={len(self.atoms)})"
        else:
            return f"QueryResult(status={self.status}, error={self.error})"
