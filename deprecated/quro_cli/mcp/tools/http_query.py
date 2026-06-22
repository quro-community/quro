"""HTTP Endpoint Query Tool - Extract HTTP routes from CQE payloads.

@module quro_cli.mcp.tools.http_query
@intent Provide specialized query for HTTP endpoints by parsing payloads.
        Short-term solution until scanner extracts structured HTTP metadata.
"""

import gzip
import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class HTTPEndpointExtractor:
    """Extract HTTP endpoint information from symbol payloads."""

    # Regex patterns for common Python web frameworks
    PATTERNS = {
        'fastapi': [
            r'@app\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
            r'@router\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']',
        ],
        'flask': [
            r'@app\.route\s*\(\s*["\']([^"\']+)["\'],?\s*methods\s*=\s*\[([^\]]+)\]',
            r'@bp\.route\s*\(\s*["\']([^"\']+)["\'],?\s*methods\s*=\s*\[([^\]]+)\]',
        ],
        'django': [
            r'path\s*\(\s*["\']([^"\']+)["\'],\s*(\w+)',
        ],
    }

    def __init__(self, index_path: Path):
        self.index_path = index_path

    def extract_endpoints(self, symbol_pattern: str) -> List[Dict]:
        """
        Extract HTTP endpoints from symbols matching pattern.

        Args:
            symbol_pattern: SQL LIKE pattern (e.g., '%quro_morph%')

        Returns:
            List of endpoint dicts with method, path, function, file
        """
        conn = sqlite3.connect(self.index_path)
        cursor = conn.cursor()

        try:
            # Find matching symbols
            cursor.execute("""
                SELECT a.id, a.features_json, p.content_gzip
                FROM atoms a
                LEFT JOIN payloads p ON a.id = p.atom_id
                WHERE a.type = 'symbol'
                  AND a.id LIKE ?
                  AND p.content_gzip IS NOT NULL
            """, (symbol_pattern,))

            endpoints = []
            for atom_id, features_json, content_gzip in cursor.fetchall():
                # Decompress payload
                try:
                    content = gzip.decompress(content_gzip).decode('utf-8')
                except Exception as e:
                    logger.warning(f"Failed to decompress payload for {atom_id}: {e}")
                    continue

                # Extract endpoints
                symbol_endpoints = self._parse_content(content, atom_id)
                endpoints.extend(symbol_endpoints)

            return endpoints

        finally:
            conn.close()

    def _parse_content(self, content: str, atom_id: str) -> List[Dict]:
        """Parse content and extract HTTP endpoints."""
        endpoints = []

        # Extract file path from atom_id
        # Format: sym::path.to.module::function_name::hash
        parts = atom_id.split('::')
        if len(parts) >= 2:
            module_path = parts[1]
            function_name = parts[2] if len(parts) >= 3 else 'unknown'
        else:
            module_path = 'unknown'
            function_name = 'unknown'

        # Try FastAPI patterns
        for pattern in self.PATTERNS['fastapi']:
            for match in re.finditer(pattern, content):
                method = match.group(1).upper()
                path = match.group(2)

                # Extract docstring if present
                doc_match = re.search(
                    rf'async def {function_name}\([^)]*\):\s*"""([^"]+)"""',
                    content
                )
                summary = doc_match.group(1).strip().split('\n')[0] if doc_match else ''

                endpoints.append({
                    'method': method,
                    'path': path,
                    'function': function_name,
                    'file': module_path,
                    'summary': summary,
                    'framework': 'fastapi',
                })

        # Try Flask patterns
        for pattern in self.PATTERNS['flask']:
            for match in re.finditer(pattern, content):
                path = match.group(1)
                methods_str = match.group(2) if len(match.groups()) > 1 else 'GET'
                methods = [m.strip().strip('"\'') for m in methods_str.split(',')]

                for method in methods:
                    endpoints.append({
                        'method': method.upper(),
                        'path': path,
                        'function': function_name,
                        'file': module_path,
                        'summary': '',
                        'framework': 'flask',
                    })

        return endpoints


def query_http_endpoints(
    index_path: Path,
    symbol_pattern: str,
    output_format: str = 'text'
) -> str:
    """
    Query HTTP endpoints for symbols matching pattern.

    Args:
        index_path: Path to CQE index database
        symbol_pattern: Symbol name or pattern (e.g., 'quro_morph', '%server%')
        output_format: 'text' or 'json'

    Returns:
        Formatted output string
    """
    extractor = HTTPEndpointExtractor(index_path)

    # Convert simple name to SQL pattern
    if not symbol_pattern.startswith('%'):
        symbol_pattern = f'%{symbol_pattern}%'

    endpoints = extractor.extract_endpoints(symbol_pattern)

    if output_format == 'json':
        import json
        return json.dumps(endpoints, indent=2)

    # Text format
    if not endpoints:
        return f"❌ No HTTP endpoints found for pattern: {symbol_pattern}"

    # Group by file
    by_file: Dict[str, List[Dict]] = {}
    for ep in endpoints:
        file = ep['file']
        if file not in by_file:
            by_file[file] = []
        by_file[file].append(ep)

    lines = [f"🌐 HTTP Endpoints ({len(endpoints)} found)\n"]
    lines.append("=" * 60)

    for file, file_endpoints in sorted(by_file.items()):
        lines.append(f"\n📁 {file}")
        lines.append("-" * 60)

        for ep in sorted(file_endpoints, key=lambda x: x['path']):
            method_color = {
                'GET': '🟢',
                'POST': '🔵',
                'PUT': '🟡',
                'DELETE': '🔴',
                'PATCH': '🟠',
            }.get(ep['method'], '⚪')

            lines.append(f"  {method_color} {ep['method']:<6} {ep['path']:<30} → {ep['function']}")
            if ep['summary']:
                lines.append(f"     └─ {ep['summary']}")

    return '\n'.join(lines)
