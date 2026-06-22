"""Shadow Adapter - Public API.

@module quro.adapters.shadows
@intent Expose clean shadow file I/O operations via Protocol-driven design.
"""

from .types import (
    DSLAtom,
    ShadowFile,
    ShadowReadRequest,
    ShadowWriteRequest,
    AtomOp,
)
from .protocol import ShadowAdapter
from .filesystem import FileSystemShadow

__all__ = [
    # Types
    "DSLAtom",
    "ShadowFile",
    "ShadowReadRequest",
    "ShadowWriteRequest",
    "AtomOp",
    # Protocol
    "ShadowAdapter",
    # Implementation
    "FileSystemShadow",
]
