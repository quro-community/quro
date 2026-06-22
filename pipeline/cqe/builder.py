"""CQE Pipeline Builder

@module quro.pipeline.cqe.builder
@intent Orchestrate Scanner → Index → CQE → Intent → Phantom pipeline

Generated from: mvp_flow_observer.py
"""

from pathlib import Path
from typing import List, Dict, Any
from scanner.orchestrator import ScannerOrchestrator
from scanner.adapters.memory import MemoryAdapter as ScannerMemoryAdapter
from index_builder import IndexBuilder, MemoryRegistryAdapter
from quro_mcp.service import QuroV3Service


class CQEPipelineBuilder:
    """Build complete CQE pipeline from scratch.

    Observed V2 behavior:
    - Edge count: 21141
    - Edge kinds: ['CALLS', 'CONTAINS', 'DEFINES', 'MEMBER_OF', 'TAG_ANCHORED']
    - Weight range: [0.01, 0.11]
    """

    def __init__(self, workspace_root: Path):
        """Initialize pipeline builder.

        Args:
            workspace_root: Workspace root directory
        """
        self.workspace_root = workspace_root
        self.service = QuroV3Service(workspace_root)

    def build(self) -> Dict[str, Any]:
        """Build complete pipeline.

        Returns:
            Build statistics
        """
        # Stage 1: Scan workspace
        scan_result = self.service.scan_workspace(progress=True)

        # Stage 2: Index is built automatically by scan_workspace

        # Stage 3: CQE query ready

        return {
            "scan": scan_result["scan"],
            "index": scan_result["index"],
            "status": "ready",
        }

    def query(self, entry_atom: str, tau: float = 0.1) -> Dict[str, Any]:
        """Run CQE query.

        Args:
            entry_atom: Starting atom (e.g., "cat::lock")
            tau: Pruning threshold

        Returns:
            Query results
        """
        return self.service.cqe_query(start=entry_atom, tau=tau, max_depth=3)
