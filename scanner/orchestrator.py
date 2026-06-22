"""Scanner v3 - Orchestrator

@module quro.scanner.orchestrator
@intent Main scanner that wires together all components
@constraint Pure orchestration - delegates to core/gates/adapters
"""

from pathlib import Path
from typing import List, Optional, Callable
from dataclasses import dataclass

from scanner.types import (
    ParsedSymbol,
    SymbolFeatures,
    SymbolInfo,
    FileInfo,
    ScanResult,
)
from scanner.ignore_parser import QuroIgnore
from scanner.core.ast_parser import PythonASTParser
from scanner.core.feature_extractor import FeatureExtractor
from scanner.core.fingerprint import compute_fingerprint
from scanner.gates.chain import ScannerGateChain
from scanner.adapters.protocol import ScannerAdapter


@dataclass(frozen=True)
class ScanStats:
    """Statistics from a scan operation."""

    files_discovered: int
    files_scanned: int
    files_skipped: int
    symbols_found: int
    symbols_kept: int
    symbols_filtered: int
    features_capped: int


class ScannerOrchestrator:
    """Main scanner orchestrator.

    Coordinates the complete scan pipeline:
    1. File discovery (workspace traversal)
    2. File filtering (file gate)
    3. AST parsing (core parser)
    4. Feature extraction (core extractor)
    5. Symbol filtering (symbol gate)
    6. Feature validation (feature gate)
    7. Output to adapter

    Pure orchestration - delegates to specialized components.
    """

    def __init__(
        self,
        workspace_root: Path,
        adapter: ScannerAdapter,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize scanner orchestrator.

        Args:
            workspace_root: Workspace root directory
            adapter: Output adapter for scan results
            progress_callback: Optional callback for progress updates
        """
        self.workspace_root = Path(workspace_root).resolve()
        self.adapter = adapter
        self.progress_callback = progress_callback

        # Initialize components
        self.gate_chain = ScannerGateChain(workspace_root)
        self.parser = PythonASTParser()
        self.extractor = FeatureExtractor()

        # Statistics
        self._stats = {
            "files_discovered": 0,
            "files_scanned": 0,
            "files_skipped": 0,
            "symbols_found": 0,
            "symbols_kept": 0,
            "symbols_filtered": 0,
            "features_capped": 0,
        }

    def scan_workspace(self) -> ScanStats:
        """Scan entire workspace.

        Returns:
            Scan statistics
        """
        self._reset_stats()

        # Discover Python files
        files = self._discover_files()
        self._stats["files_discovered"] = len(files)

        # Scan each file
        for file_path in files:
            self._report_progress(f"Scanning {file_path.relative_to(self.workspace_root)}")
            self.scan_file(file_path)

        return self._get_stats()

    def scan_file(self, file_path: Path) -> Optional[ScanResult]:
        """Scan a single file.

        Args:
            file_path: File path to scan

        Returns:
            ScanResult if file was scanned, None if skipped
        """
        import time

        start_time = time.perf_counter()

        # Gate 1: File filter
        file_result = self.gate_chain.validate_file(file_path)
        if not file_result.passed:
            self._stats["files_skipped"] += 1
            return None

        # Read file content
        try:
            source = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            self._stats["files_skipped"] += 1
            return None

        # Parse symbols
        try:
            symbols = self.parser.parse(source, str(file_path))
        except SyntaxError:
            # Invalid Python syntax - skip file
            self._stats["files_skipped"] += 1
            return None

        self._stats["files_scanned"] += 1
        self._stats["symbols_found"] += len(symbols)

        # Process symbols
        symbol_infos = []
        for symbol in symbols:
            symbol_info = self._process_symbol(symbol, source)
            if symbol_info:
                symbol_infos.append(symbol_info)

        # Calculate scan time
        scan_time_ms = (time.perf_counter() - start_time) * 1000

        # Determine language from extension
        language = "python" if file_path.suffix == ".py" else "python-stub"

        # Create file info
        file_info = FileInfo(
            file_path=str(file_path),
            language=language,
            fingerprint=compute_fingerprint(source),
            size_bytes=len(source.encode("utf-8")),
            symbol_count=len(symbol_infos),
            scan_time_ms=scan_time_ms,
        )

        # Create scan result
        result = ScanResult(
            file_info=file_info,
            symbols=tuple(symbol_infos),
        )

        # Save to adapter
        self.adapter.save_scan_result(result)

        return result

    def _process_symbol(self, symbol: ParsedSymbol, source: str) -> Optional[SymbolInfo]:
        """Process a single symbol through gates.

        Args:
            symbol: Parsed symbol
            source: Source code (for feature extraction)

        Returns:
            SymbolInfo if symbol passes gates, None if filtered
        """
        # Gate 2: Symbol filter
        symbol_result = self.gate_chain.validate_symbol(symbol)
        if not symbol_result.passed:
            self._stats["symbols_filtered"] += 1
            return None

        # Extract features
        features = self.extractor.extract(symbol, source)

        # Gate 3: Feature gate (transform gate)
        feature_result = self.gate_chain.validate_features(features)

        # Use capped features if available
        if feature_result.modified_data:
            features = feature_result.modified_data["features"]
            self._stats["features_capped"] += 1

        # Compute fingerprint
        fingerprint = compute_fingerprint(f"{symbol.name}:{symbol.signature or ''}")

        # Create symbol info
        symbol_info = SymbolInfo(
            symbol=symbol,
            features=features,
            fingerprint=fingerprint,
        )

        self._stats["symbols_kept"] += 1
        return symbol_info

    def _discover_files(self) -> List[Path]:
        """Discover Python files in workspace.

        Uses .quroignore (gitignore-compatible) for filtering.

        Returns:
            List of Python file paths
        """
        # Use QuroIgnore for filtering
        ignore = QuroIgnore(self.workspace_root)

        # Collect all .py and .pyi files
        all_files = []
        for pattern in ["**/*.py", "**/*.pyi"]:
            for file_path in self.workspace_root.rglob(pattern):
                if file_path.is_file():
                    all_files.append(file_path)

        # Filter using .quroignore
        filtered_files = ignore.filter_paths(all_files)

        return filtered_files

    def _report_progress(self, message: str):
        """Report progress via callback.

        Args:
            message: Progress message
        """
        if self.progress_callback:
            self.progress_callback(message)

    def _reset_stats(self):
        """Reset statistics."""
        for key in self._stats:
            self._stats[key] = 0

    def _get_stats(self) -> ScanStats:
        """Get current statistics.

        Returns:
            ScanStats object
        """
        return ScanStats(**self._stats)

    def get_rejection_stats(self):
        """Get gate rejection statistics.

        Returns:
            Dict mapping rejection_reason → count
        """
        return self.gate_chain.get_rejection_stats()
