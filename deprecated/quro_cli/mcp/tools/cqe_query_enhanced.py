"""
CQE Query Enhanced - Semantic filtering support for CQE queries

@module quro_cli.mcp.tools.cqe_query_enhanced
@intent Extend CQE query with semantic metadata filtering (Design 72 Ξ-14, Ξ-16)

Design 72 Ξ-14: Dual-Layer Metadata Architecture
Design 72 Ξ-16: Category System Refactoring

This module provides enhanced CQE query with semantic filtering:
- Filter by framework (http, graphql, grpc)
- Filter by type (endpoint, middleware, resolver)
- Filter by method (GET, POST, etc.)
- Filter by path pattern (/api/*)
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SemanticFilter:
    """
    Semantic filter for CQE query results.

    @intent Filter atoms by framework-specific metadata
    """

    def __init__(
        self,
        framework: str | None = None,
        type: str | None = None,
        method: str | None = None,
        path_pattern: str | None = None,
    ):
        self.framework = framework
        self.type = type
        self.method = method
        self.path_pattern = path_pattern

    def matches(self, metadata: dict[str, Any]) -> bool:
        """
        Check if metadata matches filter criteria.

        @intent Apply filter rules to semantic metadata

        Args:
            metadata: Semantic metadata dict from semantic_metadata table

        Returns:
            True if metadata matches all filter criteria
        """
        # Framework filter
        if self.framework and metadata.get('framework_id') != self.framework:
            return False

        # Extract endpoints from metadata
        endpoints = metadata.get('endpoints', [])
        if not endpoints:
            return False

        # Check if any endpoint matches
        for endpoint in endpoints:
            # Type filter (endpoint, middleware, etc.)
            if self.type and self.type != 'endpoint':
                continue

            # Method filter
            if self.method and endpoint.get('method') != self.method.upper():
                continue

            # Path pattern filter
            if self.path_pattern:
                path = endpoint.get('path', '')
                if not self._match_path_pattern(path, self.path_pattern):
                    continue

            # All filters passed
            return True

        return False

    def _match_path_pattern(self, path: str, pattern: str) -> bool:
        """
        Match path against pattern with wildcard support.

        @intent Support glob-style path matching

        Examples:
            /api/* matches /api/users, /api/posts
            /api/users/* matches /api/users/123
            /api/*/profile matches /api/users/profile, /api/admin/profile
        """
        import re

        # Convert glob pattern to regex
        regex_pattern = pattern.replace('*', '[^/]+')
        regex_pattern = f'^{regex_pattern}$'

        return bool(re.match(regex_pattern, path))


async def cqe_query_enhanced(
    index_path: Path,
    query: str,
    entry_token: str,
    tau: float = 0.1,
    max_depth: int = 3,
    semantic_filter: SemanticFilter | None = None,
) -> dict[str, Any]:
    """
    Enhanced CQE query with semantic filtering.

    @intent Combine behavioral query with semantic metadata filtering

    Args:
        index_path: Path to cqe_index.db
        query: Natural language query
        entry_token: Seed category or symbol
        tau: MI-gate threshold [0,1]
        max_depth: Maximum BFS hops
        semantic_filter: Optional semantic filter

    Returns:
        {
            "status": "success",
            "query": str,
            "entry_token": str,
            "results": [
                {
                    "atom_id": str,
                    "mi_score": float,
                    "depth": int,
                    "semantic_metadata": dict (if semantic_filter applied)
                }
            ],
            "nodes_visited": int,
            "filtered_count": int (if semantic_filter applied)
        }

    Example:
        # Query all HTTP GET endpoints
        filter = SemanticFilter(framework='http', type='endpoint', method='GET')
        result = await cqe_query_enhanced(
            index_path=Path('.quro_context/cqe_index.db'),
            query='authentication logic',
            entry_token='quro_morph',
            semantic_filter=filter
        )
    """
    # Step 1: Perform behavioral query (existing CQE logic)
    from quro_sovereign.cqe_daemon import query_daemon

    try:
        behavioral_results = await query_daemon(
            query=query,
            entry_token=entry_token,
            tau=tau,
            max_depth=max_depth
        )
    except (FileNotFoundError, ConnectionRefusedError):
        # Daemon not running, return error
        return {
            'status': 'error',
            'error': 'CQE daemon not running. Start with: quro cqe-daemon start'
        }

    if behavioral_results.get('status') != 'success':
        return behavioral_results

    # Step 2: Apply semantic filter if provided
    if not semantic_filter:
        return behavioral_results

    filtered_results = []
    conn = sqlite3.connect(index_path)
    cursor = conn.cursor()

    for result in behavioral_results.get('results', []):
        atom_id = result['atom_id']

        # Load semantic metadata for this atom
        cursor.execute("""
            SELECT framework_id, metadata_json
            FROM semantic_metadata
            WHERE atom_id = ?
        """, (atom_id,))

        row = cursor.fetchone()
        if not row:
            # No semantic metadata, skip
            continue

        framework_id, metadata_json = row
        metadata = json.loads(metadata_json)
        metadata['framework_id'] = framework_id

        # Check if metadata matches filter
        if semantic_filter.matches(metadata):
            result['semantic_metadata'] = metadata
            filtered_results.append(result)

    conn.close()

    # Return filtered results
    return {
        'status': 'success',
        'query': query,
        'entry_token': entry_token,
        'results': filtered_results,
        'nodes_visited': behavioral_results.get('nodes_visited', 0),
        'filtered_count': len(filtered_results),
        'total_before_filter': len(behavioral_results.get('results', [])),
    }


def format_semantic_results(results: dict[str, Any]) -> str:
    """
    Format semantic query results for CLI output.

    @intent Human-readable output with semantic metadata

    Args:
        results: Result dict from cqe_query_enhanced

    Returns:
        Formatted string
    """
    if results.get('status') != 'success':
        return f"❌ Query failed: {results.get('error', 'Unknown error')}"

    lines = []
    lines.append(f"🔍 Query: {results['query']}")
    lines.append(f"📍 Entry: {results['entry_token']}")
    lines.append(f"✓ Found {results['filtered_count']} results (filtered from {results['total_before_filter']})")
    lines.append("")

    for i, result in enumerate(results['results'], 1):
        atom_id = result['atom_id']
        mi_score = result.get('mi_score', 0.0)
        depth = result.get('depth', 0)

        lines.append(f"{i}. {atom_id} (MI: {mi_score:.3f}, depth: {depth})")

        # Show semantic metadata
        semantic = result.get('semantic_metadata', {})
        if semantic:
            framework = semantic.get('framework_id', 'unknown')
            lines.append(f"   Framework: {framework}")

            endpoints = semantic.get('endpoints', [])
            for ep in endpoints[:3]:  # Show first 3 endpoints
                method = ep.get('method', 'GET')
                path = ep.get('path', '/')
                function = ep.get('function', 'unknown')
                lines.append(f"   • {method} {path} → {function}")

            if len(endpoints) > 3:
                lines.append(f"   ... and {len(endpoints) - 3} more endpoints")

        lines.append("")

    return '\n'.join(lines)
