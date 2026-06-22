"""Input Gates - Stateless validation operators

@module quro.pipeline.cqe.input_gates
@intent Stateless gate operators for atom/morphism validation at extraction
"""

from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from .exceptions import InputGateRejection


# High-frequency generic symbol names that pollute the CQE graph
SKIP_SYMBOL_NAMES = frozenset({
    "task_id", "path", "symbol", "error", "ok", "status", "result",
    "data", "value", "key", "name", "type", "content", "text",
    "item", "items", "entry", "record", "row", "field", "col",
    "msg", "message", "args", "kwargs", "self", "cls",
    "config", "options", "params", "headers", "payload",
    "request", "response", "output", "input", "buffer",
    "offset", "length", "index", "count", "total", "size",
    "kind", "node", "parent", "child", "children",
    "source", "target", "source_code",
    "__init__", "__repr__", "__str__", "__eq__", "__hash__", "__len__",
})


@dataclass(frozen=True)
class GateResult:
    """Result of a gate validation.

    Attributes:
        passed: True if validation passed
        reason: Rejection reason (None if passed)
        modified_data: Modified data (for transform gates)
    """
    passed: bool
    reason: Optional[str] = None
    modified_data: Optional[Dict] = None


class SymbolBlacklistGate:
    """Gate 1: Symbol blacklist validation.

    Stateless operator: Rejects high-frequency generic symbol names.
    """

    @staticmethod
    def validate(symbol_name: str) -> GateResult:
        """Validate symbol name against blacklist.

        Args:
            symbol_name: Symbol name to validate

        Returns:
            GateResult with passed=False if blacklisted
        """
        if symbol_name in SKIP_SYMBOL_NAMES:
            return GateResult(
                passed=False,
                reason="blacklisted_symbol",
            )
        return GateResult(passed=True)


class FilePathIntegrityGate:
    """Gate 2: File path integrity validation.

    Stateless operator: Validates file exists, not ignored, has directory.
    """

    def __init__(self, project_root: Path, ignore_parser=None):
        """Initialize file path gate.

        Args:
            project_root: Project root directory
            ignore_parser: Optional .quroignore parser
        """
        self.project_root = project_root
        self.ignore_parser = ignore_parser

    def validate(self, file_path: str) -> GateResult:
        """Validate file path integrity.

        Args:
            file_path: File path to validate (relative to project root)

        Returns:
            GateResult with passed=False if invalid
        """
        if not file_path:
            return GateResult(passed=False, reason="empty_file_path")

        # Sub-gate 1: File must exist on disk
        abs_path = self.project_root / file_path
        if not abs_path.exists():
            return GateResult(passed=False, reason="file_not_found")

        # Sub-gate 2: .quroignore rules
        if self.ignore_parser and self.ignore_parser.is_ignored(file_path):
            return GateResult(passed=False, reason="quroignore_match")

        # Sub-gate 3: Reject flat paths (no directory separator)
        if "/" not in file_path:
            return GateResult(passed=False, reason="flat_path_no_directory")

        return GateResult(passed=True)


class FeatureCapGate:
    """Gate 3: Feature cap validation.

    Stateless operator: Caps features to prevent SQLite BLOB limit.
    """

    MAX_FEATURES = 1000

    @staticmethod
    def validate(features: List) -> GateResult:
        """Validate and cap features list.

        Args:
            features: Features list to validate

        Returns:
            GateResult with modified_data if capped
        """
        if len(features) > FeatureCapGate.MAX_FEATURES:
            return GateResult(
                passed=True,  # Passed with modification
                reason="features_capped",
                modified_data={"features": features[:FeatureCapGate.MAX_FEATURES]},
            )
        return GateResult(passed=True)


class InputGateChain:
    """Input gate chain - coordinates all input gates.

    Stateless orchestrator: Runs all gates in sequence.
    """

    def __init__(self, project_root: Path, ignore_parser=None):
        """Initialize input gate chain.

        Args:
            project_root: Project root directory
            ignore_parser: Optional .quroignore parser
        """
        self.symbol_gate = SymbolBlacklistGate()
        self.file_gate = FilePathIntegrityGate(project_root, ignore_parser)
        self.feature_gate = FeatureCapGate()
        self.rejection_stats: Dict[str, int] = {}

    def validate_atom(
        self,
        symbol_name: str,
        file_path: str,
        features: List,
    ) -> GateResult:
        """Validate atom through all input gates.

        Args:
            symbol_name: Symbol name
            file_path: File path
            features: Features list

        Returns:
            GateResult (passed=False if any gate failed)
        """
        # Gate 1: Symbol blacklist
        result = self.symbol_gate.validate(symbol_name)
        if not result.passed:
            self._track_rejection(result.reason)
            return result

        # Gate 2: File path integrity
        result = self.file_gate.validate(file_path)
        if not result.passed:
            self._track_rejection(result.reason)
            return result

        # Gate 3: Feature cap (transform gate)
        result = self.feature_gate.validate(features)
        if result.modified_data:
            self._track_rejection(result.reason)

        return result

    def _track_rejection(self, reason: str) -> None:
        """Track rejection statistics.

        Args:
            reason: Rejection reason
        """
        self.rejection_stats[reason] = self.rejection_stats.get(reason, 0) + 1

    def get_rejection_stats(self) -> Dict[str, int]:
        """Get rejection statistics.

        Returns:
            Dict mapping reason → count
        """
        return dict(self.rejection_stats)
