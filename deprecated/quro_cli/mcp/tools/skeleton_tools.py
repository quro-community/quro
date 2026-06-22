"""Skeleton Graph MCP Tools.

@module quro_cli.mcp.tools.skeleton_tools
@intent Provide MCP tools for querying the skeleton dependency graph.
         Replaces graft_tools.py placeholders with functional implementations.
         Uses skeleton_* prefix (not graft_*) as per requirements.
"""
from pathlib import Path
from typing import Dict, Any, Optional

from quro_lds.skeleton_graph import GraphBuilder, QueryEngine, SkeletonStore


# ---------------------------------------------------------------------------
# Skeleton Tools
# ---------------------------------------------------------------------------

class SkeletonTools:
    """Skeleton graph MCP tools.

    @intent Provide MCP tool interface for skeleton dependency graph operations.
            Wraps quro_lds/skeleton_graph backend for AI agent consumption.
    """

    def __init__(self, workspace_root: str, db_pool=None):
        """Initialize skeleton tools.

        Args:
            workspace_root: Workspace root directory.
            db_pool: Optional asyncpg connection pool for PostgreSQL.
        """
        self.workspace_root = Path(workspace_root)
        self.db_pool = db_pool
        self.store = SkeletonStore(self.workspace_root, db_pool)
        self.builder = GraphBuilder(self.workspace_root, db_pool)

    # ----------------------------------------------------------------------
    # MCP Tool Methods
    # ----------------------------------------------------------------------

    async def skeleton_query(
        self,
        query_type: str,
        module_uid: str,
        depth: int = 3
    ) -> Dict[str, Any]:
        """Query module dependencies and dependents.

        Args:
            query_type: Type of query ("dependencies" | "dependents" | "path").
            module_uid: Module unique identifier (file path relative to workspace).
            depth: Maximum traversal depth (default: 3).

        Returns:
            Dictionary with query results.

        Example:
            >>> tools = SkeletonTools("/workspace")
            >>> result = await tools.skeleton_query("dependencies", "quro_lds.chain_store", depth=2)
            >>> result["status"]
            'success'
        """
        try:
            # Load graph
            graph = await self.store.load_graph()

            if graph is None:
                return {
                    "status": "error",
                    "error": "Graph not built. Call skeleton_build first."
                }

            # Create query engine
            engine = QueryEngine(graph)

            if query_type == "dependencies":
                result = engine.get_dependencies(module_uid, depth)
                return {
                    "status": "success",
                    "query_type": query_type,
                    "module": module_uid,
                    "depth": result.depth,
                    "dependencies": [
                        {"uid": node.uid, "file": node.file_path}
                        for node in result.related_modules
                    ],
                    "traversal_path": result.traversal_path
                }

            elif query_type == "dependents":
                result = engine.get_dependents(module_uid, depth)
                return {
                    "status": "success",
                    "query_type": query_type,
                    "module": module_uid,
                    "depth": result.depth,
                    "dependents": [
                        {"uid": node.uid, "file": node.file_path}
                        for node in result.related_modules
                    ],
                    "traversal_path": result.traversal_path
                }

            else:
                return {
                    "status": "error",
                    "error": f"Unknown query_type: {query_type}. Must be 'dependencies' or 'dependents'."
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def skeleton_trace(
        self,
        from_uid: str,
        to_uid: str
    ) -> Dict[str, Any]:
        """Trace path between two modules.

        Args:
            from_uid: Starting module UID.
            to_uid: Target module UID.

        Returns:
            Dictionary with trace results.

        Example:
            >>> tools = SkeletonTools("/workspace")
            >>> result = await tools.skeleton_trace("A", "D")
            >>> result["found"]
            True
        """
        try:
            # Load graph
            graph = await self.store.load_graph()

            if graph is None:
                return {
                    "status": "error",
                    "error": "Graph not built. Call skeleton_build first."
                }

            # Create query engine
            engine = QueryEngine(graph)

            # Trace path
            result = engine.trace_path(from_uid, to_uid)

            return {
                "status": "success",
                "from": from_uid,
                "to": to_uid,
                "found": result.found,
                "depth": result.total_depth,
                "path": [
                    {
                        "from": edge.from_uid,
                        "to": edge.to_uid,
                        "type": edge.edge_type,
                        "symbols": list(edge.symbols_imported)
                    }
                    for edge in result.path
                ]
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def skeleton_detect_cycles(self) -> Dict[str, Any]:
        """Detect all circular dependencies.

        Returns:
            Dictionary with detected cycles, sorted by risk level.

        Example:
            >>> tools = SkeletonTools("/workspace")
            >>> result = await tools.skeleton_detect_cycles()
            >>> len(result["cycles"])
            3
        """
        try:
            # Load graph
            graph = await self.store.load_graph()

            if graph is None:
                return {
                    "status": "error",
                    "error": "Graph not built. Call skeleton_build first."
                }

            # Get cycles
            cycles = graph.cycles

            return {
                "status": "success",
                "total_cycles": len(cycles),
                "cycles": [
                    {
                        "path": list(cycle.cycle_path),
                        "risk_level": cycle.risk_level,
                        "witness": cycle.witness,
                        "detected_at": cycle.detected_at.isoformat()
                    }
                    for cycle in cycles
                ]
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def skeleton_export(self, format: str = "json") -> Dict[str, Any]:
        """Export graph to JSON/DOT/GraphML.

        Args:
            format: Export format ("json" | "dot" | "graphml").

        Returns:
            Dictionary with exported graph data.

        Example:
            >>> tools = SkeletonTools("/workspace")
            >>> result = await tools.skeleton_export("json")
            >>> "nodes" in result["data"]
            True
        """
        try:
            # Load graph
            graph = await self.store.load_graph()

            if graph is None:
                return {
                    "status": "error",
                    "error": "Graph not built. Call skeleton_build first."
                }

            if format == "json":
                # Export as JSON
                import json

                data = {
                    "nodes": [
                        {
                            "uid": node.uid,
                            "file_path": node.file_path,
                            "language": node.language,
                            "exports": list(node.exports),
                            "imports": list(node.imports)
                        }
                        for node in graph.nodes
                    ],
                    "edges": [
                        {
                            "from": edge.from_uid,
                            "to": edge.to_uid,
                            "type": edge.edge_type,
                            "symbols": list(edge.symbols_imported)
                        }
                        for edge in graph.edges
                    ],
                    "cycles": [
                        {
                            "path": list(cycle.cycle_path),
                            "risk": cycle.risk_level
                        }
                        for cycle in graph.cycles
                    ]
                }

                return {
                    "status": "success",
                    "format": "json",
                    "data": data
                }

            elif format == "dot":
                # Export as DOT format (GraphViz)
                dot_lines = ["digraph skeleton_graph {"]

                # Add nodes
                for node in graph.nodes:
                    dot_lines.append(f'  "{node.uid}";')

                # Add edges
                for edge in graph.edges:
                    dot_lines.append(f'  "{edge.from_uid}" -> "{edge.to_uid}";')

                dot_lines.append("}")

                return {
                    "status": "success",
                    "format": "dot",
                    "data": "\n".join(dot_lines)
                }

            else:
                return {
                    "status": "error",
                    "error": f"Unknown format: {format}. Must be 'json' or 'dot'."
                }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

    async def skeleton_build(self, files: Optional[list[str]] = None) -> Dict[str, Any]:
        """Build dependency graph from scratch.

        Args:
            files: Optional list of specific files to scan. If None, scans entire workspace.

        Returns:
            Dictionary with build results.

        Example:
            >>> tools = SkeletonTools("/workspace")
            >>> result = await tools.skeleton_build()
            >>> result["status"]
            'success'
            >>> result["stats"]["nodes"]
            42
        """
        try:
            # Build graph
            if files:
                file_paths = [Path(f) for f in files]
                graph = await self.builder.build_module_graph(file_paths)
            else:
                graph = await self.builder.build_module_graph()

            # Save graph
            await self.store.save_graph(graph)

            return {
                "status": "success",
                "message": "Skeleton graph built successfully",
                "stats": {
                    "nodes": len(graph.nodes),
                    "edges": len(graph.edges),
                    "cycles": len(graph.cycles),
                    "checksum": graph.checksum,
                    "built_at": graph.built_at.isoformat()
                }
            }

        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
