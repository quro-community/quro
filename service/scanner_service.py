"""Scanner Service

@module quro.service.scanner_service
@intent Workspace scanning and index building service.
"""

from pathlib import Path
from typing import Any, Dict

from service.base import BaseService


class ScannerService(BaseService):
    """Workspace scanning and index building service.

    Scans workspace and builds symbol registry + graph database.
    """

    def __init__(self):
        """Initialize scanner service."""
        super().__init__()

    def get_name(self) -> str:
        """Return service name."""
        return "scanner"

    def get_description(self) -> str:
        """Return service description."""
        return "Workspace scanning and index building"

    def initialize(self, workspace_root: Path) -> None:
        """Initialize service with workspace.

        Args:
            workspace_root: Path to workspace root directory

        Raises:
            ValueError: If workspace is invalid
        """
        if not workspace_root.exists():
            raise ValueError(f"Workspace not found: {workspace_root}")

        if not workspace_root.is_dir():
            raise ValueError(f"Workspace is not a directory: {workspace_root}")

        self._workspace_root = workspace_root
        self._initialized = True

    def get_capabilities(self) -> Dict[str, Any]:
        """Return service capabilities."""
        return {
            "name": self.get_name(),
            "description": self.get_description(),
            "methods": [
                "scan_workspace",
                "get_stats",
            ],
            "initialized": self._initialized,
        }

    def scan_workspace(
        self,
        rebuild: bool = False,
        progress: bool = True,
    ) -> Dict[str, Any]:
        """Scan workspace and build index.

        Args:
            rebuild: Clear existing index and rebuild (default: False)
            progress: Show progress messages (default: True)

        Returns:
            Scan and build statistics

        Raises:
            RuntimeError: If service not initialized or scan fails
        """
        self._ensure_initialized()

        from scanner.orchestrator import ScannerOrchestrator
        from scanner.adapters.memory import MemoryAdapter as ScannerMemoryAdapter
        from index_builder import IndexBuilder
        from index_builder.adapters import SQLiteRegistryAdapter
        from index_builder.types import EdgeWeightConfig
        from index_builder.providers.default_enricher import DefaultHeuristicEnricher
        from index_builder.enrichers import (
            HubPressureEnricher,
            PathEntropyEnricher,
            RoleEnricher,
            IntentEnricher,
        )
        from index_builder.types import EnricherSpec, TypeBoundary

        # Ensure output directory exists
        output_path = self._workspace_root / ".quro_context" / "registry.db"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Create adapters
        scan_adapter = ScannerMemoryAdapter()
        registry_adapter = SQLiteRegistryAdapter(db_path=output_path)

        # Clear if rebuild
        if rebuild:
            registry_adapter.clear()

        # Create components
        scanner = ScannerOrchestrator(
            workspace_root=self._workspace_root,
            adapter=scan_adapter,
        )

        index_builder = IndexBuilder(
            adapter=registry_adapter,
            enrichers=[DefaultHeuristicEnricher()],
            edge_config=EdgeWeightConfig(),
        )

        # Register enrichers
        symbol_registry = {}
        path_enricher = PathEntropyEnricher(symbol_registry, collision_threshold=1)
        index_builder.register_enricher(
            enricher=path_enricher,
            priority=10,
            spec=EnricherSpec(
                name="PathEntropyEnricher",
                input_boundary=TypeBoundary(),
                output_boundary=TypeBoundary(),
                description="Detect ambiguous symbols (name collisions, wildcard imports)",
            ),
        )

        hub_enricher = HubPressureEnricher(
            registry=registry_adapter,
            fanout_threshold=50,
        )
        index_builder.register_enricher(
            enricher=hub_enricher,
            priority=100,
            spec=EnricherSpec(
                name="HubPressureEnricher",
                input_boundary=TypeBoundary(),
                output_boundary=TypeBoundary(),
                description="Detect high-fanout hubs (>50 edges) for CQE pruning",
            ),
        )

        role_enricher = RoleEnricher(confidence_threshold=0.3)
        index_builder.register_enricher(
            enricher=role_enricher,
            priority=20,
            spec=EnricherSpec(
                name="RoleEnricher",
                input_boundary=TypeBoundary(),
                output_boundary=TypeBoundary(),
                description="Detect architectural roles (controller, worker, adapter, etc.)",
            ),
        )

        intent_enricher = IntentEnricher(confidence_threshold=0.3)
        index_builder.register_enricher(
            enricher=intent_enricher,
            priority=21,
            spec=EnricherSpec(
                name="IntentEnricher",
                input_boundary=TypeBoundary(),
                output_boundary=TypeBoundary(),
                description="Detect semantic intent (io, network, database, test, etc.)",
            ),
        )

        # Scan and build index
        try:
            scanner.progress_callback = print if progress else None
            scan_stats = scanner.scan_workspace()

            symbols = scan_adapter.get_all_symbols()
            index_builder.progress_callback = print if progress else None
            build_stats = index_builder.build_index(symbols)

        except Exception as e:
            raise RuntimeError(f"Scan failed: {e}") from e

        return {
            "scan": {
                "files_discovered": scan_stats.files_discovered,
                "files_scanned": scan_stats.files_scanned,
                "files_skipped": scan_stats.files_skipped,
                "symbols_found": scan_stats.symbols_found,
                "symbols_kept": scan_stats.symbols_kept,
                "symbols_filtered": scan_stats.symbols_filtered,
            },
            "index": {
                "symbols_indexed": build_stats.symbols_indexed,
                "nodes_created": build_stats.nodes_created,
                "edges_created": build_stats.edges_created,
                "categories_created": build_stats.categories_created,
            },
            "output": str(output_path),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get scanner statistics.

        Returns:
            Statistics about indexed data

        Raises:
            RuntimeError: If service not initialized or index not found
        """
        self._ensure_initialized()

        from index_builder.adapters import SQLiteRegistryAdapter

        output_path = self._workspace_root / ".quro_context" / "registry.db"

        if not output_path.exists():
            raise RuntimeError(
                f"Index not found at {output_path}. "
                f"Run scan_workspace() first."
            )

        registry_adapter = SQLiteRegistryAdapter(db_path=output_path)

        # Get basic stats
        symbols = registry_adapter.list_symbols(limit=10000)
        categories = registry_adapter.list_categories()

        return {
            "symbols_count": len(symbols),
            "categories_count": len(categories),
            "index_path": str(output_path),
        }
