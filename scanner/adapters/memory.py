"""Scanner v3 - Memory Adapter

@module quro.scanner.adapters.memory
@intent In-memory storage adapter for testing
@constraint Pure Python, no external dependencies
"""

from typing import Dict, List
from scanner.types import SymbolInfo, FileInfo, ScanResult


class MemoryAdapter:
    """In-memory storage adapter.

    Stores scan results in memory using dicts.
    Useful for testing and small workspaces.
    """

    def __init__(self):
        """Initialize memory adapter."""
        self.files: Dict[str, FileInfo] = {}
        self.symbols: Dict[str, List[SymbolInfo]] = {}

    def save_file(self, file_info: FileInfo) -> None:
        """Save file metadata.

        Args:
            file_info: File information to save
        """
        self.files[file_info.file_path] = file_info

    def save_symbol(self, symbol_info: SymbolInfo) -> None:
        """Save symbol information.

        Args:
            symbol_info: Symbol information to save
        """
        file_path = symbol_info.symbol.file_path

        if file_path not in self.symbols:
            self.symbols[file_path] = []

        self.symbols[file_path].append(symbol_info)

    def save_scan_result(self, result: ScanResult) -> None:
        """Save complete scan result.

        Args:
            result: Scan result to save
        """
        # Save file info
        self.save_file(result.file_info)

        # Save all symbols
        for symbol_info in result.symbols:
            self.save_symbol(symbol_info)

    def get_symbols(self, file_path: str) -> List[SymbolInfo]:
        """Get symbols for a file.

        Args:
            file_path: File path to query

        Returns:
            List of symbols in file
        """
        return self.symbols.get(file_path, [])

    def get_file(self, file_path: str) -> FileInfo | None:
        """Get file info.

        Args:
            file_path: File path to query

        Returns:
            File info or None if not found
        """
        return self.files.get(file_path)

    def get_all_files(self) -> List[FileInfo]:
        """Get all file info.

        Returns:
            List of all file info
        """
        return list(self.files.values())

    def get_all_symbols(self) -> List[SymbolInfo]:
        """Get all symbols.

        Returns:
            List of all symbols
        """
        all_symbols = []
        for symbols in self.symbols.values():
            all_symbols.extend(symbols)
        return all_symbols

    def clear(self) -> None:
        """Clear all stored data."""
        self.files.clear()
        self.symbols.clear()
