"""
@module: quro_cli.mcp.tools.shadow_tools
@intent: Shadow draft management tools for Neural Compiler integration

Provides MCP tools for creating, ejecting, and monitoring shadow drafts
in the staging area before materialization to filesystem.
"""
from typing import Dict, Any, List, Optional
from quro_cli.shadow.shadow_draft_tools import ShadowDraftManager


class ShadowTools:
    """
    Shadow draft management tools

    Provides tools for Neural Compiler shadow draft operations:
    - create_shadow_draft: Create draft in staging area
    - eject_shadow_draft: Materialize draft to filesystem
    - get_draft_status: Poll draft status
    """

    def __init__(self, workspace_root: str, shadow_manager: ShadowDraftManager):
        """
        Initialize shadow tools

        Args:
            workspace_root: Workspace root directory
            shadow_manager: Shadow draft manager instance
        """
        self.workspace_root = workspace_root
        self.shadow_manager = shadow_manager

    async def create_shadow_draft(
        self,
        symbol: str,
        atoms: List[str],
        language: str,
        target_path: str,
        auto_eject: bool = False
    ) -> Dict[str, Any]:
        """
        Create draft in staging area

        Args:
            symbol: Symbol name
            atoms: List of DSL atoms
            language: Target language (python, typescript, etc.)
            target_path: Target file path
            auto_eject: Auto-eject after creation (default: False)

        Returns:
            Dictionary with draft info:
            {
                "status": "success" | "error",
                "draft_id": str,
                "symbol": str,
                "checksum": str,
                "staging_path": str
            }
        """
        try:
            result = await self.shadow_manager.create_shadow_draft(
                symbol=symbol,
                atoms=atoms,
                language=language,
                target_path=target_path,
                auto_eject=auto_eject
            )

            if result["ok"]:
                return {
                    "status": "success",
                    "draft_id": result["draft_id"],
                    "symbol": symbol,
                    "checksum": result["checksum"],
                    "draft_status": result["status"],
                    "language": language,
                    "target_path": target_path,
                    "auto_eject": auto_eject,
                    "atoms_count": len(atoms)
                }
            else:
                return {
                    "status": "error",
                    "symbol": symbol,
                    "error": result.get("error", "Unknown error")
                }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    async def eject_shadow_draft(
        self,
        symbol: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Materialize draft to filesystem

        Args:
            symbol: Symbol name
            force: Force ejection even if validation fails (default: False)

        Returns:
            Dictionary with ejection result:
            {
                "status": "success" | "error",
                "symbol": str,
                "materialized_path": str,
                "risk_score": float
            }
        """
        try:
            result = await self.shadow_manager.eject_shadow_draft(
                symbol=symbol,
                force=force
            )

            if result["ok"]:
                return {
                    "status": "success",
                    "symbol": symbol,
                    "draft_status": result["status"],
                    "risk_score": result.get("risk_score", 0.0),
                    "materialized_path": result.get("target_path"),
                    "skeleton_preview": result.get("skeleton_preview"),
                    "forced": force,
                    "rejection_report": result.get("rejection_report")
                }
            else:
                return {
                    "status": "error",
                    "symbol": symbol,
                    "error": result.get("error", "Unknown error")
                }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }

    async def get_draft_status(
        self,
        symbol: str
    ) -> Dict[str, Any]:
        """
        Poll draft status

        Args:
            symbol: Symbol name

        Returns:
            Dictionary with draft status:
            {
                "status": "success" | "error",
                "symbol": str,
                "draft_status": str,
                "progress": float,
                "message": str
            }
        """
        try:
            result = await self.shadow_manager.get_draft_status(symbol)

            if result["ok"]:
                return {
                    "status": "success",
                    "symbol": symbol,
                    "draft_status": result["status"],
                    "draft_id": result.get("draft_id"),
                    "risk_score": result.get("risk_score"),
                    "warnings": result.get("warnings", []),
                    "created_at": result.get("created_at"),
                    "materialized_at": result.get("materialized_at")
                }
            else:
                return {
                    "status": "error",
                    "symbol": symbol,
                    "error": result.get("error", "Unknown error")
                }

        except Exception as e:
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e)
            }
