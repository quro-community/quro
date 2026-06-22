"""
Graph Adapter Factory - Creates GraphInterface from available sources.

Priority order:
1. adjacency_cache.pkl (Phase 2 output) - FASTEST
2. field_data_cache.pkl (Phase 4 output)
3. manifold_states.jsonl (contains in_neighbors/out_neighbors)
4. SQLite registry.db
5. graph_events.jsonl (slow fallback)
"""

import logging
from pathlib import Path
from typing import Optional, List

from ..interfaces.graph import GraphInterface
from .file_graph import (
    FileGraphAdapter,
    FieldDataGraphAdapter,
    MemoryGraphAdapter,
    StreamingGraphAdapter,
)

logger = logging.getLogger(__name__)


class GraphAdapter:
    """Factory for creating GraphInterface implementations.

    Usage:
        # Automatic detection (uses best available source)
        graph = GraphAdapter.create(field_data_path)

        # Force specific source
        graph = GraphAdapter.create(field_data_path, preferred_source="sqlite")

    Sources:
        - "cache": adjacency_cache.pkl (Phase 2)
        - "field_cache": field_data_cache.pkl (Phase 4)
        - "sqlite": registry.db
        - "jsonl": graph_events.jsonl (slow)
        - "memory": in-memory (empty, for testing)
    """

    _SOURCE_PRIORITY = [
        "cache",      # adjacency_cache.pkl
        "field_cache", # field_data_cache.pkl
        "sqlite",     # registry.db
        "jsonl",      # graph_events.jsonl
    ]

    @staticmethod
    def create(
        field_data_path: Path,
        preferred_source: Optional[str] = None,
    ) -> GraphInterface:
        """Create a GraphInterface with automatic source detection.

        Args:
            field_data_path: Path to .quro_context/tda/
            preferred_source: Force specific source ("cache", "sqlite", "jsonl")

        Returns:
            GraphInterface implementation

        Raises:
            FileNotFoundError: If no graph source is available
        """
        field_data_path = Path(field_data_path)

        if preferred_source == "memory":
            logger.debug("Creating in-memory graph adapter")
            return MemoryGraphAdapter()

        if preferred_source in (None, "cache", "auto"):
            cache_path = field_data_path / "adjacency_cache.pkl"
            if cache_path.exists():
                logger.info("Using adjacency_cache.pkl (Phase 2 output)")
                return FileGraphAdapter(cache_path)

        if preferred_source in (None, "field_cache", "auto"):
            field_cache = field_data_path / "field_data_cache.pkl"
            if field_cache.exists():
                logger.info("Using field_data_cache.pkl (Phase 4 output)")
                return FieldDataGraphAdapter(field_cache)

        # Check for manifold_states.jsonl with embedded neighbors
        if preferred_source in (None, "manifold", "auto"):
            manifold_path = field_data_path / "phase2" / "manifold_states.jsonl"
            if manifold_path.exists():
                try:
                    from manifold_graph import ManifoldStatesGraphAdapter
                    logger.info("Using manifold_states.jsonl")
                    return ManifoldStatesGraphAdapter(manifold_path)
                except Exception as e:
                    logger.warning("Failed to load manifold_states: %s", e)

        if preferred_source in (None, "sqlite", "auto"):
            registry_path = field_data_path.parent / "registry.db"
            if registry_path.exists():
                logger.info("Using registry.db")
                try:
                    from sqlite_graph import SQLiteGraphAdapter
                    return SQLiteGraphAdapter(registry_path)
                except Exception as e:
                    logger.warning("Failed to load SQLite: %s", e)

        if preferred_source in (None, "jsonl", "auto"):
            events_path = field_data_path / "phase1" / "graph_events.jsonl"
            if events_path.exists():
                logger.warning(
                    "No cache found. Falling back to slow graph_events.jsonl parsing. "
                    "Run Phase 2 to create adjacency_cache.pkl for faster access."
                )
                return StreamingGraphAdapter(events_path)

        raise FileNotFoundError(
            f"No graph source found in {field_data_path}.\n"
            f"Run Phase 2 to generate adjacency_cache.pkl.\n"
            f"Expected files:\n"
            f"  - {field_data_path}/adjacency_cache.pkl\n"
            f"  - {field_data_path}/field_data_cache.pkl\n"
            f"  - {field_data_path.parent}/registry.db\n"
            f"  - {field_data_path}/phase1/graph_events.jsonl"
        )

    @staticmethod
    def create_with_fallback(
        field_data_path: Path,
        fallback_to_jsonl: bool = True,
    ) -> GraphInterface:
        """Create graph with explicit fallback control.

        Use this when you want to ensure the fastest source is used
        but handle missing caches gracefully.
        """
        try:
            return GraphAdapter.create(field_data_path)
        except FileNotFoundError as e:
            if fallback_to_jsonl:
                logger.warning("Cache not found, using JSONL fallback: %s", e)
                events_path = Path(field_data_path) / "phase1" / "graph_events.jsonl"
                if events_path.exists():
                    return StreamingGraphAdapter(events_path)
            raise

    @staticmethod
    def list_available_sources(field_data_path: Path) -> List[str]:
        """List all available graph sources in order of preference."""
        sources = []
        field_data_path = Path(field_data_path)

        checks = [
            ("cache", field_data_path / "adjacency_cache.pkl"),
            ("field_cache", field_data_path / "field_data_cache.pkl"),
            ("manifold", field_data_path / "phase2" / "manifold_states.jsonl"),
            ("sqlite", field_data_path.parent / "registry.db"),
            ("jsonl", field_data_path / "phase1" / "graph_events.jsonl"),
        ]

        for name, path in checks:
            if path.exists():
                sources.append(f"{name} ({path})")

        return sources


__all__ = ["GraphAdapter"]
