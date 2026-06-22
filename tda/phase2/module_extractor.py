"""
Module Extractor for Cognitive Mass Calculation

Extracts module membership from registry.db using cat::* tags
and file path clustering as fallback.
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Set, Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleInfo:
    """Module membership information for a symbol."""

    symbol_id: str
    modules: Set[str]  # Set of module names (e.g., {"cat::async", "quro_distiller"})
    extraction_method: str  # "cat_tags" or "file_path"


class ModuleExtractor:
    """Extracts module membership from registry.db."""

    def __init__(self, registry_db_path: str, use_cat_tags: bool = True):
        """Initialize module extractor.

        Args:
            registry_db_path: Path to registry.db
            use_cat_tags: If True, use cat::* tags as primary module source
        """
        self.registry_db_path = registry_db_path
        self.use_cat_tags = use_cat_tags
        self._conn: Optional[sqlite3.Connection] = None

    def __enter__(self):
        """Context manager entry."""
        self._conn = sqlite3.connect(self.registry_db_path)
        self._conn.row_factory = sqlite3.Row
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def extract_modules_for_symbol(self, symbol_id: str) -> ModuleInfo:
        """Extract module membership for a single symbol.

        Args:
            symbol_id: Symbol ID (e.g., "sym::run_mvp_flow")

        Returns:
            ModuleInfo with extracted modules
        """
        if not self._conn:
            raise RuntimeError("ModuleExtractor must be used as context manager")

        # Fetch symbol from registry
        cursor = self._conn.execute(
            "SELECT id, type, tags, metadata FROM nodes WHERE id = ?",
            (symbol_id,)
        )
        row = cursor.fetchone()

        if not row:
            return ModuleInfo(
                symbol_id=symbol_id,
                modules=set(),
                extraction_method="not_found"
            )

        # Parse tags and metadata
        tags = json.loads(row["tags"])
        metadata = json.loads(row["metadata"])

        # Method 1: Extract from cat::* tags
        if self.use_cat_tags:
            cat_modules = self._extract_from_cat_tags(tags)
            if cat_modules:
                return ModuleInfo(
                    symbol_id=symbol_id,
                    modules=cat_modules,
                    extraction_method="cat_tags"
                )

        # Method 2: Fallback to file path clustering
        file_path = metadata.get("file_path")
        if file_path:
            path_modules = self._extract_from_file_path(file_path)
            return ModuleInfo(
                symbol_id=symbol_id,
                modules=path_modules,
                extraction_method="file_path"
            )

        # No module information available
        return ModuleInfo(
            symbol_id=symbol_id,
            modules={"unknown"},
            extraction_method="fallback"
        )

    def extract_modules_for_all_symbols(self) -> Dict[str, ModuleInfo]:
        """Extract module membership for all symbols in registry.

        Returns:
            Dict mapping symbol_id to ModuleInfo
        """
        if not self._conn:
            raise RuntimeError("ModuleExtractor must be used as context manager")

        result = {}

        cursor = self._conn.execute(
            "SELECT id, type, tags, metadata FROM nodes WHERE type = 'symbol'"
        )

        for row in cursor:
            symbol_id = row["id"]
            tags = json.loads(row["tags"])
            metadata = json.loads(row["metadata"])

            # Extract modules
            if self.use_cat_tags:
                cat_modules = self._extract_from_cat_tags(tags)
                if cat_modules:
                    result[symbol_id] = ModuleInfo(
                        symbol_id=symbol_id,
                        modules=cat_modules,
                        extraction_method="cat_tags"
                    )
                    continue

            # Fallback to file path
            file_path = metadata.get("file_path")
            if file_path:
                path_modules = self._extract_from_file_path(file_path)
                result[symbol_id] = ModuleInfo(
                    symbol_id=symbol_id,
                    modules=path_modules,
                    extraction_method="file_path"
                )
            else:
                result[symbol_id] = ModuleInfo(
                    symbol_id=symbol_id,
                    modules={"unknown"},
                    extraction_method="fallback"
                )

        return result

    def get_all_modules(self) -> Set[str]:
        """Get set of all unique modules in the system.

        Returns:
            Set of all module names
        """
        all_modules = set()
        module_infos = self.extract_modules_for_all_symbols()

        for info in module_infos.values():
            all_modules.update(info.modules)

        return all_modules

    def _extract_from_cat_tags(self, tags: list) -> Set[str]:
        """Extract modules from cat::* tags.

        Args:
            tags: List of tag strings (e.g., ["async", "database"])

        Returns:
            Set of cat::* module names (e.g., {"cat::async", "cat::database"})
        """
        cat_modules = set()

        for tag in tags:
            # Convert tag to cat::* format
            cat_module = f"cat::{tag}"
            cat_modules.add(cat_module)

        return cat_modules

    def _extract_from_file_path(self, file_path: str) -> Set[str]:
        """Extract module from file path using prefix clustering.

        Args:
            file_path: Absolute file path

        Returns:
            Set containing single module name based on path prefix
        """
        path = Path(file_path)

        # Try to find a meaningful module prefix
        # Priority: quro/module_name or top-level directory

        parts = path.parts

        # Look for quro/submodule pattern
        if "quro" in parts:
            idx = parts.index("quro")
            if idx + 1 < len(parts):
                submodule = parts[idx + 1]
                return {f"quro/{submodule}"}
            return {"quro"}

        # Look for quro_* pattern at top level
        for part in parts:
            if part.startswith("quro_"):
                return {part}

        # Fallback: use first directory after workspace root
        # Assume workspace root is the directory containing .quro_context
        for i, part in enumerate(parts):
            if part == ".quro_context" and i > 0:
                # Use parent directory as module
                return {parts[i - 1]}

        # Last resort: use first non-root directory
        if len(parts) > 1:
            return {parts[1]}

        return {"unknown"}

    def get_calling_modules(self, symbol_id: str) -> Set[str]:
        """Get set of modules that call this symbol.

        Args:
            symbol_id: Symbol ID to query

        Returns:
            Set of module names that have edges pointing to this symbol
        """
        if not self._conn:
            raise RuntimeError("ModuleExtractor must be used as context manager")

        # Get all symbols that call this symbol
        cursor = self._conn.execute(
            "SELECT DISTINCT src FROM edges WHERE dst = ?",
            (symbol_id,)
        )

        calling_symbols = [row["src"] for row in cursor]

        # Extract modules for each calling symbol
        calling_modules = set()
        for caller_id in calling_symbols:
            caller_info = self.extract_modules_for_symbol(caller_id)
            calling_modules.update(caller_info.modules)

        return calling_modules
