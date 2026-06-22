"""Index Builder v3 - Adapters Module

@module quro.index_builder.adapters
@intent Pluggable registry adapters
"""

from index_builder.adapters.protocol import RegistryAdapter
from index_builder.adapters.memory import MemoryRegistryAdapter
from index_builder.adapters.sqlite import SQLiteRegistryAdapter

__all__ = [
    "RegistryAdapter",
    "MemoryRegistryAdapter",
    "SQLiteRegistryAdapter",
]
