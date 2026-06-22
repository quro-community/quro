"""
TypeScript Analyzer - High-level interface for TypeScript code analysis

Combines TypeScript probe with tree-sitter fallback for robust analysis.
Provides unified interface for symbol resolution, type inference, and dependency tracking.
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from quro_cli.analysis.typescript_probe import (
    TypeScriptProbe,
    TypeScriptProbeError,
    TypeInfo,
    DefinitionLocation,
    Diagnostic
)

logger = logging.getLogger(__name__)


@dataclass
class SymbolInfo:
    """Unified symbol information"""
    name: str
    file_path: str
    line: int
    character: int
    kind: str
    type_string: Optional[str] = None
    fingerprint: Optional[str] = None
    source: str = "typescript"  # "typescript" or "tree-sitter"


@dataclass
class ImportInfo:
    """Import statement information"""
    import_path: str
    resolved_path: Optional[str]
    symbols: List[str]
    is_type_only: bool
    line: int


class TypeScriptAnalyzer:
    """
    High-level TypeScript analysis interface

    Combines TypeScript Compiler API (via probe) with tree-sitter fallback
    for robust analysis that never fails.
    """

    def __init__(self, workspace_root: str, tsconfig_path: Optional[str] = None):
        """
        Initialize analyzer

        Args:
            workspace_root: Workspace root directory
            tsconfig_path: Path to tsconfig.json (optional)
        """
        self.workspace_root = Path(workspace_root)
        self.tsconfig_path = tsconfig_path
        self.probe: Optional[TypeScriptProbe] = None
        self._probe_available = False

    async def initialize(self):
        """Initialize the analyzer and start TypeScript probe"""
        try:
            self.probe = TypeScriptProbe(self.tsconfig_path)
            await self.probe.start()
            self._probe_available = True
            logger.info("TypeScript analyzer initialized with probe")
        except Exception as e:
            logger.warning(f"TypeScript probe unavailable, using tree-sitter fallback: {e}")
            self._probe_available = False

    async def shutdown(self):
        """Shutdown the analyzer"""
        if self.probe:
            await self.probe.stop()
            self.probe = None
            self._probe_available = False

    async def get_symbol_at_position(
        self,
        file_path: str,
        line: int,
        character: int
    ) -> Optional[SymbolInfo]:
        """
        Get symbol information at a specific position

        Args:
            file_path: Absolute file path
            line: 0-indexed line number
            character: 0-indexed character offset

        Returns:
            SymbolInfo or None if no symbol found
        """
        # Try TypeScript probe first
        if self._probe_available and self.probe:
            try:
                type_info = await self.probe.get_type_at_position(file_path, line, character)
                return SymbolInfo(
                    name=type_info.symbol_name or "unknown",
                    file_path=file_path,
                    line=line,
                    character=character,
                    kind=type_info.kind,
                    type_string=type_info.type_string,
                    fingerprint=type_info.fingerprint,
                    source="typescript"
                )
            except TypeScriptProbeError as e:
                logger.debug(f"TypeScript probe failed, falling back to tree-sitter: {e}")

        # Fallback to tree-sitter
        return await self._get_symbol_tree_sitter(file_path, line, character)

    async def find_definition(
        self,
        file_path: str,
        line: int,
        character: int
    ) -> Optional[SymbolInfo]:
        """
        Find definition location for a symbol

        Args:
            file_path: Absolute file path
            line: 0-indexed line number
            character: 0-indexed character offset

        Returns:
            SymbolInfo for definition location or None
        """
        # Try TypeScript probe first
        if self._probe_available and self.probe:
            try:
                def_loc = await self.probe.find_definition(file_path, line, character)
                return SymbolInfo(
                    name=def_loc.symbol_name,
                    file_path=def_loc.file_path,
                    line=def_loc.line,
                    character=def_loc.character,
                    kind=def_loc.kind,
                    fingerprint=def_loc.fingerprint,
                    source="typescript"
                )
            except TypeScriptProbeError as e:
                logger.debug(f"TypeScript probe failed, falling back to tree-sitter: {e}")

        # Fallback to tree-sitter
        return await self._find_definition_tree_sitter(file_path, line, character)

    async def resolve_import(
        self,
        file_path: str,
        import_path: str
    ) -> Optional[str]:
        """
        Resolve import path to absolute file path

        Args:
            file_path: Source file path
            import_path: Import specifier

        Returns:
            Resolved absolute path or None
        """
        # Try TypeScript probe first
        if self._probe_available and self.probe:
            try:
                resolved = await self.probe.resolve_import_path(file_path, import_path)
                return resolved
            except TypeScriptProbeError as e:
                logger.debug(f"TypeScript probe failed, falling back to heuristic: {e}")

        # Fallback to heuristic resolution
        return self._resolve_import_heuristic(file_path, import_path)

    async def get_file_imports(self, file_path: str) -> List[ImportInfo]:
        """
        Get all imports from a file

        Args:
            file_path: Absolute file path

        Returns:
            List of ImportInfo objects
        """
        # Use tree-sitter for import extraction (faster than probe)
        return await self._get_imports_tree_sitter(file_path)

    async def get_file_exports(self, file_path: str) -> List[SymbolInfo]:
        """
        Get all exported symbols from a file

        Args:
            file_path: Absolute file path

        Returns:
            List of SymbolInfo objects for exports
        """
        # Use tree-sitter for export extraction
        return await self._get_exports_tree_sitter(file_path)

    async def get_diagnostics(self, file_path: str) -> List[Diagnostic]:
        """
        Get TypeScript diagnostics for a file

        Args:
            file_path: Absolute file path

        Returns:
            List of Diagnostic objects
        """
        if self._probe_available and self.probe:
            try:
                return await self.probe.get_diagnostics(file_path)
            except Exception as e:
                logger.warning(f"Failed to get diagnostics: {e}")

        return []

    async def health_check(self) -> Dict[str, Any]:
        """
        Check analyzer health status

        Returns:
            Health status dictionary
        """
        status = {
            "probe_available": self._probe_available,
            "workspace_root": str(self.workspace_root),
            "tsconfig_path": self.tsconfig_path
        }

        if self._probe_available and self.probe:
            try:
                probe_alive = await self.probe.ping()
                status["probe_alive"] = probe_alive
            except Exception:
                status["probe_alive"] = False

        return status

    # === Tree-sitter Fallback Methods ===

    async def _get_symbol_tree_sitter(
        self,
        file_path: str,
        line: int,
        character: int
    ) -> Optional[SymbolInfo]:
        """
        Get symbol using tree-sitter (fallback)

        TODO: Implement tree-sitter parsing
        For now, returns None (Phase 3 implementation)
        """
        logger.debug(f"Tree-sitter fallback not yet implemented for symbol at {file_path}:{line}:{character}")
        return None

    async def _find_definition_tree_sitter(
        self,
        file_path: str,
        line: int,
        character: int
    ) -> Optional[SymbolInfo]:
        """
        Find definition using tree-sitter (fallback)

        TODO: Implement tree-sitter definition lookup
        For now, returns None (Phase 3 implementation)
        """
        logger.debug(f"Tree-sitter fallback not yet implemented for definition at {file_path}:{line}:{character}")
        return None

    def _resolve_import_heuristic(
        self,
        file_path: str,
        import_path: str
    ) -> Optional[str]:
        """
        Resolve import using heuristic rules (fallback)

        Handles common patterns:
        - Relative imports: ./foo, ../bar
        - Absolute imports: @/foo (assumes @ = src/)
        - Node modules: ignored (external)
        """
        if import_path.startswith('.'):
            # Relative import
            source_dir = Path(file_path).parent
            resolved = (source_dir / import_path).resolve()

            # Try common extensions
            for ext in ['.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.tsx']:
                candidate = Path(str(resolved) + ext)
                if candidate.exists():
                    return str(candidate)

            return None

        elif import_path.startswith('@/'):
            # Absolute import with @ alias
            relative_path = import_path[2:]  # Remove '@/'
            resolved = self.workspace_root / 'src' / relative_path

            # Try common extensions
            for ext in ['.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.tsx']:
                candidate = Path(str(resolved) + ext)
                if candidate.exists():
                    return str(candidate)

            return None

        else:
            # External module - ignore
            return None

    async def _get_imports_tree_sitter(self, file_path: str) -> List[ImportInfo]:
        """
        Extract imports using tree-sitter (fallback)

        TODO: Implement tree-sitter import extraction
        For now, returns empty list (Phase 3 implementation)
        """
        logger.debug(f"Tree-sitter import extraction not yet implemented for {file_path}")
        return []

    async def _get_exports_tree_sitter(self, file_path: str) -> List[SymbolInfo]:
        """
        Extract exports using tree-sitter (fallback)

        TODO: Implement tree-sitter export extraction
        For now, returns empty list (Phase 3 implementation)
        """
        logger.debug(f"Tree-sitter export extraction not yet implemented for {file_path}")
        return []

    # === Context Manager Support ===

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.shutdown()
