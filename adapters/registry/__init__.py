"""Registry Adapter - Public API.

@module quro.adapters.registry
@intent Expose clean registry I/O operations via Protocol-driven design.
"""

from .types import (
    FileRecord,
    SymbolRecord,
    MorphismRecord,
    SymbolInsertRequest,
    MorphismInsertRequest,
)
from .protocol import RegistryAdapter
from .postgres import PostgresRegistry

__all__ = [
    # Types
    "FileRecord",
    "SymbolRecord",
    "MorphismRecord",
    "SymbolInsertRequest",
    "MorphismInsertRequest",
    # Protocol
    "RegistryAdapter",
    # Implementation
    "PostgresRegistry",
]
