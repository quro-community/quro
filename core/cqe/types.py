"""
CQE Types - Core data structures from v2

@module quro.core.cqe.types
@intent Define core CQE types (from v2, unchanged)
@constraint Immutable types, no side effects

Copied from quro_sovereign/cqe_v2/types.py
"""

from dataclasses import dataclass, field
from typing import List, Optional, Protocol, Iterable, Tuple, Dict, runtime_checkable, Any


@dataclass
class CanonicalResult:
    """
    Represents the deterministic result of a canonicalization attempt.

    From v2: unchanged
    """
    status: str  # "exact" | "alias" | "corrected" | "ambiguous" | "not_found"
    token: Optional[str] = None
    candidates: List[str] = field(default_factory=list)


@dataclass
class CQEResult:
    """
    The deterministic output of the CQE Kernel.
    Contains both the final weights and the mathematical proof (predecessors) of how they were reached.

    From v2: unchanged
    """
    max_weights: Dict[str, float]
    predecessors: Dict[str, Optional[str]]


@dataclass
class CQERefinedResult:
    """
    Refined CQE result specifically formatted to prevent context explosion
    and present a structured, actionable layout for the AI.

    Categories:
    - primary_structural: Core dependencies, typically high weight (e.g. interfaces, base classes)
    - secondary_structural: Utilities or constants, typically lower weight
    - related_concepts: Non-structural, semantic associations

    Constraints:
    - strict_token_budget_est: Estimated token count, must not exceed policy limit
    """
    primary_structural: List[Dict[str, Any]] = field(default_factory=list)
    secondary_structural: List[Dict[str, Any]] = field(default_factory=list)
    related_concepts: List[Dict[str, Any]] = field(default_factory=list)

    # Context explosion safeguards
    metadata: Dict[str, Any] = field(default_factory=dict)
    strict_token_budget_est: int = 0
    truncated: bool = False

    # Prompting guidance for the LLM consuming this object
    advisory: str = ""


@dataclass
class CQETier:
    """Single tier of CQE results at a specific tau threshold."""
    tau: float
    node_count: int
    refined: CQERefinedResult
    advisory: str


@dataclass
class CQEMultiTierResult:
    """Multi-tier CQE results at different confidence levels.

    Tiers:
    - core: High confidence (tau=0.3) - tight focus on core dependencies
    - extended: Medium confidence (tau=0.1) - balanced view
    - exploratory: Low confidence (tau=0.05) - wide discovery
    """
    core: CQETier
    extended: CQETier
    exploratory: CQETier
    recommendation: str
    entry_token: str


@runtime_checkable
class CQERefinerProtocol(Protocol):
    """
    Protocol to refine a raw CQEResult into structured insights for the AI.
    
    Responsibility:
    - Categorize retrieved nodes by structural importance.
    - Fetch payloads only for primary structures, omitting or trimming secondary.
    - Apply token budget constraints to prevent context explosion.
    """
    def refine(self, result: CQEResult, entry_token: str) -> CQERefinedResult:
        ...

@runtime_checkable
class GraphProtocol(Protocol):
    """
    Protocol defining the required interface for the static graph
    used by the CQE pure kernel.

    From v2: unchanged

    INVARIANT: Pure data access
    - neighbors() must be a pure function
    - No side effects allowed
    - No I/O operations
    """
    def neighbors(self, node: str) -> Iterable[Tuple[str, float]]:
        """
        Yields tuples of (neighbor_node, edge_weight) for a given node.
        Edge weights must be in the range (0, 1].

        MUST be pure: same node → same neighbors
        """
        ...

    def edges(self, node: str) -> Iterable[Any]:
        """
        Yields GraphEdge items containing metadata and kind.
        """
        ...

    def out_degree(self, node: str) -> int:
        """
        Get out-degree for Hub normalization rules.
        """
        ...