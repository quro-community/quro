"""
Call Graph MCP Tools.

@module quro_cli.mcp.tools.call_graph_tools
@intent Provide MCP tool for querying the call graph from morphism_edges data.
         Reads existing CALLS edges stored by CallGraphExtractor + scanner.
"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import asyncpg

logger = logging.getLogger(__name__)


class CallGraphTools:
    """Call graph query tools backed by morphism_edges.

    @intent Read-only structural adjacency queries over CALLS edges.
            No new tables, no new storage. Pure read from existing PG data.
    """

    def __init__(
        self,
        workspace_root: Path,
        db_pool: Optional[asyncpg.Pool] = None,
    ):
        self.workspace_root = workspace_root
        self.db_pool = db_pool

    async def call_graph(
        self,
        symbol: str,
        depth: int = 2,
    ) -> Dict[str, Any]:
        """BFS traversal over CALLS morphism_edges.

        Args:
            symbol: Symbol name to start traversal from.
            depth: Maximum BFS depth (default 2, clamped to [1, 10]).

        Returns:
            Dict with status, calls, called_by, edges, graph_freshness, etc.
        """
        if not self.db_pool:
            return {"status": "error", "error": "Database connection required"}

        if depth < 1:
            depth = 1
        if depth > 10:
            depth = 10

        try:
            async with self.db_pool.acquire() as conn:
                # Step 1: Resolve starting symbol
                start_row = await conn.fetchrow("""
                    SELECT s.id, s.symbol_name
                    FROM symbols s
                    WHERE s.symbol_name = $1
                      AND s.deprecated_at IS NULL
                    ORDER BY s.confidence DESC
                    LIMIT 1
                """, symbol)

                if not start_row:
                    return {
                        "status": "not_found",
                        "symbol": symbol,
                        "error": f"Symbol '{symbol}' not found or deprecated",
                    }

                start_id = start_row["id"]

                # Step 2: Get CALLS morphism_type_id
                mt_row = await conn.fetchrow("""
                    SELECT id FROM morphism_types WHERE type_name = 'CALLS'
                """)

                if not mt_row:
                    return {
                        "status": "error",
                        "error": "CALLS morphism type not found in morphism_types table",
                    }

                calls_mt_id = mt_row["id"]

                # Step 3: BFS traversal
                visited: Set[int] = {start_id}
                queue: deque = deque([(start_id, 0)])

                all_edges: List[Dict[str, Any]] = []
                calls_set: Set[str] = set()
                called_by_set: Set[str] = set()
                max_updated_at: Optional[datetime] = None

                while queue:
                    current_id, current_depth = queue.popleft()

                    if current_depth >= depth:
                        continue

                    # Fetch both outgoing and incoming CALLS edges
                    rows = await conn.fetch("""
                        SELECT
                            me.from_symbol_id,
                            me.to_symbol_id,
                            s_from.symbol_name AS from_name,
                            f_from.file_path   AS from_file,
                            s_to.symbol_name   AS to_name,
                            f_to.file_path     AS to_file,
                            me.weight,
                            me.updated_at
                        FROM morphism_edges me
                        JOIN symbols s_from ON me.from_symbol_id = s_from.id
                        JOIN files   f_from ON s_from.file_id   = f_from.id
                        JOIN symbols s_to   ON me.to_symbol_id   = s_to.id
                        JOIN files   f_to   ON s_to.file_id     = f_to.id
                        WHERE (me.from_symbol_id = $1 OR me.to_symbol_id = $1)
                          AND me.morphism_type_id = $2
                          AND s_from.deprecated_at IS NULL
                          AND s_to.deprecated_at IS NULL
                    """, current_id, calls_mt_id)

                    for row in rows:
                        from_id = row["from_symbol_id"]
                        to_id = row["to_symbol_id"]
                        from_name = row["from_name"]
                        to_name = row["to_name"]
                        from_file = row["from_file"]
                        to_file = row["to_file"]

                        edge = {
                            "from": f"{from_name} ({from_file})",
                            "to": f"{to_name} ({to_file})",
                            "from_symbol": from_name,
                            "to_symbol": to_name,
                            "from_file": from_file,
                            "to_file": to_file,
                            "weight": row["weight"],
                        }
                        all_edges.append(edge)

                        # Track freshness
                        if row["updated_at"]:
                            if max_updated_at is None or row["updated_at"] > max_updated_at:
                                max_updated_at = row["updated_at"]

                        # Collect outgoing calls from start symbol
                        if from_id == start_id:
                            calls_set.add(to_name)

                        # Collect incoming calls to start symbol
                        if to_id == start_id:
                            called_by_set.add(from_name)

                        # Enqueue unvisited neighbors
                        if from_id not in visited and from_id != current_id:
                            visited.add(from_id)
                            queue.append((from_id, current_depth + 1))

                        if to_id not in visited and to_id != current_id:
                            visited.add(to_id)
                            queue.append((to_id, current_depth + 1))

                # Deduplicate edges by (from_symbol, to_symbol)
                seen_edges: Set[tuple] = set()
                deduped_edges: List[Dict] = []
                for edge in all_edges:
                    key = (edge["from_symbol"], edge["to_symbol"])
                    if key not in seen_edges:
                        seen_edges.add(key)
                        deduped_edges.append(edge)

                return {
                    "status": "success",
                    "symbol": symbol,
                    "calls": sorted(calls_set),
                    "called_by": sorted(called_by_set),
                    "edges": deduped_edges,
                    "graph_freshness": (
                        max_updated_at.isoformat() if max_updated_at else None
                    ),
                    "depth": depth,
                    "nodes_visited": len(visited),
                }

        except Exception as e:
            logger.error("call_graph error for symbol=%s: %s", symbol, e)
            return {
                "status": "error",
                "symbol": symbol,
                "error": str(e),
            }
