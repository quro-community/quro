"""
DeepScanner MCP Tools — Structural uncertainty annotation.

@module quro_cli.mcp.tools.deep_scanner_tools
@intent Read-only AST-based structural diagnostics. No DB writes, no semantic classification.

Exposes quro_audit: returns ClassSignature + diagnostics from Deep Index.
Strictly read-only — never modifies PG, CQE, or Registry.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg

from quro_cli.scanner_deep.class_signature import extract_class_signature
from quro_cli.scanner_deep.deep_index import DeepIndex
from quro_cli.scanner_deep.audit_rules import (
    check_unbound_attributes,
    check_structural_mismatch,
    check_deprecated_references,
    check_dual_write_patterns,
)

logger = logging.getLogger(__name__)

_DEFAULT_DEEP_INDEX_PATH = ".quro_context/deep_index.db"


class DeepScannerTools:
    """DeepScanner audit tools — read-only structural diagnostics.

    All methods are pure reads. No writes to PG, CQE, or Registry.
    """

    def __init__(
        self,
        workspace_root: Path,
        db_pool: asyncpg.Pool,
        deep_index_path: Optional[str] = None,
    ):
        self.workspace_root = workspace_root
        self.db_pool = db_pool
        self.deep_index_path = deep_index_path or _DEFAULT_DEEP_INDEX_PATH

    async def quro_audit(
        self,
        file_path: Optional[str] = None,
        class_name: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run structural audit via DeepScanner.

        Modes:
            - No args: workspace-level audit (structural mismatch, deprecated refs)
            - file_path: single-file audit (unbound attributes, dual-write)
            - file_path + class_name: single-class audit (class signature + unbound attrs)

        Args:
            file_path: Optional file to audit (relative to workspace root)
            class_name: Optional class to audit (requires file_path)
            workspace_root: Override workspace root (optional)

        Returns:
            Audit result with diagnostics array, registry_health, and scan_version.
        """
        ws_root = Path(workspace_root) if workspace_root else self.workspace_root

        # Mode 1: Single class audit
        if file_path and class_name:
            return await self._audit_class(file_path, class_name, ws_root)

        # Mode 2: Single file audit
        if file_path:
            return await self._audit_file(file_path, ws_root)

        # Mode 3: Workspace-level audit
        return await self._audit_workspace(ws_root)

    async def _audit_class(
        self,
        file_path: str,
        class_name: str,
        ws_root: Path,
    ) -> Dict[str, Any]:
        """Audit a single class: return ClassSignature + unbound attribute diagnostics."""
        abs_path = ws_root / file_path
        if not abs_path.exists():
            return {
                "status": "error",
                "error": f"file not found: {file_path}",
                "scan_version": "deepscanner-v0.1",
            }

        source = abs_path.read_text(encoding="utf-8")
        sigs = extract_class_signature(source, file_path, class_name=class_name)

        if not sigs:
            return {
                "status": "success",
                "symbol": class_name,
                "observation_scope": "AST_ONLY",
                "class_signature": None,
                "diagnostics": [],
                "message": f"class {class_name} not found in {file_path}",
                "scan_version": "deepscanner-v0.1",
            }

        sig = sigs[0]
        diagnostics = check_unbound_attributes(file_path, source, sigs)

        return {
            "status": "success",
            "symbol": sig.class_name,
            "file_path": sig.file_path,
            "observation_scope": sig.observation_scope,
            "class_signature": {
                "explicit_attrs": list(sig.explicit_attrs),
                "property_attrs": list(sig.property_attrs),
                "method_names": list(sig.method_names),
            },
            "diagnostics": diagnostics,
            "scan_version": "deepscanner-v0.1",
        }

    async def _audit_file(
        self,
        file_path: str,
        ws_root: Path,
    ) -> Dict[str, Any]:
        """Audit a single file: ClassSignatures + unbound attrs + dual-write check."""
        abs_path = ws_root / file_path
        if not abs_path.exists():
            return {
                "status": "error",
                "error": f"file not found: {file_path}",
                "scan_version": "deepscanner-v0.1",
            }

        source = abs_path.read_text(encoding="utf-8")
        sigs = extract_class_signature(source, file_path)

        # Unbound attribute check
        unbound = check_unbound_attributes(file_path, source, sigs)
        diagnostics = list(unbound)

        # Dual-write pattern check
        dual_write = check_dual_write_patterns(source, file_path)
        diagnostics.extend(dual_write)

        # Also check Deep Index for cached data
        cached_count = 0
        try:
            deep_index = DeepIndex(db_path=self.deep_index_path)
            cached_sigs = deep_index.lookup_file(file_path)
            cached_count = len(cached_sigs)
            deep_index.close()
        except Exception as e:
            logger.debug("Deep Index not available for %s: %s", file_path, e)

        return {
            "status": "success",
            "file_path": file_path,
            "observation_scope": "AST_ONLY",
            "class_signatures": [
                {
                    "class_name": s.class_name,
                    "explicit_attrs": list(s.explicit_attrs),
                    "property_attrs": list(s.property_attrs),
                    "method_names": list(s.method_names),
                }
                for s in sigs
            ],
            "deep_index_cached": cached_count,
            "diagnostics": diagnostics,
            "scan_version": "deepscanner-v0.1",
        }

    async def _audit_workspace(self, ws_root: Path) -> Dict[str, Any]:
        """Workspace-level audit: structural mismatch + deprecated references."""
        registry_health = {
            "symbols_in_registry_not_in_git": 0,
            "symbols_deprecated_still_referenced": 0,
            "dual_write_patterns": 0,
        }
        diagnostics: List[Dict[str, Any]] = []

        # Query Registry for all non-deprecated symbols
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT s.symbol_name, f.file_path, s.deprecated_at
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE f.file_path IS NOT NULL
                    AND f.file_path != ''
                    ORDER BY f.file_path, s.symbol_name
                """)
        except Exception as e:
            logger.error("DeepScanner workspace audit: DB query failed: %s", e)
            return {
                "status": "error",
                "error": f"database query failed: {e}",
                "scan_version": "deepscanner-v0.1",
            }

        all_registry_symbols = [dict(r) for r in rows]

        # Build git AST symbol set (file_path::symbol_name)
        git_ast_symbols: set = set()
        for sym in all_registry_symbols:
            fp = sym["file_path"]
            abs_path = ws_root / fp
            if not abs_path.exists():
                continue
            try:
                source = abs_path.read_text(encoding="utf-8")
                if fp.endswith(".py"):
                    sigs = extract_class_signature(source, fp)
                    for sig in sigs:
                        for name in sig.all_observed:
                            git_ast_symbols.add(f"{fp}::{name}")
            except OSError as e:
                logger.debug("Cannot read %s for AST extraction: %s", fp, e)
                continue

        # Structural mismatch: registry symbols not in git AST
        mismatch_diags = check_structural_mismatch(all_registry_symbols, git_ast_symbols)
        registry_health["symbols_in_registry_not_in_git"] = len(mismatch_diags)
        diagnostics.extend(mismatch_diags)

        # Deprecated symbols still referenced
        deprecated = [
            s for s in all_registry_symbols
            if s.get("deprecated_at") is not None
        ]
        if deprecated:
            # Collect source files for active (non-deprecated) symbols
            active_files: Dict[str, str] = {}
            active_symbols = [s for s in all_registry_symbols if s.get("deprecated_at") is None]
            seen_files: set = set()
            for sym in active_symbols:
                fp = sym["file_path"]
                if fp in seen_files:
                    continue
                seen_files.add(fp)
                abs_path = ws_root / fp
                if abs_path.exists():
                    try:
                        active_files[fp] = abs_path.read_text(encoding="utf-8")
                    except OSError as e:
                        logger.debug("Cannot read %s for deprecated ref check: %s", fp, e)
                        continue

            dep_diags = check_deprecated_references(deprecated, active_files)
            registry_health["symbols_deprecated_still_referenced"] = len(dep_diags)
            diagnostics.extend(dep_diags)

        # Deep Index stats
        class_count = 0
        try:
            deep_index = DeepIndex(db_path=self.deep_index_path)
            class_count = deep_index.class_count()
            deep_index.close()
        except Exception as e:
            logger.debug("Deep Index not available for workspace audit: %s", e)

        return {
            "status": "success",
            "observation_scope": "AST_ONLY",
            "diagnostics": diagnostics,
            "registry_health": registry_health,
            "deep_index_classes": class_count,
            "scan_version": "deepscanner-v0.1",
        }
