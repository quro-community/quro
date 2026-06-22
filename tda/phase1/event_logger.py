"""
Graph event logger for Phase-1 observation recording.
"""

import json
import uuid
import time
from pathlib import Path
from typing import Optional

from tda.phase1.schema import (
    NodeVisitEvent,
    EdgeTraverseEvent,
    PathCompleteEvent,
    QueryMetadata,
    NodeInfo,
    VisitContext,
    EdgeInfo,
    TraverseContext,
    PathInfo,
    PathContext,
    PathEdge,
    QueryParams,
    ExecutionStats,
)


class GraphEventLogger:
    """
    Phase-1 pure observation logger.

    Records atomic graph traversal events to the configured backend.
    When output_path is provided, writes to JSONL.
    When duckdb_writer is provided, writes to DuckDB.
    At least one backend must be configured.
    """

    def __init__(self, output_path: Optional[Path] = None, duckdb_writer = None):
        """
        Initialize event logger.

        Args:
            output_path: Optional path to output JSONL file
            duckdb_writer: Optional DuckDBEventWriter for DuckDB writes
        """
        self.output_path = output_path
        self.current_query_id: Optional[str] = None
        self.duckdb_writer = duckdb_writer

        # Ensure output directory exists if JSONL backend is used
        if self.output_path is not None:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)

    def start_query(self, query_params: dict) -> str:
        """
        Start a new query observation session.

        Args:
            query_params: Query parameters dict

        Returns:
            query_id: Unique query ID
        """
        query_id = str(uuid.uuid4())
        self.current_query_id = query_id

        # Create query metadata record
        metadata = QueryMetadata(
            query_id=query_id,
            timestamp=self._get_timestamp(),
            query_params=QueryParams(**query_params),
            execution_stats=ExecutionStats()
        )

        self._append_event(metadata.model_dump())

        return query_id

    def log_node_visit(
        self,
        node_id: str,
        kind: str,
        file_path: str,
        line_number: int,
        signature: Optional[str],
        depth: int,
        predecessor: Optional[str],
        via_edge_type: Optional[str]
    ):
        """
        Log a node visit event.

        Args:
            node_id: Canonical symbol ID
            kind: Symbol type (function/class/method)
            file_path: Source file path
            line_number: Line number in source
            signature: Function/method signature (optional)
            depth: BFS depth when visited
            predecessor: Node ID that led to this visit (optional)
            via_edge_type: Edge type traversed to reach here (optional)
        """
        event = NodeVisitEvent(
            event_id=str(uuid.uuid4()),
            timestamp=self._get_timestamp(),
            query_id=self.current_query_id,
            node=NodeInfo(
                id=node_id,
                kind=kind,
                file_path=file_path,
                line_number=line_number,
                signature=signature
            ),
            visit_context=VisitContext(
                depth=depth,
                predecessor=predecessor,
                via_edge_type=via_edge_type
            )
        )

        self._append_event(event.model_dump())

    def log_edge_traverse(
        self,
        src: str,
        dst: str,
        edge_type: str,
        weight: float,
        direction: str,
        depth: int,
        tau_threshold: float,
        passed_gate: bool
    ):
        """
        Log an edge traversal event.

        Args:
            src: Source node ID
            dst: Destination node ID
            edge_type: Edge type (CALL/IMPORT/CATEGORY/etc.)
            weight: Edge weight (MI or semantic score)
            direction: Edge direction (outbound/inbound)
            depth: BFS depth when traversed
            tau_threshold: MI-gate threshold for this query
            passed_gate: Whether edge passed MI gate
        """
        event = EdgeTraverseEvent(
            event_id=str(uuid.uuid4()),
            timestamp=self._get_timestamp(),
            query_id=self.current_query_id,
            edge=EdgeInfo(
                src=src,
                dst=dst,
                edge_type=edge_type,
                weight=weight,
                direction=direction
            ),
            traverse_context=TraverseContext(
                depth=depth,
                tau_threshold=tau_threshold,
                passed_gate=passed_gate
            )
        )

        self._append_event(event.model_dump())

    def log_path_complete(
        self,
        nodes: list[str],
        edges: list[dict],
        entry_point: str,
        target: str,
        is_shortest: bool
    ):
        """
        Log a complete path.

        Args:
            nodes: Ordered list of node IDs in path
            edges: Ordered list of edges (dicts with 'type' and 'weight')
            entry_point: Query start node
            target: Query target node
            is_shortest: Whether this is a shortest path
        """
        event = PathCompleteEvent(
            event_id=str(uuid.uuid4()),
            timestamp=self._get_timestamp(),
            query_id=self.current_query_id,
            path=PathInfo(
                nodes=nodes,
                edges=[PathEdge(**e) for e in edges],
                total_length=len(edges)
            ),
            path_context=PathContext(
                entry_point=entry_point,
                target=target,
                is_shortest=is_shortest
            )
        )

        self._append_event(event.model_dump())

    def _get_timestamp(self) -> int:
        """Get current timestamp in microseconds."""
        return int(time.time() * 1e6)

    def _append_event(self, event: dict):
        """
        Append event to the configured backend(s).

        Args:
            event: Event dict to append
        """
        if self.output_path is not None:
            with open(self.output_path, 'a') as f:
                f.write(json.dumps(event) + '\n')

        if self.duckdb_writer is not None:
            self.duckdb_writer.write_event(event)
