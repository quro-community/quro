"""Shadow Adapter Types - Immutable data structures for shadow file operations.

@module quro.adapters.shadows.types
@intent Define pure data contracts for shadow file I/O operations.
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Literal


AtomOp = Literal["ACQUIRE", "AWAIT", "CONT", "EMIT", "GEN", "CALL", "RELEASE", "STATE"]


@dataclass(frozen=True)
class DSLAtom:
    """Pure data: DSL atom record (immutable).

    Represents a single operation in the shadow DSL.
    """
    op: AtomOp
    resource: str
    line_hint: int = 0
    in_finally: Optional[bool] = None


@dataclass(frozen=True)
class ShadowFile:
    """Pure data: shadow file record (immutable).

    Represents a complete .qss shadow file.
    """
    symbol: str
    deps: Tuple[str, ...]
    checksum: str
    atoms: Tuple[DSLAtom, ...]
    risks: Tuple[str, ...] = ()
    truncated: bool = False
    extra_symbols: Tuple[str, ...] = ()
    behavioral_tags: Tuple[str, ...] = ()
    risk_anchors: Tuple[str, ...] = ()
    schema_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ShadowReadRequest:
    """Pure data: shadow read request (immutable).

    Request to read a shadow file.
    """
    file_path: str


@dataclass(frozen=True)
class ShadowWriteRequest:
    """Pure data: shadow write request (immutable).

    Request to write a shadow file.
    """
    file_path: str
    shadow: ShadowFile
