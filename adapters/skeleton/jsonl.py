"""Skeleton Adapter - JSONL implementation.

@module quro.adapters.skeleton.jsonl
@intent JSONL (append-only) implementation of SkeletonAdapter protocol.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from .types import (
    SkeletonGraph,
    GraphInsertRequest,
    ModuleNode,
    DependencyEdge,
    CircularDependency,
)
from .protocol import SkeletonAdapter


class JsonlSkeleton:
    """JSONL implementation of SkeletonAdapter.

    Stores skeleton graph snapshots in append-only JSONL format.
    Each line is a complete graph snapshot with timestamp and checksum.
    """

    def __init__(self, workspace_root: Path):
        """Initialize with workspace root.

        Args:
            workspace_root: Workspace root directory
        """
        self.workspace_root = Path(workspace_root)
        self.jsonl_path = self.workspace_root / ".quro_context" / "skeleton_graph.jsonl"

    async def setup(self) -> None:
        """Initialize storage directory."""
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    async def save_graph(
        self,
        request: GraphInsertRequest
    ) -> SkeletonGraph:
        """Save complete skeleton graph snapshot.

        Args:
            request: Graph insert request (frozen dataclass)

        Returns:
            SkeletonGraph with timestamp and checksum
        """
        # Create graph with timestamp and checksum
        built_at = datetime.now()
        graph = SkeletonGraph(
            nodes=request.nodes,
            edges=request.edges,
            cycles=request.cycles,
            built_at=built_at,
            checksum=self._compute_checksum(request),
        )

        # Serialize to JSON
        graph_json = self._serialize_graph(graph)

        # Append to JSONL
        await self._atomic_append(graph_json)

        return graph

    async def load_graph(self) -> Optional[SkeletonGraph]:
        """Load latest skeleton graph snapshot.

        Returns:
            SkeletonGraph if exists, None otherwise
        """
        if not self.jsonl_path.exists():
            return None

        try:
            # Read all lines
            with open(self.jsonl_path, "r", encoding="utf-8") as f:
                lines = f.read().strip().split("\n")

            if not lines:
                return None

            # Take last non-empty line
            last_line = lines[-1].strip()
            if not last_line:
                return None

            # Deserialize
            return self._deserialize_graph(last_line)

        except Exception:
            return None

    async def delete_graph(self) -> bool:
        """Delete all graph data.

        Returns:
            True if deleted, False if nothing to delete
        """
        if not self.jsonl_path.exists():
            return False

        self.jsonl_path.unlink()
        return True

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _serialize_graph(self, graph: SkeletonGraph) -> str:
        """Serialize skeleton graph to JSON string."""
        data = {
            "nodes": [
                {
                    "uid": node.uid,
                    "file_path": node.file_path,
                    "language": node.language,
                    "exports": list(node.exports),
                    "imports": list(node.imports),
                    "behavioral_tags": list(node.behavioral_tags),
                    "checksum": node.checksum,
                }
                for node in graph.nodes
            ],
            "edges": [
                {
                    "from_uid": edge.from_uid,
                    "to_uid": edge.to_uid,
                    "edge_type": edge.edge_type,
                    "symbols_imported": list(edge.symbols_imported),
                    "risk_level": edge.risk_level,
                    "line_number": edge.line_number,
                }
                for edge in graph.edges
            ],
            "cycles": [
                {
                    "cycle_path": list(cycle.cycle_path),
                    "risk_level": cycle.risk_level,
                    "detected_at": cycle.detected_at.isoformat(),
                    "witness": cycle.witness,
                }
                for cycle in graph.cycles
            ],
            "built_at": graph.built_at.isoformat(),
            "checksum": graph.checksum,
        }
        return json.dumps(data)

    def _deserialize_graph(self, json_str: str) -> SkeletonGraph:
        """Deserialize JSON string to skeleton graph."""
        data = json.loads(json_str)

        # Deserialize nodes
        nodes = tuple(
            ModuleNode(
                uid=node["uid"],
                file_path=node["file_path"],
                language=node["language"],
                exports=tuple(node["exports"]),
                imports=tuple(node["imports"]),
                behavioral_tags=tuple(node.get("behavioral_tags", [])),
                checksum=node.get("checksum", ""),
            )
            for node in data["nodes"]
        )

        # Deserialize edges
        edges = tuple(
            DependencyEdge(
                from_uid=edge["from_uid"],
                to_uid=edge["to_uid"],
                edge_type=edge["edge_type"],
                symbols_imported=tuple(edge.get("symbols_imported", [])),
                risk_level=edge.get("risk_level", "LOW"),
                line_number=edge.get("line_number"),
            )
            for edge in data["edges"]
        )

        # Deserialize cycles
        cycles = tuple(
            CircularDependency(
                cycle_path=tuple(cycle["cycle_path"]),
                risk_level=cycle["risk_level"],
                detected_at=datetime.fromisoformat(cycle["detected_at"]),
                witness=cycle["witness"],
            )
            for cycle in data["cycles"]
        )

        return SkeletonGraph(
            nodes=nodes,
            edges=edges,
            cycles=cycles,
            built_at=datetime.fromisoformat(data["built_at"]),
            checksum=data["checksum"],
        )

    async def _atomic_append(self, content: str) -> None:
        """Append content to JSONL file."""
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(content + "\n")
            f.flush()

    def _compute_checksum(self, request: GraphInsertRequest) -> str:
        """Compute MD5 checksum of graph content."""
        # Create deterministic string representation
        content = json.dumps(
            {
                "nodes": [n.uid for n in request.nodes],
                "edges": [(e.from_uid, e.to_uid) for e in request.edges],
                "cycles": [list(c.cycle_path) for c in request.cycles],
            },
            sort_keys=True,
        )
        return hashlib.md5(content.encode()).hexdigest()[:8]
