"""Index Builder v3 - Types

@module quro.index_builder.types
@intent Define types for index building pipeline
@constraint Immutable types, no side effects
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, List, Any, Protocol, Set, TypeVar, Generic
from scanner.types import SymbolInfo

@dataclass(frozen=True)
class EdgeWeightConfig:
    """Standardized pipeline edge weight mapping with Semantic Layering."""
    # --- STRUCTURAL LAYER (Ground Truth) ---
    INHERITANCE: float = 1.0       # Is-a (Strongest base truth)
    CALL: float = 0.8              # Uses-a (Definitive execution)
    IMPORT: float = 0.5            # Depends-on (Module containment)

    # --- SEMANTIC LAYER (Heuristics & Hubs) ---
    CATEGORY_FORWARD: float = 0.5  # Is-defined-as (Downgraded to prevent Hub Domination)
    CATEGORY_REVERSE: float = 0.15 # Bipartite Gravity Hubs: Strict Hop Penalty

    # --- NOISY/RUNTIME LAYER (Weak signals) ---
    ATTR_ACCESS: float = 0.2       # State access (Heavily penalized to avoid graph bloat)


@dataclass(frozen=True)
class FilteredRefs:
    calls: Tuple[str, ...] = ()
    imports: Tuple[str, ...] = ()
    attributes: Tuple[str, ...] = ()
    inherits: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EnrichedSymbol:
    """Semantically enriched symbol.
    
    Contains the original SymbolInfo plus semantic intent and noise-filtered references.
    """
    base: SymbolInfo
    semantic_tags: Tuple[str, ...] = ()
    intent: str = "Unknown"
    confidence_score: float = 1.0
    is_noisy: bool = False
    filtered_refs: FilteredRefs = field(default_factory=FilteredRefs)

class SymbolEnricherProtocol(Protocol):
    """Protocol for semantic enrichment plugins.

    Ensures that domain-specific logic, intent extraction, and noise filtering
    are injected, rather than hardcoded into the index builder core.
    """
    def enrich(self, symbol: EnrichedSymbol) -> EnrichedSymbol:
        ...


T = TypeVar("T", bound="EnrichedSymbol")


@dataclass(frozen=True)
class TypeBoundary(Generic[T]):
    """Type boundary constraints for enricher validation.

    Defines lower and upper boundaries for semantic enrichment:
    - Lower Boundary: Required tags that must be present
    - Upper Boundary: Forbidden intents that must not be present
    """
    required_tags: Set[str] = field(default_factory=set)
    """Lower Boundary: Tags that must be present"""

    forbidden_intents: Set[str] = field(default_factory=set)
    """Upper Boundary: Intents that must not be present"""

    def validate(self, symbol: EnrichedSymbol) -> bool:
        """Validate symbol against type boundaries.

        Args:
            symbol: Enriched symbol to validate

        Returns:
            True if symbol satisfies all constraints
        """
        # Check lower boundary: all required tags must be present
        if not all(tag in symbol.semantic_tags for tag in self.required_tags):
            return False

        # Check upper boundary: no forbidden intents
        if symbol.intent in self.forbidden_intents:
            return False

        return True


@dataclass(frozen=True)
class EnricherSpec:
    """Enricher contract specification.

    Defines the formal contract that an enricher must satisfy:
    - Input constraints (what symbols it can process)
    - Output guarantees (what it produces)
    - Behavioral invariants
    """
    name: str
    """Enricher name for debugging"""

    input_boundary: TypeBoundary
    """Input constraints - what symbols this enricher accepts"""

    output_boundary: TypeBoundary
    """Output guarantees - what this enricher produces"""

    description: str = ""
    """Human-readable description of enricher behavior"""


@dataclass(frozen=True)
class RegisteredEnricher:
    """Registered enricher with priority and contract.

    Combines an enricher implementation with its priority and formal specification.
    The spec is mandatory for contract verification at system startup.
    """
    enricher: SymbolEnricherProtocol
    """The enricher implementation"""

    priority: int
    """Execution priority (lower = earlier)"""

    spec: EnricherSpec
    """Formal contract specification (mandatory)"""


class SystemArchitectureError(Exception):
    """Raised when enricher contract validation fails at system startup."""
    pass

@dataclass(frozen=True)
class GraphNode:
    """Graph node for CQE.

    Represents a symbol in the knowledge graph.
    """

    id: str
    """Node ID (e.g., 'sym::LockManager', 'cat::async')"""

    type: str
    """Node type: 'symbol' | 'category' | 'alias'"""

    tags: Tuple[str, ...] = ()
    """Behavioral/structural tags"""

    metadata: Dict[str, Any] = None
    """Optional metadata"""

    def __post_init__(self):
        """Ensure metadata is immutable."""
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


@dataclass(frozen=True)
class GraphEdge:
    """Graph edge for CQE.

    Represents a relationship between nodes.
    """

    src: str
    """Source node ID"""

    dst: str
    """Destination node ID"""

    weight: float
    """Edge weight (0, 1]"""

    kind: str
    """Edge kind: 'calls' | 'imports' | 'similar' | 'category'"""

    metadata: Dict[str, Any] = None
    """Optional metadata"""

    def __post_init__(self):
        """Validate edge and ensure metadata is immutable."""
        if self.weight <= 0 or self.weight > 1:
            raise ValueError(f"Edge weight must be in (0, 1], got {self.weight}")
        if self.metadata is None:
            object.__setattr__(self, "metadata", {})


@dataclass(frozen=True)
class IndexResult:
    """Result of indexing a symbol.

    Contains the graph nodes and edges created for a symbol.
    """

    symbol_node: GraphNode
    """Primary symbol node"""

    category_nodes: Tuple[GraphNode, ...] = ()
    """Category nodes created"""

    edges: Tuple[GraphEdge, ...] = ()
    """Edges created"""

    skipped: bool = False
    """Whether symbol was skipped"""

    skip_reason: Optional[str] = None
    """Reason for skipping"""


@dataclass(frozen=True)
class BuildStats:
    """Statistics from index building."""

    symbols_processed: int
    symbols_indexed: int
    symbols_skipped: int
    nodes_created: int
    edges_created: int
    categories_created: int
    containment_edges: int = 0

