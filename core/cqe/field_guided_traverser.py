"""Field-Guided Traverser — TDA Energy Landscape Navigation

@module quro.core.cqe.field_guided_traverser
@intent Follow TDA field vectors for energy descent (to attractors) or
       ascent (from repellers). Uses field magnitude and direction from
       Phase 2.5 offline physics.

       Navigation modes:
       - DESCENT: Follow negative gradient to attractors (stable wells)
       - ASCENT: Follow positive gradient from repellers (escape volatility)

       Field vector: F(x) = -∇E(x) from Phase 2.5 Pass 4
"""

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Set, Tuple

from adapters.graph.protocol import GraphAdapter
from core.cqe.tda_bridge import TDABridge
from core.cqe.node_state import FieldRole

logger = logging.getLogger(__name__)


class FieldNavigationMode(Enum):
    """Field navigation mode."""
    DESCENT = "descent"    # Follow gradient to attractors (minimize energy)
    ASCENT = "ascent"      # Follow gradient from repellers (maximize energy)


@dataclass(frozen=True)
class FieldGuidedResult:
    """Result of field-guided traversal.

    Attributes:
        start_node: Starting node ID
        mode: Navigation mode (DESCENT or ASCENT)
        visited_nodes: Set of visited node IDs
        trajectory: List of (node_id, energy, field_magnitude) along path
        endpoint: Final node reached
        endpoint_role: Field role of endpoint (attractor/repeller/saddle/other)
        total_energy_change: Total energy change along trajectory
    """
    start_node: str
    mode: FieldNavigationMode
    visited_nodes: Set[str]
    trajectory: List[Tuple[str, float, float]]
    endpoint: str
    endpoint_role: FieldRole
    total_energy_change: float


class FieldGuidedTraverser:
    """Field-guided traverser following TDA energy gradients.

    Uses field vectors from Phase 2.5 to navigate energy landscape.
    Descent mode: follow gradient to attractors (stable wells).
    Ascent mode: follow gradient from repellers (escape volatility).

    Invariant: Follows steepest gradient at each step.
    """

    def __init__(
        self,
        graph: GraphAdapter,
        tda_bridge: TDABridge,
    ):
        """Initialize field-guided traverser.

        Args:
            graph: Graph adapter
            tda_bridge: TDA bridge for field vectors and energy
        """
        self.graph = graph
        self.tda_bridge = tda_bridge

    def _compute_field_alignment(
        self,
        current_node: str,
        neighbor_node: str,
        mode: FieldNavigationMode,
    ) -> float:
        """Compute field alignment score for neighbor selection.

        For DESCENT: prefer neighbors with lower energy (negative gradient).
        For ASCENT: prefer neighbors with higher energy (positive gradient).

        Args:
            current_node: Current node ID
            neighbor_node: Neighbor node ID
            mode: Navigation mode

        Returns:
            Alignment score (higher = better alignment)
        """
        current_energy = self.tda_bridge.get_energy_total(current_node)
        neighbor_energy = self.tda_bridge.get_energy_total(neighbor_node)

        energy_delta = neighbor_energy - current_energy

        if mode == FieldNavigationMode.DESCENT:
            # Prefer lower energy (negative delta)
            return -energy_delta
        else:  # ASCENT
            # Prefer higher energy (positive delta)
            return energy_delta

    def traverse(
        self,
        start_node: str,
        mode: FieldNavigationMode = FieldNavigationMode.DESCENT,
        max_steps: int = 10,
    ) -> FieldGuidedResult:
        """Traverse following field gradient.

        Greedy algorithm: at each step, select neighbor with best field alignment.
        Stops when reaching attractor (DESCENT) or when no better neighbor exists.

        Args:
            start_node: Starting node ID
            mode: Navigation mode (DESCENT or ASCENT)
            max_steps: Maximum traversal steps (default 10)

        Returns:
            FieldGuidedResult with trajectory and endpoint
        """
        logger.info(
            "Starting field-guided traversal from %s (mode=%s, max_steps=%d)",
            start_node, mode.value, max_steps,
        )

        # Initialize trajectory
        visited: Set[str] = set()
        trajectory: List[Tuple[str, float, float]] = []
        current_node = start_node

        # Record start state
        start_energy = self.tda_bridge.get_energy_total(start_node)
        start_field = self.tda_bridge.get_field_magnitude(start_node)
        trajectory.append((start_node, start_energy, start_field))
        visited.add(start_node)

        # Greedy traversal
        for step in range(max_steps):
            # Get current state
            current_energy = self.tda_bridge.get_energy_total(current_node)
            current_field_role = self.tda_bridge.get_field_role(current_node)

            # Stop if reached attractor (DESCENT mode)
            if mode == FieldNavigationMode.DESCENT and current_field_role == FieldRole.ATTRACTOR:
                logger.info("Reached attractor at step %d: %s", step, current_node)
                break

            # Stop if reached repeller (ASCENT mode)
            if mode == FieldNavigationMode.ASCENT and current_field_role == FieldRole.REPELLER:
                logger.info("Reached repeller at step %d: %s", step, current_node)
                break

            # Get neighbors
            neighbors = list(self.graph.neighbors(current_node))

            if not neighbors:
                logger.info("No neighbors at step %d, stopping", step)
                break

            # Score neighbors by field alignment
            neighbor_scores: List[Tuple[str, float]] = []
            for neighbor_id, edge_weight in neighbors:
                if neighbor_id in visited:
                    continue

                alignment = self._compute_field_alignment(current_node, neighbor_id, mode)
                # Combine alignment with edge weight
                score = alignment * edge_weight
                neighbor_scores.append((neighbor_id, score))

            if not neighbor_scores:
                logger.info("All neighbors visited, stopping at step %d", step)
                break

            # Select best neighbor (highest score)
            neighbor_scores.sort(key=lambda x: x[1], reverse=True)
            best_neighbor, best_score = neighbor_scores[0]

            # Stop if no improvement (local minimum/maximum)
            if best_score <= 0:
                logger.info("No improvement possible at step %d, stopping", step)
                break

            # Move to best neighbor
            current_node = best_neighbor
            visited.add(current_node)

            # Record state
            neighbor_energy = self.tda_bridge.get_energy_total(current_node)
            neighbor_field = self.tda_bridge.get_field_magnitude(current_node)
            trajectory.append((current_node, neighbor_energy, neighbor_field))

            logger.debug(
                "Step %d: moved to %s (energy=%.4f, field=%.4f, score=%.4f)",
                step + 1, current_node, neighbor_energy, neighbor_field, best_score,
            )

        # Compute total energy change
        end_energy = self.tda_bridge.get_energy_total(current_node)
        total_energy_change = end_energy - start_energy

        # Get endpoint role
        endpoint_role = self.tda_bridge.get_field_role(current_node)

        logger.info(
            "Field-guided traversal complete: %d steps, energy change %.4f, endpoint role %s",
            len(trajectory) - 1, total_energy_change, endpoint_role.value,
        )

        return FieldGuidedResult(
            start_node=start_node,
            mode=mode,
            visited_nodes=visited,
            trajectory=trajectory,
            endpoint=current_node,
            endpoint_role=endpoint_role,
            total_energy_change=total_energy_change,
        )

    def find_nearest_attractor(
        self,
        start_node: str,
        max_steps: int = 10,
    ) -> Tuple[str, float]:
        """Find nearest attractor via energy descent.

        Args:
            start_node: Starting node ID
            max_steps: Maximum traversal steps

        Returns:
            Tuple of (attractor_id, energy_change)
        """
        result = self.traverse(start_node, FieldNavigationMode.DESCENT, max_steps)

        if result.endpoint_role == FieldRole.ATTRACTOR:
            return (result.endpoint, result.total_energy_change)
        else:
            # Did not reach attractor
            return (result.endpoint, result.total_energy_change)

    def escape_repeller(
        self,
        start_node: str,
        max_steps: int = 5,
    ) -> Tuple[str, float]:
        """Escape from repeller via energy ascent.

        Args:
            start_node: Starting repeller node ID
            max_steps: Maximum traversal steps

        Returns:
            Tuple of (escape_node, energy_change)
        """
        result = self.traverse(start_node, FieldNavigationMode.ASCENT, max_steps)
        return (result.endpoint, result.total_energy_change)
