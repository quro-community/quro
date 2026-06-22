"""Scanner v3 - Adapters Module

@module quro.scanner.adapters
@intent Pluggable output adapters for scan results
"""

from scanner.adapters.protocol import ScannerAdapter
from scanner.adapters.memory import MemoryAdapter

__all__ = [
    "ScannerAdapter",
    "MemoryAdapter",
]
