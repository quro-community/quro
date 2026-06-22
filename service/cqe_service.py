"""CQE Service

@module quro.service.cqe_service
@intent CQE query and graph navigation service.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from service.base import BaseService
from quro_mcp.service import QuroV3Service


class CQEService(BaseService):
    """CQE query and graph navigation service.

    Provides semantic query capabilities over the indexed codebase graph.
    """

    def __init__(self):
        """Initialize CQE service."""
        super().__init__()
        self._quro_service: Optional[QuroV3Service] = None

    def get_name(self) -> str:
        """Return service name."""
        return "cqe"

    def get_description(self) -> str:
        """Return service description."""
        return "CQE semantic query and graph navigation"

    def initialize(self, workspace_root: Path) -> None:
        """Initialize service with workspace.

        Args:
            workspace_root: Path to workspace root directory

        Raises:
            ValueError: If workspace is invalid
            RuntimeError: If initialization fails
        """
        if not workspace_root.exists():
            raise ValueError(f"Workspace not found: {workspace_root}")

        if not workspace_root.is_dir():
            raise ValueError(f"Workspace is not a directory: {workspace_root}")

        # Check for index
        index_path = workspace_root / ".quro_context" / "registry.db"
        if not index_path.exists():
            raise RuntimeError(
                f"Index not found at {index_path}. "
                f"Run 'quro scan' first to build the index."
            )

        # Initialize QuroV3Service
        try:
            self._quro_service = QuroV3Service(workspace_root=workspace_root)
            self._workspace_root = workspace_root
            self._initialized = True
        except Exception as e:
            raise RuntimeError(f"Failed to initialize CQE service: {e}") from e

    def get_capabilities(self) -> Dict[str, Any]:
        """Return service capabilities."""
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "methods": [
                "query",
                "query_multi_tier",
                "query_with_mode",
                "get_symbol",
                "get_category",
                "list_symbols",
                "list_categories",
                "get_stats",
            ],
            "initialized": self._initialized,
        }

    def query(
        self,
        start: str,
        tau: float = 0.05,
        max_depth: int = 3,
        use_semantic_refiner: bool = True,
    ) -> Dict[str, Any]:
        """Execute CQE semantic query.

        Args:
            start: Starting node ID (e.g., 'sym::LockManager' or 'cat::async')
            tau: MI-gate threshold [0, 1] (default: 0.05)
            max_depth: Maximum traversal depth (default: 3)
            use_semantic_refiner: Use semantic refiner (default: True)

        Returns:
            Query results with related symbols and categories

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()
        return self._quro_service.cqe_query(
            start=start,
            tau=tau,
            max_depth=max_depth,
            use_semantic_refiner=use_semantic_refiner,
        )

    def query_multi_tier(
        self,
        start: str,
        max_depth: int = 3,
        use_semantic_refiner: bool = True,
    ) -> Dict[str, Any]:
        """Execute multi-tier CQE query.

        Queries at multiple tau levels (0.3, 0.1, 0.05) for tiered results.

        Args:
            start: Starting node ID
            max_depth: Maximum traversal depth (default: 3)
            use_semantic_refiner: Use semantic refiner (default: True)

        Returns:
            Tiered query results (core/extended/exploratory)

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()
        return self._quro_service.cqe_query_multi_tier(
            start=start,
            max_depth=max_depth,
            use_semantic_refiner=use_semantic_refiner,
        )

    def query_with_mode(
        self,
        start: str,
        tau: float = 0.05,
        max_depth: int = 3,
        use_semantic_refiner: bool = True,
        traversal_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute CQE query with traversal mode.

        Args:
            start: Starting node ID
            tau: MI-gate threshold (default: 0.05)
            max_depth: Maximum traversal depth (default: 3)
            use_semantic_refiner: Use semantic refiner (default: True)
            traversal_mode: Force specific mode (forward/reverse/field_guided/saddle_escape)

        Returns:
            Query results with mode information

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()
        return self._quro_service.cqe_query_with_mode(
            start=start,
            tau=tau,
            max_depth=max_depth,
            use_semantic_refiner=use_semantic_refiner,
            traversal_mode=traversal_mode,
        )

    def get_symbol(self, symbol_name: str) -> Optional[Dict[str, Any]]:
        """Get symbol details.

        Args:
            symbol_name: Symbol name (without 'sym::' prefix)

        Returns:
            Symbol details or None if not found

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()
        return self._quro_service.get_symbol(symbol_name)

    def get_category(self, category_name: str) -> Optional[Dict[str, Any]]:
        """Get category details.

        Args:
            category_name: Category name (without 'cat::' prefix)

        Returns:
            Category details or None if not found

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()
        return self._quro_service.get_category(category_name)

    def list_symbols(self, limit: int = 100) -> List[str]:
        """List all symbols.

        Args:
            limit: Maximum number of symbols to return (default: 100)

        Returns:
            List of symbol names

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()
        return self._quro_service.list_symbols(limit=limit)

    def list_categories(self) -> List[str]:
        """List all categories.

        Returns:
            List of category names

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()
        return self._quro_service.list_categories()

    def get_stats(self) -> Dict[str, Any]:
        """Get service statistics.

        Returns:
            Statistics about indexed symbols, nodes, edges, etc.

        Raises:
            RuntimeError: If service not initialized
        """
        self._ensure_initialized()
        return self._quro_service.get_stats()
