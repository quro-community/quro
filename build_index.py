"""
Quro v3 Index Builder CLI

Scans workspace and builds symbol registry + graph database.

Usage:
    python -m quro.build_index [OPTIONS]

Examples:
    # Build index for current directory
    python -m quro.build_index

    # Build index for specific directory
    python -m quro.build_index --workspace /path/to/project

    # Rebuild (clear existing index)
    python -m quro.build_index --rebuild
"""

import argparse
import sys
import time
from pathlib import Path

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


def main():
    """CLI entry point for index builder."""
    parser = argparse.ArgumentParser(
        description="Quro v3 Index Builder - Scan workspace and build symbol registry",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build index for current directory
  python -m quro.build_index

  # Build index for specific directory
  python -m quro.build_index --workspace /path/to/project

  # Rebuild (clear existing index)
  python -m quro.build_index --rebuild

Output:
  Creates .quro_context/ directory with:
  - registry.db (symbol registry - SQLite persistent storage)
  - graph.db (graph database - SQLite persistent storage)
        """
    )

    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace root directory (default: current directory)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".quro_context/registry.db"),
        help="Output SQLite database path (default: .quro_context/registry.db)"
    )

    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear existing index and rebuild from scratch"
    )

    parser.add_argument(
        "--progress",
        action="store_true",
        default=True,
        help="Show progress messages (default: True)"
    )

    args = parser.parse_args()

    # Validate workspace
    workspace = args.workspace.resolve()
    if not workspace.exists():
        print(f"[Error] Workspace not found: {workspace}")
        return 1

    if not workspace.is_dir():
        print(f"[Error] Workspace is not a directory: {workspace}")
        return 1

    # Ensure output directory exists
    args.output.parent.mkdir(parents=True, exist_ok=True)

    print(f"[Index Builder] Workspace: {workspace}")
    print(f"[Index Builder] Output: {args.output}")
    print(f"[Index Builder] Rebuild: {args.rebuild}")
    print()

    # Create adapters
    scan_adapter = ScannerMemoryAdapter()
    registry_adapter = SQLiteRegistryAdapter(db_path=args.output)

    # Clear if rebuild
    if args.rebuild:
        print("[Index Builder] Clearing existing index...")
        registry_adapter.clear()

    # Create components
    scanner = ScannerOrchestrator(
        workspace_root=workspace,
        adapter=scan_adapter,
    )

    index_builder = IndexBuilder(
        adapter=registry_adapter,
        enrichers=[DefaultHeuristicEnricher()],
        edge_config=EdgeWeightConfig()
    )

    # Register enrichers
    _register_enrichers(index_builder, registry_adapter)

    # Scan and build index
    print("[Index Builder] Scanning workspace and building index...")
    start_time = time.time()

    try:
        # Step 1: Scan workspace
        scanner.progress_callback = print if args.progress else None
        scan_stats = scanner.scan_workspace()

        # Step 2: Build index
        symbols = scan_adapter.get_all_symbols()
        index_builder.progress_callback = print if args.progress else None
        build_stats = index_builder.build_index(symbols)

    except Exception as e:
        print(f"\n[Index Builder] Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

    duration = time.time() - start_time

    # Print summary
    print()
    print("=" * 60)
    print("Index Build Complete")
    print("=" * 60)
    print()
    print("Scan Statistics:")
    print(f"  Files discovered: {scan_stats.files_discovered}")
    print(f"  Files scanned:    {scan_stats.files_scanned}")
    print(f"  Files skipped:    {scan_stats.files_skipped}")
    print(f"  Symbols found:    {scan_stats.symbols_found}")
    print(f"  Symbols kept:     {scan_stats.symbols_kept}")
    print(f"  Symbols filtered: {scan_stats.symbols_filtered}")
    print()
    print("Index Statistics:")
    print(f"  Symbols indexed:  {build_stats.symbols_indexed}")
    print(f"  Nodes created:    {build_stats.nodes_created}")
    print(f"  Edges created:    {build_stats.edges_created}")
    print(f"  Categories:       {build_stats.categories_created}")
    print()
    print(f"Duration: {duration:.2f}s")
    print(f"Output: {args.output}")
    print()
    print("✓ Index persisted to SQLite database")
    print()
    print("Next steps:")
    print("  1. Run Phase-1 TDA: python -m quro.tda.phase1")
    print("  2. Or use MCP tools for querying")
    print()

    return 0


def _register_enrichers(index_builder, registry_adapter):
    """Register semantic enrichers."""
    from index_builder.types import EnricherSpec, TypeBoundary

    # Phase 1 enrichers
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

    # Phase 2 enrichers
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


if __name__ == "__main__":
    sys.exit(main())
