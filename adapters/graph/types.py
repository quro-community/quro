"""Graph Adapter Types

@module quro.adapters.graph.types
@intent Define graph data structures for CQE traversal
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class GraphNode:
    """Graph node (atom).

    Represents a single atom in the CQE knowledge graph.
    """

    id: str
    """Atom ID (e.g., 'cat::lock', 'sym::...')"""

    type: str
    """Atom type: 'symbol' | 'category' | 'pitfall' | 'qra'"""

    tags: Tuple[str, ...]
    """Behavioral tags (from features_json)"""


@dataclass(frozen=True)
class GraphEdge:
    """Graph edge (morphism).

    Represents a directed edge between two atoms.
    """

    src: str
    """Source atom ID"""

    dst: str
    """Destination atom ID"""

    kind: str
    """Edge type: 'CALLS' | 'CONTAINS' | 'DEFINES' | 'MEMBER_OF' | 'TAG_ANCHORED'"""

    weight: float
    """Edge weight (base weight from index)"""
