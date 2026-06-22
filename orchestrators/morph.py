"""Morph Orchestrator - Bridges Manifold Adapter and Morph Kernel.

@module quro.orchestrators.morph
@intent Coordinate morphism drift detection and persistence.
"""

from typing import Tuple, Optional
from core.morph import ManifoldEngine, DriftResult, BettiResult
from adapters.manifold import (
    ManifoldAdapter,
    DriftResult as AdapterDriftResult,
)


class MorphOrchestrator:
    """Orchestrates morphism drift detection and persistence.

    Coordinates:
    - Morph Kernel (pure computation)
    - Manifold Adapter (I/O persistence)

    Invariant: Orchestration only, no business logic.
    """

    def __init__(
        self,
        manifold_adapter: ManifoldAdapter,
        drift_threshold: float = 0.3,
    ):
        """Initialize Morph orchestrator.

        Args:
            manifold_adapter: Manifold persistence adapter
            drift_threshold: Drift detection threshold [0, 1]
        """
        self.manifold = manifold_adapter
        self.drift_threshold = drift_threshold
        self.kernel = ManifoldEngine(drift_threshold)

    async def detect_drift(
        self,
        symbol: str,
        old_fingerprint: Tuple[int, ...],
        new_fingerprint: Tuple[int, ...],
    ) -> AdapterDriftResult:
        """Detect drift between old and new fingerprints.

        Args:
            symbol: Symbol name
            old_fingerprint: Previous LSH fingerprint
            new_fingerprint: Current LSH fingerprint

        Returns:
            DriftResult with drift metrics

        Pipeline:
            1. Compute drift (kernel)
            2. Store drift result (adapter)
        """
        # Step 1: Compute drift (pure computation)
        kernel_result = self.kernel.compute_drift(
            old_bands=old_fingerprint,
            new_bands=new_fingerprint,
        )

        # Step 2: Store drift result (I/O)
        adapter_result = AdapterDriftResult(
            symbol_uid=symbol,
            drift=kernel_result.lsh_drift,
            is_stable=kernel_result.lsh_drift <= self.drift_threshold,
            old_lsh=old_fingerprint,
            new_lsh=new_fingerprint,
            threshold=self.drift_threshold,
        )

        await self.manifold.record_drift(adapter_result)

        return adapter_result

    async def compute_topology(
        self,
        symbol: str,
        fingerprint: Tuple[int, ...],
    ) -> BettiResult:
        """Compute topological features (Betti numbers) for symbol.

        Args:
            symbol: Symbol name
            fingerprint: LSH fingerprint

        Returns:
            BettiResult with topological metrics

        Pipeline:
            1. Compute Betti numbers (kernel)
            2. Store in manifold metadata (adapter)
        """
        # Step 1: Compute topology (pure computation)
        betti = self.kernel.compute_betti_numbers(fingerprint)

        # Step 2: Store in manifold (I/O)
        # Update node metadata with Betti numbers
        node = await self.manifold.get_node(symbol)
        if node is not None:
            updated_metadata = {
                **node.metadata,
                "betti_0": betti.b0,
                "betti_1": betti.b1,
            }
            # Note: Manifold adapter would need an update_metadata method
            # For now, we just return the Betti numbers

        return betti

    async def get_drift_history(
        self,
        symbol: str,
        limit: int = 10,
    ) -> Tuple[AdapterDriftResult, ...]:
        """Get drift history for a symbol.

        Args:
            symbol: Symbol name
            limit: Maximum number of drift records

        Returns:
            Tuple of DriftResult objects

        Pipeline:
            1. Load drift history (adapter)
        """
        # Load drift history (I/O)
        history = await self.manifold.get_drift_history(symbol, limit=limit)

        return history

    async def find_drifted_symbols(
        self,
        threshold: Optional[float] = None,
    ) -> Tuple[str, ...]:
        """Find all symbols with drift above threshold.

        Args:
            threshold: Drift threshold (defaults to orchestrator threshold)

        Returns:
            Tuple of symbol names with drift

        Pipeline:
            1. Load all drift results (adapter)
            2. Filter by threshold
        """
        threshold = threshold or self.drift_threshold

        # Load all drift results (I/O)
        all_drifts = await self.manifold.list_drifts()

        # Filter by threshold
        drifted = tuple(
            drift.symbol_uid
            for drift in all_drifts
            if drift.drift > threshold
        )

        return drifted
