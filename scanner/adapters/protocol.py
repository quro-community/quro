"""Scanner v3 - Adapter Protocol

@module quro.scanner.adapters.protocol
@intent Define interface for pluggable output adapters
@constraint Protocol only - no implementation
"""

from typing import Protocol, List
from scanner.types import SymbolInfo, FileInfo, ScanResult


class ScannerAdapter(Protocol):
    """Protocol for scanner output adapters.

    Adapters handle persistence of scan results.
    Implementations: memory, SQLite, PostgreSQL, etc.
    """

    def save_file(self, file_info: FileInfo) -> None:
        """Save file metadata.

        Args:
            file_info: File information to save
        """
        ...

    def save_symbol(self, symbol_info: SymbolInfo) -> None:
        """Save symbol information.

        Args:
            symbol_info: Symbol information to save
        """
        ...

    def save_scan_result(self, result: ScanResult) -> None:
        """Save complete scan result.

        Args:
            result: Scan result to save
        """
        ...

    def get_symbols(self, file_path: str) -> List[SymbolInfo]:
        """Get symbols for a file.

        Args:
            file_path: File path to query

        Returns:
            List of symbols in file
        """
        ...

    def clear(self) -> None:
        """Clear all stored data."""
        ...
