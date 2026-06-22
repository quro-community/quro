"""Scanner v3 - Gate Chain

@module quro.scanner.gates.chain
@intent Orchestrate gate execution and track statistics
@constraint Stateless gates, mutable statistics
"""

from pathlib import Path
from typing import Dict
from scanner.types import ParsedSymbol, SymbolFeatures
from scanner.gates.types import GateResult
from scanner.gates.file_filter import FileFilterGate
from scanner.gates.symbol_filter import SymbolFilterGate
from scanner.gates.feature_gate import FeatureGate


class ScannerGateChain:
    """Scanner gate chain orchestrator.

    Coordinates file and symbol gates, tracks rejection statistics.

    Gates are stateless, but chain tracks statistics.
    """

    def __init__(self, workspace_root: Path):
        """Initialize gate chain.

        Args:
            workspace_root: Workspace root directory
        """
        self.workspace_root = Path(workspace_root)

        # Initialize gates
        self.file_gate = FileFilterGate(workspace_root)
        self.symbol_gate = SymbolFilterGate()
        self.feature_gate = FeatureGate()

        # Statistics (mutable)
        self.rejection_stats: Dict[str, int] = {}

    def validate_file(self, file_path: Path) -> GateResult:
        """Validate file through file gate.

        Args:
            file_path: File path to validate

        Returns:
            GateResult
        """
        result = self.file_gate.validate(file_path)

        if not result.passed:
            self._track_rejection(result.reason)

        return result

    def validate_symbol(self, symbol: ParsedSymbol) -> GateResult:
        """Validate symbol through symbol gate.

        Args:
            symbol: Parsed symbol to validate

        Returns:
            GateResult
        """
        result = self.symbol_gate.validate(symbol)

        if not result.passed:
            self._track_rejection(result.reason)

        return result

    def validate_features(self, features: SymbolFeatures) -> GateResult:
        """Validate and cap features through feature gate.

        Transform gate: May return modified features.

        Args:
            features: Symbol features to validate

        Returns:
            GateResult with optional modified_data
        """
        result = self.feature_gate.validate(features)

        if result.reason:  # Capped
            self._track_rejection(result.reason)

        return result

    def get_rejection_stats(self) -> Dict[str, int]:
        """Get rejection statistics.

        Returns:
            Dict mapping rejection_reason → count
        """
        return self.rejection_stats.copy()

    def reset_stats(self):
        """Reset rejection statistics."""
        self.rejection_stats.clear()

    def _track_rejection(self, reason: str):
        """Track rejection reason.

        Args:
            reason: Rejection reason
        """
        self.rejection_stats[reason] = self.rejection_stats.get(reason, 0) + 1
