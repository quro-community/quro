"""Manifold Engine - Pure drift detection and topological analysis.

@module quro.core.morph.engine
@intent Concrete implementation of MorphKernel protocol.
        Pure topological analysis with no side effects.
"""

from typing import List, Tuple
from types import ManifoldNode, DriftResult, TopologicalHole, BettiResult


class ManifoldEngine:
    """Manifold drift detection kernel - pure implementation.

    Invariants:
    - All methods are pure (no side effects)
    - Database-blind (receives data structures, not connections)
    - No I/O (no file, database, network access)
    - No logging (pure computation only)
    """

    def __init__(self, drift_threshold: float = 0.3):
        """Initialize manifold engine.

        Args:
            drift_threshold: Jaccard distance threshold for stability
        """
        self.drift_threshold = drift_threshold

    def detect_drift(
        self,
        old_node: ManifoldNode,
        new_lsh: List[int]
    ) -> DriftResult:
        """Pure: (old_state, new_lsh) → drift_result.

        Args:
            old_node: Previous manifold state
            new_lsh: Current LSH band hashes

        Returns:
            DriftResult with drift score and stability flag

        Invariant: Deterministic (same inputs → same output).
        """
        # Compute Jaccard distance between old and new LSH
        drift = self._jaccard_distance(old_node.lsh_bands, new_lsh)

        # Stability check
        is_stable = drift < self.drift_threshold

        return DriftResult(
            symbol_uid=old_node.symbol_uid,
            drift=drift,
            is_stable=is_stable,
            old_lsh=old_node.lsh_bands,
            new_lsh=new_lsh,
            threshold=self.drift_threshold
        )

    def _jaccard_distance(self, bands1: List[int], bands2: List[int]) -> float:
        """Compute Jaccard distance between two LSH band lists.

        Args:
            bands1: First LSH band hashes
            bands2: Second LSH band hashes

        Returns:
            Jaccard distance ∈ [0.0, 1.0]

        Invariant: distance(A, B) = 1 - similarity(A, B)
        """
        if not bands1 or not bands2:
            return 1.0  # Maximum distance for empty sets

        if len(bands1) != len(bands2):
            raise ValueError(
                f"Band lists must have same length: {len(bands1)} != {len(bands2)}"
            )

        # Count matching bands
        matches = sum(1 for b1, b2 in zip(bands1, bands2) if b1 == b2)

        # Jaccard similarity = matches / total
        similarity = matches / len(bands1)

        # Jaccard distance = 1 - similarity
        return 1.0 - similarity

    def compute_betti_1(
        self,
        nodes: List[ManifoldNode],
        k_neighbors: int = 3
    ) -> BettiResult:
        """Pure: nodes → Betti number (topological invariant).

        Args:
            nodes: List of manifold nodes
            k_neighbors: Number of neighbors for k-NN graph

        Returns:
            BettiResult with β₁ and graph statistics

        Invariant: β₁ = (edges - nodes + components) // 2
        """
        if len(nodes) < 50:
            # Too few nodes for meaningful topology
            return BettiResult(
                betti_1=0,
                num_nodes=len(nodes),
                num_edges=0,
                num_components=0
            )

        try:
            import numpy as np
            from sklearn.neighbors import kneighbors_graph
            import networkx as nx

            # Extract 2D coordinates
            coords = np.array([
                (n.manifold_x, n.manifold_y) for n in nodes
            ])

            # Build k-NN graph
            adjacency = kneighbors_graph(
                coords,
                n_neighbors=k_neighbors,
                mode='connectivity',
                include_self=False
            )

            # Convert to NetworkX graph
            graph = nx.from_scipy_sparse_array(adjacency)

            # Compute graph statistics
            num_nodes = graph.number_of_nodes()
            num_edges = graph.number_of_edges()
            num_components = nx.number_connected_components(graph)

            # Compute β₁ (first Betti number)
            # β₁ = edges - nodes + components (for planar graphs)
            betti_1 = max(0, (num_edges - num_nodes + num_components) // 2)

            return BettiResult(
                betti_1=betti_1,
                num_nodes=num_nodes,
                num_edges=num_edges,
                num_components=num_components
            )

        except ImportError:
            # scikit-learn or networkx not available
            return BettiResult(
                betti_1=0,
                num_nodes=len(nodes),
                num_edges=0,
                num_components=0
            )

    def find_topological_holes(
        self,
        nodes: List[ManifoldNode],
        grid_size: int = 10,
        density_threshold: float = 0.1
    ) -> List[TopologicalHole]:
        """Pure: nodes → low-density regions.

        Args:
            nodes: List of manifold nodes
            grid_size: Grid resolution for density analysis
            density_threshold: Relative density threshold (0.0-1.0)

        Returns:
            List of TopologicalHole (low-density regions)

        Invariant: Holes are grid cells with density < threshold * avg_density.
        """
        if not nodes or len(nodes) < 5:
            return []

        # Extract coordinates
        coords = [(n.manifold_x, n.manifold_y) for n in nodes]

        # Compute bounding box
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]

        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)

        # Check for degenerate case (all points on a line)
        if x_max - x_min < 1e-9 or y_max - y_min < 1e-9:
            return []

        # Create density grid
        grid = [[0] * grid_size for _ in range(grid_size)]
        x_step = (x_max - x_min) / grid_size
        y_step = (y_max - y_min) / grid_size

        # Count nodes in each grid cell
        for x, y in coords:
            xi = min(int((x - x_min) / x_step), grid_size - 1)
            yi = min(int((y - y_min) / y_step), grid_size - 1)
            grid[xi][yi] += 1

        # Compute average density
        avg_density = len(coords) / (grid_size * grid_size)
        threshold = avg_density * density_threshold

        # Find low-density cells (holes)
        holes = []
        for xi in range(grid_size):
            for yi in range(grid_size):
                cell_density = grid[xi][yi]
                if cell_density < threshold:
                    # Compute cell center
                    cx = x_min + (xi + 0.5) * x_step
                    cy = y_min + (yi + 0.5) * y_step

                    # Relative density (0.0 = empty, 1.0 = average)
                    relative_density = cell_density / avg_density if avg_density > 0 else 0.0

                    holes.append(TopologicalHole(
                        center_x=cx,
                        center_y=cy,
                        density=relative_density,
                        grid_index=(xi, yi)
                    ))

        return holes
