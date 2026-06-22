"""CQE Flow Observer - Pipeline tracing and diagnostics.

@module quro.core.cqe.flow_observer
@intent Trace data shape at each CQE pipeline stage for debugging
@constraint Minimal overhead when disabled
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
import json


@dataclass
class FlowSnapshot:
    """Snapshot of data at a pipeline stage."""
    stage: str
    timestamp: float
    data_shape: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FlowTrace:
    """Complete trace of a CQE query through the pipeline."""
    query_id: str
    start_time: float
    snapshots: List[FlowSnapshot] = field(default_factory=list)

    def add_snapshot(self, stage: str, data: Any, metadata: Optional[Dict[str, Any]] = None):
        """Add a snapshot at a pipeline stage.

        Args:
            stage: Stage name (e.g., "kernel_output", "refiner_input", "alias_fetch")
            data: Data at this stage
            metadata: Optional metadata about this stage
        """
        snapshot = FlowSnapshot(
            stage=stage,
            timestamp=datetime.now().timestamp(),
            data_shape=self._extract_shape(data),
            metadata=metadata or {}
        )
        self.snapshots.append(snapshot)

    def _extract_shape(self, data: Any) -> Dict[str, Any]:
        """Extract data shape without full content (for performance)."""
        if isinstance(data, dict):
            return {
                "type": "dict",
                "keys": list(data.keys()),
                "size": len(data),
                "sample": {k: type(v).__name__ for k, v in list(data.items())[:3]}
            }
        elif isinstance(data, list):
            return {
                "type": "list",
                "length": len(data),
                "sample_types": [type(item).__name__ for item in data[:3]]
            }
        elif hasattr(data, "__dict__"):
            return {
                "type": type(data).__name__,
                "fields": list(data.__dict__.keys())
            }
        else:
            return {
                "type": type(data).__name__,
                "value": str(data)[:100]
            }

    def to_dict(self) -> Dict[str, Any]:
        """Convert trace to dict for serialization."""
        return {
            "query_id": self.query_id,
            "start_time": self.start_time,
            "duration_ms": (self.snapshots[-1].timestamp - self.start_time) * 1000 if self.snapshots else 0,
            "stages": [
                {
                    "stage": s.stage,
                    "timestamp": s.timestamp,
                    "elapsed_ms": (s.timestamp - self.start_time) * 1000,
                    "data_shape": s.data_shape,
                    "metadata": s.metadata
                }
                for s in self.snapshots
            ]
        }


class FlowObserver:
    """Observer for CQE query pipeline flow.

    Traces data shape at each stage:
    1. Query input (start, tau, max_depth)
    2. Graph transform (HubNormalizer, TopKPruner)
    3. Kernel output (max_weights, predecessors)
    4. Refiner input (CQEResult)
    5. Alias fetch (per-node)
    6. Refiner output (CQERefinedResult)
    7. Final output (dict)
    """

    def __init__(self, enabled: bool = False):
        """Initialize observer.

        Args:
            enabled: Whether to enable tracing (default: False for performance)
        """
        self.enabled = enabled
        self.traces: Dict[str, FlowTrace] = {}

    def start_trace(self, query_id: str, query_params: Dict[str, Any]) -> Optional[FlowTrace]:
        """Start a new trace.

        Args:
            query_id: Unique query identifier
            query_params: Query parameters (start, tau, max_depth, etc.)

        Returns:
            FlowTrace if enabled, None otherwise
        """
        if not self.enabled:
            return None

        trace = FlowTrace(
            query_id=query_id,
            start_time=datetime.now().timestamp()
        )
        trace.add_snapshot("query_input", query_params)
        self.traces[query_id] = trace
        return trace

    def observe(self, query_id: str, stage: str, data: Any, metadata: Optional[Dict[str, Any]] = None):
        """Observe data at a pipeline stage.

        Args:
            query_id: Query identifier
            stage: Stage name
            data: Data at this stage
            metadata: Optional metadata
        """
        if not self.enabled:
            return

        trace = self.traces.get(query_id)
        if trace:
            trace.add_snapshot(stage, data, metadata)

    def get_trace(self, query_id: str) -> Optional[Dict[str, Any]]:
        """Get trace for a query.

        Args:
            query_id: Query identifier

        Returns:
            Trace dict if found, None otherwise
        """
        trace = self.traces.get(query_id)
        return trace.to_dict() if trace else None

    def clear_trace(self, query_id: str):
        """Clear a trace from memory.

        Args:
            query_id: Query identifier
        """
        self.traces.pop(query_id, None)

    def get_all_traces(self) -> List[Dict[str, Any]]:
        """Get all traces.

        Returns:
            List of trace dicts
        """
        return [trace.to_dict() for trace in self.traces.values()]

    def clear_all(self):
        """Clear all traces."""
        self.traces.clear()
