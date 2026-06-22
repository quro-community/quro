"""Registry Adapter Types - Immutable data structures for registry operations.

@module quro.adapters.registry.types
@intent Define pure data contracts for registry I/O operations.
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Literal
from datetime import datetime


@dataclass(frozen=True)
class SymbolMetadata:
    """Semantic type metadata for symbols.

    Distinguishes between TYPE nodes (Classes, Modules) and EXECUTOR nodes (Methods, Functions).
    """
    node_type: Literal["class", "method", "function", "module"]
    """Semantic node type"""

    is_container: bool
    """True for Classes and Modules (structural nodes)"""

    is_executor: bool
    """True for Methods and Functions (behavioral nodes)"""

    @classmethod
    def from_symbol_kind(cls, kind: str) -> "SymbolMetadata":
        """Derive metadata from symbol kind.

        Args:
            kind: Symbol kind from scanner (e.g., 'class', 'method', 'function')

        Returns:
            SymbolMetadata with appropriate flags
        """
        if kind == "class":
            return cls(node_type="class", is_container=True, is_executor=False)
        elif kind in ("method", "async_method"):
            return cls(node_type="method", is_container=False, is_executor=True)
        elif kind == "function":
            return cls(node_type="function", is_container=False, is_executor=True)
        elif kind == "module":
            return cls(node_type="module", is_container=True, is_executor=False)
        else:
            # Default to function for unknown kinds
            return cls(node_type="function", is_container=False, is_executor=True)


@dataclass(frozen=True)
class FileRecord:
    """Pure data: file record (immutable).

    Represents a source file in the registry.
    """
    id: int
    file_path: str
    language: str
    fingerprint: Optional[str] = None
    fidelity: float = 1.0
    contract_status: str = "INCOMPLETE"
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class SymbolRecord:
    """Pure data: symbol record (immutable).

    Represents a symbol (function, class, etc.) in the registry.
    """
    id: int
    canonical_uid: str
    file_id: int
    file_path: str
    symbol_name: str
    symbol_type: str
    content_hash: str
    canonical_hash: str
    role: Optional[str] = None
    intent: Optional[str] = None
    tags: Tuple[str, ...] = ()
    confidence: float = 0.8
    scan_completed: bool = False
    language: Optional[str] = None
    scanned_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    node_type: Optional[str] = None
    is_container: Optional[bool] = None
    is_executor: Optional[bool] = None


@dataclass(frozen=True)
class MorphismRecord:
    """Pure data: morphism edge record (immutable).

    Represents a relationship between two symbols.
    """
    id: int
    from_symbol_id: int
    to_symbol_id: int
    morphism_type: str
    weight: float
    metadata: dict
    updated_at: Optional[datetime] = None


@dataclass(frozen=True)
class SymbolInsertRequest:
    """Pure data: symbol insert request (immutable).

    Request to insert or update a symbol.
    """
    file_path: str
    symbol_name: str
    symbol_type: str = 'function'
    role: Optional[str] = None
    intent: Optional[str] = None
    tags: Tuple[str, ...] = ()
    confidence: float = 0.8
    scan_completed: bool = False
    lsh_signature: Optional[str] = None
    signature: Optional[str] = None
    fingerprint: Optional[str] = None
    fidelity: float = 1.0
    contract_status: str = "INCOMPLETE"
    node_type: Optional[str] = None
    is_container: Optional[bool] = None
    is_executor: Optional[bool] = None


@dataclass(frozen=True)
class MorphismInsertRequest:
    """Pure data: morphism insert request (immutable).

    Request to insert or update a morphism edge.
    """
    from_symbol_name: str
    to_symbol_name: str
    morphism_type: str = 'CALLS'
    weight: float = 0.8
    metadata: dict = None

    def __post_init__(self):
        """Set default metadata if None."""
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})
