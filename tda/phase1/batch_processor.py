"""
Phase-1 offline batch processor for full graph traversal.
"""

import json
from collections import deque
from pathlib import Path
from typing import Optional, Set, List
from tqdm import tqdm

from tda.phase1.event_logger import GraphEventLogger
from index_builder.adapters import SQLiteRegistryAdapter


class Phase1BatchProcessor:
    """
    Offline batch processor for full graph traversal.

    Iterates through ALL symbols in the registry and performs graph traversal
    for each, logging atomic events to JSONL.

    Optionally writes to DuckDB when duckdb_writer is provided.
    """

    def __init__(
        self,
        registry_db: Path,
        output_path: Optional[Path] = None,
        tau: float = 0.05,
        max_depth: int = 3,
        duckdb_writer = None,
    ):
        """
        Initialize batch processor.

        Args:
            registry_db: Path to symbol registry database (SQLite)
            output_path: Optional path to output JSONL file
            tau: MI-gate threshold (default: 0.05)
            max_depth: Maximum BFS depth (default: 3)
            duckdb_writer: Optional DuckDBEventWriter for DuckDB writes
        """
        self.registry_db = registry_db
        self.output_path = output_path
        self.tau = tau
        self.max_depth = max_depth
        self.duckdb_writer = duckdb_writer

        # Initialize event logger (JSONL optional, DuckDB optional)
        self.event_logger = GraphEventLogger(output_path, duckdb_writer=duckdb_writer)

        # Lazy-loaded components (initialized in run_full_traversal)
        self.registry = None

    async def run_full_traversal(self, incremental: bool = False):
        """
        Run offline traversal for ALL symbols.

        Args:
            incremental: Skip symbols already processed
        """
        # Initialize registry adapter
        self.registry = SQLiteRegistryAdapter(self.registry_db)

        # Load all symbols
        all_symbols = await self._load_all_symbols()
        print(f"[Phase-1] Loaded {len(all_symbols)} symbols from registry")

        # Filter if incremental
        if incremental:
            processed = self._load_processed_symbols()
            all_symbols = [s for s in all_symbols if s not in processed]
            print(f"[Phase-1] Incremental mode: {len(all_symbols)} symbols remaining")

        if len(all_symbols) == 0:
            print("[Phase-1] No symbols to process")
            return

        # Process each symbol
        total_events = 0
        for idx, symbol in enumerate(tqdm(all_symbols, desc="Processing symbols")):
            try:
                events = await self._traverse_symbol(symbol)
                total_events += events
            except Exception as e:
                print(f"\n[Phase-1] Error processing {symbol}: {e}")
                continue

            # Checkpoint every 100 symbols
            if (idx + 1) % 100 == 0:
                print(f"\n[Phase-1] Checkpoint: {idx + 1}/{len(all_symbols)} symbols, {total_events} events")

        print(f"\n[Phase-1] Complete: {len(all_symbols)} symbols processed")
        print(f"[Phase-1] Events written: {total_events}")

    async def _load_all_symbols(self) -> List[str]:
        """
        Load all symbols from registry.

        Returns:
            List of symbol IDs
        """
        all_nodes = self.registry.get_all_nodes()
        # Filter to only symbol nodes (not categories)
        symbols = [node.id for node in all_nodes if node.type == "symbol"]
        return symbols

    async def _traverse_symbol(self, symbol: str) -> int:
        """
        Traverse graph starting from this symbol.

        Args:
            symbol: Starting symbol ID

        Returns:
            Number of events logged
        """
        # Start query observation
        query_id = self.event_logger.start_query({
            "start": symbol,
            "target": None,  # Full traversal, no specific target
            "tau": self.tau,
            "max_depth": self.max_depth,
            "mode": "offline_batch"
        })

        event_count = 1  # Count the query metadata event

        # BFS traversal
        visited: Set[str] = set()
        queue = deque([(symbol, 0, None, None)])  # (node, depth, predecessor, edge_type)

        while queue:
            node_id, depth, pred, edge_type = queue.popleft()

            if node_id in visited or depth > self.max_depth:
                continue

            # Get node info from registry
            try:
                node_info = await self._get_node_info(node_id)
            except Exception:
                # Symbol not found in registry, skip
                continue

            # Log node visit
            self.event_logger.log_node_visit(
                node_id=node_id,
                kind=node_info.get("kind", "unknown"),
                file_path=node_info.get("file_path", ""),
                line_number=node_info.get("line_number", 0),
                signature=node_info.get("signature"),
                depth=depth,
                predecessor=pred,
                via_edge_type=edge_type
            )
            event_count += 1

            visited.add(node_id)

            # Get neighbors from graph
            neighbors = await self._get_neighbors(node_id)

            for neighbor in neighbors:
                # Check MI gate
                passed_gate = neighbor["weight"] >= self.tau

                # Log edge traverse
                self.event_logger.log_edge_traverse(
                    src=node_id,
                    dst=neighbor["id"],
                    edge_type=neighbor["edge_type"],
                    weight=neighbor["weight"],
                    direction="outbound",
                    depth=depth,
                    tau_threshold=self.tau,
                    passed_gate=passed_gate
                )
                event_count += 1

                if passed_gate and neighbor["id"] not in visited:
                    queue.append((
                        neighbor["id"],
                        depth + 1,
                        node_id,
                        neighbor["edge_type"]
                    ))

        return event_count

    async def _get_node_info(self, node_id: str) -> dict:
        """
        Get node information from registry.

        Args:
            node_id: Symbol ID

        Returns:
            Node info dict
        """
        node = self.registry.get_node(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        return {
            "kind": node.metadata.get("kind", "unknown"),
            "file_path": node.metadata.get("file_path", ""),
            "line_number": node.metadata.get("line", 0),
            "signature": node.metadata.get("signature")
        }

    async def _get_neighbors(self, node_id: str) -> List[dict]:
        """
        Get neighbors from graph.

        Args:
            node_id: Symbol ID

        Returns:
            List of neighbor dicts with 'id', 'edge_type', 'weight'
        """
        edges = self.registry.get_edges_from(node_id)

        return [
            {
                "id": edge.dst,
                "edge_type": edge.kind,
                "weight": edge.weight
            }
            for edge in edges
        ]

    def _load_processed_symbols(self) -> Set[str]:
        """
        Load set of already-processed symbols from event log.

        Returns:
            Set of processed symbol IDs
        """
        processed: Set[str] = set()

        if self.output_path is None or not self.output_path.exists():
            return processed

        try:
            with open(self.output_path, 'r') as f:
                for line in f:
                    if '"record_type"' in line and '"QUERY_METADATA"' in line:
                        try:
                            event = json.loads(line)
                            if event.get("record_type") == "QUERY_METADATA":
                                start_symbol = event["query_params"]["start"]
                                processed.add(start_symbol)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"[Phase-1] Warning: Could not load processed symbols: {e}")

        return processed
