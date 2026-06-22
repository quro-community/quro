"""
Shadow Draft Tools - Real Implementation

Integrates DSL parser and Monte Carlo simulator for safe code generation.
"""
import os
import hashlib
import json
import asyncio
from typing import Dict, Any, List, Optional
from pathlib import Path
from datetime import datetime
import logging

from quro_cli.shadow.dsl_parser import DSLAtomParser, ExecutionGraph
from quro_cli.shadow.monte_carlo_simulator import MonteCarloSimulator

logger = logging.getLogger(__name__)


class ShadowDraftManager:
    """Manages shadow drafts with Monte Carlo validation"""

    def __init__(self, workspace_root: str, risk_gate: float = 0.1):
        """
        Initialize shadow draft manager

        Args:
            workspace_root: Project root directory
            risk_gate: Maximum acceptable risk score (default 0.1)
        """
        self.workspace_root = Path(workspace_root)
        self.shadow_dir = self.workspace_root / ".quro_context" / "shadows"
        self.shadow_dir.mkdir(parents=True, exist_ok=True)

        self.parser = DSLAtomParser()
        self.simulator = MonteCarloSimulator(num_runs=1000, max_steps=1000)
        self.risk_gate = risk_gate

        # Track drafts
        self.drafts: Dict[str, Dict[str, Any]] = {}
        self.rejection_counts: Dict[str, int] = {}

    async def create_shadow_draft(
        self,
        symbol: str,
        atoms: List[str],
        language: str,
        target_path: str,
        auto_eject: bool = False
    ) -> Dict[str, Any]:
        """
        Create shadow draft from atom sequence

        Args:
            symbol: Symbol name
            atoms: List of atom strings (e.g., ["ACQ(lock)", "STA(work)", "REL(lock)"])
            language: Target language ("python" or "typescript")
            target_path: Target file path (relative to workspace root)
            auto_eject: Automatically eject if validation passes

        Returns:
            {
                "ok": bool,
                "draft_id": str,
                "checksum": str,
                "status": str,
                "error": str (if ok=false)
            }
        """
        try:
            # Parse atoms
            parsed_atoms = self.parser.parse_sequence(atoms)
            if not parsed_atoms:
                return {
                    "ok": False,
                    "error": "Failed to parse atom sequence"
                }

            # Validate sequence
            is_valid, errors = self.parser.validate_sequence(parsed_atoms)
            if not is_valid:
                return {
                    "ok": False,
                    "error": f"Invalid atom sequence: {'; '.join(errors)}"
                }

            # Build execution graph
            graph = self.parser.build_execution_graph(parsed_atoms)

            # Detect potential deadlocks (static analysis)
            warnings = self.parser.detect_potential_deadlocks(graph)

            # Generate draft ID
            draft_id = self._generate_draft_id(symbol, atoms)
            checksum = self._compute_checksum(atoms)

            # Store draft
            self.drafts[symbol] = {
                "draft_id": draft_id,
                "symbol": symbol,
                "atoms": atoms,
                "parsed_atoms": parsed_atoms,
                "graph": graph,
                "language": language,
                "target_path": target_path,
                "checksum": checksum,
                "status": "PENDING",
                "warnings": warnings,
                "created_at": datetime.utcnow().isoformat()
            }

            # Auto-eject if requested
            if auto_eject:
                eject_result = await self.eject_shadow_draft(symbol, force=False)
                return {
                    "ok": True,
                    "draft_id": draft_id,
                    "checksum": checksum,
                    "status": eject_result.get("status", "PENDING"),
                    "auto_ejected": True
                }

            return {
                "ok": True,
                "draft_id": draft_id,
                "checksum": checksum,
                "status": "PENDING"
            }

        except Exception as e:
            logger.error(f"Failed to create shadow draft: {e}")
            return {
                "ok": False,
                "error": str(e)
            }

    async def eject_shadow_draft(
        self,
        symbol: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Eject shadow draft (run Monte Carlo simulation and generate code)

        Args:
            symbol: Symbol name
            force: Force ejection even if risk score exceeds gate

        Returns:
            {
                "ok": bool,
                "status": str,  # MATERIALIZED, REJECTED, PENDING
                "risk_score": float,
                "skeleton_preview": str,
                "target_path": str,
                "error": str (if ok=false),
                "rejection_report": dict (if REJECTED)
            }
        """
        try:
            if symbol not in self.drafts:
                return {
                    "ok": False,
                    "error": f"No draft found for symbol: {symbol}"
                }

            draft = self.drafts[symbol]
            graph = draft["graph"]

            # Run Monte Carlo simulation
            logger.info(f"Running Monte Carlo simulation for {symbol}...")
            sim_result = self.simulator.simulate([graph])

            risk_score = sim_result.risk_score
            draft["risk_score"] = risk_score
            draft["simulation_result"] = sim_result

            # Check risk gate
            effective_gate = self.risk_gate
            if self.rejection_counts.get(symbol, 0) >= 3:
                # Relax gate after 3 rejections
                effective_gate = 0.3
                draft["warn_gate_relaxed"] = True

            if risk_score >= effective_gate and not force:
                # Rejected
                draft["status"] = "REJECTED"
                self.rejection_counts[symbol] = self.rejection_counts.get(symbol, 0) + 1

                rejection_report = {
                    "risk_score": risk_score,
                    "risk_gate": effective_gate,
                    "num_deadlocks": sim_result.num_deadlocks,
                    "num_runs": sim_result.num_runs,
                    "witness_traces": [
                        {
                            "deadlock_cycle": trace.deadlock_cycle,
                            "num_steps": len(trace.steps)
                        }
                        for trace in sim_result.witness_traces
                    ]
                }

                return {
                    "ok": True,
                    "status": "REJECTED",
                    "risk_score": risk_score,
                    "rejection_report": rejection_report
                }

            # Generate skeleton
            language = draft["language"]
            if language == "python":
                skeleton = self.parser.generate_python_skeleton(graph, symbol)
            elif language == "typescript":
                skeleton = self.parser.generate_typescript_skeleton(graph, symbol)
            else:
                return {
                    "ok": False,
                    "error": f"Unsupported language: {language}"
                }

            # Materialize to file
            target_path = self.workspace_root / draft["target_path"]
            target_path.parent.mkdir(parents=True, exist_ok=True)

            with open(target_path, "w") as f:
                f.write(skeleton)

            draft["status"] = "MATERIALIZED"
            draft["materialized_at"] = datetime.utcnow().isoformat()

            # Reset rejection count on success
            self.rejection_counts[symbol] = 0

            return {
                "ok": True,
                "status": "MATERIALIZED",
                "risk_score": risk_score,
                "skeleton_preview": skeleton[:500] + "..." if len(skeleton) > 500 else skeleton,
                "target_path": str(target_path)
            }

        except Exception as e:
            logger.error(f"Failed to eject shadow draft: {e}")
            return {
                "ok": False,
                "error": str(e)
            }

    async def get_draft_status(self, symbol: str) -> Dict[str, Any]:
        """
        Get status of shadow draft

        Args:
            symbol: Symbol name

        Returns:
            {
                "ok": bool,
                "status": str,
                "draft_id": str,
                "risk_score": float (if available),
                "warnings": list,
                "created_at": str,
                "materialized_at": str (if MATERIALIZED)
            }
        """
        if symbol not in self.drafts:
            return {
                "ok": False,
                "error": f"No draft found for symbol: {symbol}"
            }

        draft = self.drafts[symbol]

        return {
            "ok": True,
            "status": draft["status"],
            "draft_id": draft["draft_id"],
            "risk_score": draft.get("risk_score"),
            "warnings": draft.get("warnings", []),
            "created_at": draft["created_at"],
            "materialized_at": draft.get("materialized_at")
        }

    async def approve_self_heal(
        self,
        symbol: str,
        corrected_atoms: List[str]
    ) -> Dict[str, Any]:
        """
        Approve self-heal with corrected atom sequence

        Args:
            symbol: Symbol name
            corrected_atoms: Corrected atom sequence

        Returns:
            {
                "ok": bool,
                "draft_id": str,
                "status": str
            }
        """
        if symbol not in self.drafts:
            return {
                "ok": False,
                "error": f"No draft found for symbol: {symbol}"
            }

        draft = self.drafts[symbol]

        # Create new draft with corrected atoms
        result = await self.create_shadow_draft(
            symbol=symbol,
            atoms=corrected_atoms,
            language=draft["language"],
            target_path=draft["target_path"],
            auto_eject=True
        )

        return result

    def _generate_draft_id(self, symbol: str, atoms: List[str]) -> str:
        """Generate unique draft ID"""
        content = f"{symbol}:{':'.join(atoms)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _compute_checksum(self, atoms: List[str]) -> str:
        """Compute checksum for atom sequence"""
        content = ":".join(atoms)
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# MCP tool implementations

async def create_shadow_draft(
    symbol: str,
    atoms: List[str],
    language: str,
    target_path: str,
    auto_eject: bool = False,
    workspace_root: str = "."
) -> Dict[str, Any]:
    """
    MCP tool: create_shadow_draft

    Create shadow draft from atom sequence.
    """
    manager = ShadowDraftManager(workspace_root)
    return await manager.create_shadow_draft(
        symbol=symbol,
        atoms=atoms,
        language=language,
        target_path=target_path,
        auto_eject=auto_eject
    )


async def eject_shadow_draft(
    symbol: str,
    force: bool = False,
    workspace_root: str = "."
) -> Dict[str, Any]:
    """
    MCP tool: eject_shadow_draft

    Eject shadow draft (run Monte Carlo simulation and generate code).
    """
    manager = ShadowDraftManager(workspace_root)
    return await manager.eject_shadow_draft(symbol=symbol, force=force)


async def get_draft_status(
    symbol: str,
    workspace_root: str = "."
) -> Dict[str, Any]:
    """
    MCP tool: get_draft_status

    Get status of shadow draft.
    """
    manager = ShadowDraftManager(workspace_root)
    return await manager.get_draft_status(symbol=symbol)


async def approve_self_heal(
    symbol: str,
    corrected_atoms: List[str],
    workspace_root: str = "."
) -> Dict[str, Any]:
    """
    MCP tool: approve_self_heal

    Approve self-heal with corrected atom sequence.
    """
    manager = ShadowDraftManager(workspace_root)
    return await manager.approve_self_heal(symbol=symbol, corrected_atoms=corrected_atoms)
