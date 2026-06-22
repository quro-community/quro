"""
MCP Tools - Modular Architecture

@module quro_cli.mcp.tools
@intent Provide modular MCP tool registration with category-based organization

Architecture:
  - tools/symbol_tools.py - Symbol discovery and identification
  - tools/cqe_tools.py - CQE query and analysis
  - tools/skeleton_tools.py - Skeleton dependency graph operations
  - tools/shadow_tools.py - Shadow draft and neural compiler
  - tools/session_tools.py - Session and metadata management
  - tools/scan_tools.py - Workspace scanning and indexing
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import asyncpg

from quro_cli.analysis.typescript_analyzer import TypeScriptAnalyzer
from quro_cli.shadow.shadow_draft_tools import ShadowDraftManager

# Import tool modules
from quro_cli.mcp.tools.symbol_tools import SymbolTools
from quro_cli.mcp.tools.cqe_tools import CQETools
from quro_cli.mcp.tools.skeleton_tools import SkeletonTools
from quro_cli.mcp.tools.shadow_tools import ShadowTools
from quro_cli.mcp.tools.session_tools import SessionTools
from quro_cli.mcp.tools.scan_tools import ScanTools
from quro_cli.mcp.tools.qra_tools import QRATools
from quro_cli.mcp.tools.lds_tools import LDSTools
from quro_cli.mcp.tools.twin_tools import TwinTools
from quro_cli.mcp.tools.deep_scanner_tools import DeepScannerTools
from quro_cli.mcp.tools.call_graph_tools import CallGraphTools

logger = logging.getLogger(__name__)


class MCPTools:
    """
    MCP Tools - Modular tool registry

    Delegates to specialized tool modules:
    - SymbolTools: identify_symbol, read_source_symbol, verify_symbol_integrity
    - CQETools: cqe_query, cqe_reflect, cqe_diagnose, cqe_get_mi_stats
    - SkeletonTools: skeleton_query, skeleton_trace, skeleton_detect_cycles, skeleton_export, skeleton_build
    - ShadowTools: create_shadow_draft, eject_shadow_draft, get_draft_status
    - SessionTools: update_session, get_morph_alerts, get_nrt_alerts
    - ScanTools: get_file_morphism, save_file_morphism

    All tool modules are lazily initialized on first use — no setup() call required.
    This avoids the 3-5 second PostgreSQL connection delay at MCP server startup.
    """

    def __init__(
        self,
        workspace_root: str | Path,
        db_url: Optional[str] = None,
        tsconfig_path: Optional[str] = None
    ):
        self.workspace_root = Path(workspace_root)
        self.db_url = db_url
        self.tsconfig_path = tsconfig_path

        # Shared resources (lazy)
        self.db_pool: Optional[asyncpg.Pool] = None
        self.analyzer: Optional[TypeScriptAnalyzer] = None
        self.shadow_manager: Optional[ShadowDraftManager] = None

        # Tool modules (all None until first use)
        self.symbol_tools: Optional[SymbolTools] = None
        self.cqe_tools: Optional[CQETools] = None
        self.skeleton_tools: Optional[SkeletonTools] = None
        self.shadow_tools: Optional[ShadowTools] = None
        self.session_tools: Optional[SessionTools] = None
        self.scan_tools: Optional[ScanTools] = None
        self.qra_tools: Optional[QRATools] = None
        self.lds_tools: Optional[LDSTools] = None
        self.twin_tools: Optional[TwinTools] = None
        self.deep_scanner_tools: Optional[DeepScannerTools] = None
        self.call_graph_tools: Optional[CallGraphTools] = None

    async def _ensure_db_pool(self) -> Optional[asyncpg.Pool]:
        """Lazy-init PostgreSQL connection pool on first use."""
        if self.db_pool is None and self.db_url:
            logger.info("Lazy-initializing PostgreSQL pool...")
            self.db_pool = await asyncpg.create_pool(
                self.db_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("PostgreSQL pool initialized")
        return self.db_pool

    async def _ensure_shadow_manager(self) -> ShadowDraftManager:
        """Lazy-init shadow manager."""
        if self.shadow_manager is None:
            self.shadow_manager = ShadowDraftManager(str(self.workspace_root))
        return self.shadow_manager

    async def _ensure_analyzer(self) -> TypeScriptAnalyzer:
        """Lazy-load TypeScript analyzer (only when needed)."""
        if self.analyzer is None:
            logger.info("Lazy-loading TypeScript analyzer...")
            self.analyzer = TypeScriptAnalyzer(
                str(self.workspace_root),
                self.tsconfig_path
            )
            await self.analyzer.initialize()
            logger.info("TypeScript analyzer initialized")
        return self.analyzer

    async def _ensure_symbol_tools(self) -> SymbolTools:
        """Lazy-init symbol_tools on first use."""
        if self.symbol_tools is None:
            pool = await self._ensure_db_pool()
            self.symbol_tools = SymbolTools(
                workspace_root=self.workspace_root,
                db_pool=pool,
                analyzer_getter=self._ensure_analyzer
            )
        return self.symbol_tools

    async def _ensure_cqe_tools(self) -> CQETools:
        """Lazy-init cqe_tools on first use."""
        if self.cqe_tools is None:
            pool = await self._ensure_db_pool()
            self.cqe_tools = CQETools(
                workspace_root=self.workspace_root,
                db_pool=pool
            )
        return self.cqe_tools

    async def _ensure_skeleton_tools(self) -> SkeletonTools:
        """Lazy-init skeleton_tools on first use."""
        if self.skeleton_tools is None:
            pool = await self._ensure_db_pool()
            self.skeleton_tools = SkeletonTools(
                workspace_root=self.workspace_root,
                db_pool=pool
            )
        return self.skeleton_tools

    async def _ensure_shadow_tools(self) -> ShadowTools:
        if self.shadow_tools is None:
            mgr = await self._ensure_shadow_manager()
            self.shadow_tools = ShadowTools(
                workspace_root=self.workspace_root,
                shadow_manager=mgr
            )
        return self.shadow_tools

    async def _ensure_session_tools(self) -> SessionTools:
        if self.session_tools is None:
            pool = await self._ensure_db_pool()
            self.session_tools = SessionTools(
                workspace_root=self.workspace_root,
                db_pool=pool
            )
        return self.session_tools

    async def _ensure_scan_tools(self) -> ScanTools:
        if self.scan_tools is None:
            pool = await self._ensure_db_pool()
            self.scan_tools = ScanTools(
                workspace_root=self.workspace_root,
                db_pool=pool,
                analyzer_getter=self._ensure_analyzer
            )
        return self.scan_tools

    async def _ensure_qra_tools(self) -> QRATools:
        if self.qra_tools is None:
            pool = await self._ensure_db_pool()
            self.qra_tools = QRATools(
                workspace_root=self.workspace_root,
                db_pool=pool
            )
        return self.qra_tools

    async def _ensure_lds_tools(self) -> LDSTools:
        if self.lds_tools is None:
            pool = await self._ensure_db_pool()
            self.lds_tools = LDSTools(
                workspace_root=self.workspace_root,
                db_pool=pool
            )
        return self.lds_tools

    async def _ensure_twin_tools(self) -> TwinTools:
        if self.twin_tools is None:
            pool = await self._ensure_db_pool()
            self.twin_tools = TwinTools(
                workspace_root=self.workspace_root,
                db_pool=pool
            )
        return self.twin_tools

    async def _ensure_deep_scanner_tools(self) -> DeepScannerTools:
        if self.deep_scanner_tools is None:
            pool = await self._ensure_db_pool()
            self.deep_scanner_tools = DeepScannerTools(
                workspace_root=self.workspace_root,
                db_pool=pool,
            )
        return self.deep_scanner_tools

    async def _ensure_call_graph_tools(self) -> CallGraphTools:
        """Lazy-init call_graph_tools on first use."""
        if self.call_graph_tools is None:
            pool = await self._ensure_db_pool()
            self.call_graph_tools = CallGraphTools(
                workspace_root=self.workspace_root,
                db_pool=pool,
            )
        return self.call_graph_tools

    # === Explicit setup() for backward compat (optional) ===
    async def setup(self):
        """Initialize all tool modules eagerly (for testing or explicit init)."""
        await self._ensure_symbol_tools()
        await self._ensure_cqe_tools()
        await self._ensure_skeleton_tools()
        await self._ensure_shadow_tools()
        await self._ensure_session_tools()
        await self._ensure_scan_tools()
        await self._ensure_qra_tools()
        await self._ensure_lds_tools()
        await self._ensure_twin_tools()
        await self._ensure_deep_scanner_tools()
        await self._ensure_call_graph_tools()
        logger.info("MCP tools initialized (eager setup)")

    async def shutdown(self):
        """Cleanup resources"""
        if self.analyzer:
            await self.analyzer.shutdown()
        if self.db_pool:
            await self.db_pool.close()
        logger.info("MCP tools shutdown complete")

    async def health_check(self) -> Dict[str, Any]:
        """Health check for all tool modules"""
        health = {
            "status": "healthy",
            "workspace_root": str(self.workspace_root),
            "db_connected": self.db_pool is not None,
            "analyzer_loaded": self.analyzer is not None,
            "modules": {}
        }

        if self.analyzer:
            analyzer_health = await self.analyzer.health_check()
            health["modules"]["typescript_analyzer"] = {
                "status": "healthy" if analyzer_health.get("probe_alive") else "unhealthy",
                "probe_alive": analyzer_health.get("probe_alive", False)
            }

        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                health["modules"]["database"] = {"status": "healthy"}
            except Exception as e:
                health["modules"]["database"] = {"status": "unhealthy", "error": str(e)}
                health["status"] = "degraded"

        return health

    # === Symbol Tools (lazy) ===
    async def identify_symbol(self, symbol: str, level: Optional[str] = None, workspace_root: Optional[str] = None, task_intent: Optional[str] = None):
        tools = await self._ensure_symbol_tools()
        return await tools.identify_symbol(symbol, level, workspace_root, task_intent)

    async def read_source_symbol(self, filepath: str, symbol_name: str, line_range: Optional[list] = None):
        tools = await self._ensure_symbol_tools()
        return await tools.read_source_symbol(filepath, symbol_name, line_range)

    async def verify_symbol_integrity(self, symbol: str):
        tools = await self._ensure_symbol_tools()
        return await tools.verify_symbol_integrity(symbol)

    async def distill_patch_context(self, file_path: str, line_start: int, line_end: int):
        tools = await self._ensure_symbol_tools()
        return await tools.distill_patch_context(file_path, line_start, line_end)

    async def compact_context(self, context: str, max_tokens: int = 2000, preserve_symbols: Optional[list] = None):
        tools = await self._ensure_symbol_tools()
        return await tools.compact_context(context, max_tokens, preserve_symbols)

    async def trace_logic_path(self, start_symbol: str, end_symbol: Optional[str] = None, max_depth: int = 5):
        tools = await self._ensure_symbol_tools()
        return await tools.trace_logic_path(start_symbol, end_symbol, max_depth)

    async def get_pitfall(self, category: Optional[str] = None, severity: Optional[str] = None):
        tools = await self._ensure_symbol_tools()
        return await tools.get_pitfall(category, severity)

    async def project_panorama(self, include_stats: bool = True, include_health: bool = True):
        tools = await self._ensure_symbol_tools()
        return await tools.project_panorama(include_stats, include_health)

    async def query_semantic_inventory(self, query: str, limit: int = 10, threshold: float = 0.3):
        tools = await self._ensure_symbol_tools()
        return await tools.query_semantic_inventory(query, limit, threshold)

    async def get_vocabulary(self, file_path: str):
        tools = await self._ensure_symbol_tools()
        return await tools.get_vocabulary(file_path)

    async def quro_explore(self):
        tools = await self._ensure_symbol_tools()
        return await tools.quro_explore()

    # === CQE Tools (lazy) ===
    async def cqe_query(self, query: str, entry_token: Optional[str] = None, tau: float = 0.1, max_depth: int = 3, suggest: bool = False):
        tools = await self._ensure_cqe_tools()
        return await tools.cqe_query(query, entry_token, tau, max_depth, suggest=suggest)

    async def cqe_reflect(self, query_id: Optional[str] = None, entry_atom: Optional[str] = None, limit: int = 20, mi_summary: bool = False):
        tools = await self._ensure_cqe_tools()
        return await tools.cqe_reflect(query_id, entry_atom, limit, mi_summary)

    async def cqe_diagnose(self, query_id: str):
        tools = await self._ensure_cqe_tools()
        return await tools.cqe_diagnose(query_id)

    async def cqe_get_mi_stats(self, atom_id: Optional[str] = None):
        tools = await self._ensure_cqe_tools()
        return await tools.cqe_get_mi_stats(atom_id)

    # === Skeleton Tools (lazy) ===
    async def skeleton_query(self, query_type: str, module_uid: str, depth: int = 3):
        tools = await self._ensure_skeleton_tools()
        return await tools.skeleton_query(query_type, module_uid, depth)

    async def skeleton_trace(self, from_uid: str, to_uid: str):
        tools = await self._ensure_skeleton_tools()
        return await tools.skeleton_trace(from_uid, to_uid)

    async def skeleton_detect_cycles(self):
        tools = await self._ensure_skeleton_tools()
        return await tools.skeleton_detect_cycles()

    async def skeleton_export(self, format: str = "json"):
        tools = await self._ensure_skeleton_tools()
        return await tools.skeleton_export(format)

    async def skeleton_build(self, files=None):
        tools = await self._ensure_skeleton_tools()
        return await tools.skeleton_build(files)

    # === Shadow Tools (lazy) ===
    async def create_shadow_draft(self, symbol: str, atoms: list, language: str, target_path: str, auto_eject: bool = False):
        tools = await self._ensure_shadow_tools()
        return await tools.create_shadow_draft(symbol, atoms, language, target_path, auto_eject)

    async def eject_shadow_draft(self, symbol: str, force: bool = False):
        tools = await self._ensure_shadow_tools()
        return await tools.eject_shadow_draft(symbol, force)

    async def get_draft_status(self, symbol: str):
        tools = await self._ensure_shadow_tools()
        return await tools.get_draft_status(symbol)

    # === Session Tools (lazy) ===
    async def update_session(self, session_id: str, metadata: dict):
        tools = await self._ensure_session_tools()
        return await tools.update_session(session_id, metadata)

    async def get_morph_alerts(self, severity: Optional[str] = None, limit: int = 10):
        tools = await self._ensure_session_tools()
        return await tools.get_morph_alerts(severity, limit)

    async def get_nrt_alerts(self, severity: Optional[str] = None, limit: int = 10):
        tools = await self._ensure_session_tools()
        return await tools.get_nrt_alerts(severity, limit)

    # === Scan Tools (lazy) ===
    async def scan(self, file_paths=None, force=False):
        tools = await self._ensure_scan_tools()
        return await tools.scan(file_paths, force)

    async def enrich(self, file_paths=None, use_ai=False):
        tools = await self._ensure_scan_tools()
        return await tools.enrich(file_paths, use_ai)

    async def get_file_morphism(self, file_path: str):
        tools = await self._ensure_scan_tools()
        return await tools.get_file_morphism(file_path)

    async def save_file_morphism(self, file_path: str, morphism_data: dict):
        tools = await self._ensure_scan_tools()
        return await tools.save_file_morphism(file_path, morphism_data)

    # === QRA / LDS / Twin Tools (lazy) ===
    async def get_chain(self, symbol: str):
        tools = await self._ensure_qra_tools()
        return await tools.get_chain(symbol)

    async def commit_reasoning(self, symbol: str, reasoning: str, tags: Optional[list] = None):
        tools = await self._ensure_qra_tools()
        return await tools.commit_reasoning(symbol, reasoning, tags)

    async def commit_chain(self, symbol: str, chain: list):
        tools = await self._ensure_qra_tools()
        return await tools.commit_chain(symbol, chain)

    async def lds_audit(self, file_path: Optional[str] = None, symbol: Optional[str] = None):
        tools = await self._ensure_lds_tools()
        return await tools.lds_audit(file_path, symbol)

    async def patch_logic_atoms(self, file_path: str, atoms: list, validation: bool = True):
        tools = await self._ensure_lds_tools()
        return await tools.patch_logic_atoms(file_path, atoms, validation)

    async def approve_self_heal(self, proposal_id: str, approved: bool, reason: Optional[str] = None):
        tools = await self._ensure_twin_tools()
        return await tools.approve_self_heal(proposal_id, approved, reason)

    async def run_twin_simulation(self, atoms: list, iterations: int = 1000, timeout: int = 30):
        tools = await self._ensure_twin_tools()
        return await tools.run_twin_simulation(atoms, iterations, timeout)

    async def get_twin_report(self, simulation_id: str):
        tools = await self._ensure_twin_tools()
        return await tools.get_twin_report(simulation_id)

    # === DeepScanner Tools (lazy) ===
    async def quro_audit(
        self,
        file_path: Optional[str] = None,
        class_name: Optional[str] = None,
        workspace_root: Optional[str] = None,
    ):
        tools = await self._ensure_deep_scanner_tools()
        return await tools.quro_audit(file_path, class_name, workspace_root)

    # === Call Graph Tools (lazy) ===
    async def call_graph(self, symbol: str, depth: int = 2):
        tools = await self._ensure_call_graph_tools()
        return await tools.call_graph(symbol, depth)
