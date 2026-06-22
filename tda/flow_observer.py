"""
Flow Observer - Captures data shape transformations through TDA pipeline.

Minimal MVP for observing data flow through:
  Phase 2 → Phase 3 Pass 1 → Pass 2 → Pass 3 → Pass 4
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import json
from pathlib import Path
from datetime import datetime


@dataclass(frozen=True)
class DataSnapshot:
    """Immutable snapshot of data at a pipeline stage."""

    stage: str
    timestamp: str
    symbol: str
    shape: Dict[str, Any]  # Type, size, key fields
    sample_data: Optional[Dict[str, Any]] = None  # Small sample for inspection


@dataclass
class FlowTrace:
    """Trace of data flow through pipeline for a single symbol."""

    symbol: str
    snapshots: List[DataSnapshot] = field(default_factory=list)

    def add_snapshot(self, snapshot: DataSnapshot) -> None:
        """Add snapshot to trace."""
        self.snapshots.append(snapshot)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "snapshots": [
                {
                    "stage": s.stage,
                    "timestamp": s.timestamp,
                    "shape": s.shape,
                    "sample_data": s.sample_data,
                }
                for s in self.snapshots
            ],
        }


class FlowObserver:
    """Observes and logs data shape transformations."""

    def __init__(self, output_dir: str = ".quro_context/flow_traces"):
        """Initialize observer.

        Args:
            output_dir: Directory to write trace files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.traces: Dict[str, FlowTrace] = {}

    def observe_phase2_output(
        self,
        symbol: str,
        sms: Any,  # SymbolManifoldState
    ) -> None:
        """Observe Phase 2 output (SymbolManifoldState).

        Args:
            symbol: Symbol ID
            sms: SymbolManifoldState object
        """
        shape = {
            "type": "SymbolManifoldState",
            "fields": {
                "symbol": "str",
                "percentiles": f"dict[{len(sms.percentiles)} keys]",
                "category_coupling": f"dict[{len(sms.category_coupling)} categories]",
                "temporal_signature": "TemporalSignature",
                "cognitive_mass": "float",
            },
        }

        sample_data = {
            "symbol": sms.symbol,
            "cognitive_mass": sms.cognitive_mass,
            "frequency": sms.temporal_signature.frequency,
            "top_categories": list(sms.category_coupling.keys())[:3],
        }

        snapshot = DataSnapshot(
            stage="phase2_output",
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            shape=shape,
            sample_data=sample_data,
        )

        self._add_snapshot(symbol, snapshot)

    def observe_pass1_output(
        self,
        symbol: str,
        cognitive_role: Any,  # CognitiveRole
    ) -> None:
        """Observe Pass 1 output (CognitiveRole).

        Args:
            symbol: Symbol ID
            cognitive_role: CognitiveRole object
        """
        shape = {
            "type": "CognitiveRole",
            "fields": {
                "type": "str",
                "query_bias": "str",
                "action_implication": "str",
            },
        }

        sample_data = {
            "type": cognitive_role.type,
            "query_bias": cognitive_role.query_bias,
            "action_implication": cognitive_role.action_implication,
        }

        snapshot = DataSnapshot(
            stage="pass1_cognitive_role",
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            shape=shape,
            sample_data=sample_data,
        )

        self._add_snapshot(symbol, snapshot)

    def observe_pass2_output(
        self,
        symbol: str,
        stability: Any,  # StabilityAssessment
    ) -> None:
        """Observe Pass 2 output (StabilityAssessment).

        Args:
            symbol: Symbol ID
            stability: StabilityAssessment object
        """
        shape = {
            "type": "StabilityAssessment",
            "fields": {
                "stability_class": "str",
                "mutation_risk": "str",
                "refactor_sensitivity": "float",
                "change_impact_radius": "str",
            },
        }

        sample_data = {
            "stability_class": stability.stability_class,
            "mutation_risk": stability.mutation_risk,
            "refactor_sensitivity": stability.refactor_sensitivity,
            "change_impact_radius": stability.change_impact_radius,
        }

        snapshot = DataSnapshot(
            stage="pass2_stability",
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            shape=shape,
            sample_data=sample_data,
        )

        self._add_snapshot(symbol, snapshot)

    def observe_pass3_output(
        self,
        symbol: str,
        affordances: List[str],
        attention_weight: float,
    ) -> None:
        """Observe Pass 3 output (Affordances + Attention).

        Args:
            symbol: Symbol ID
            affordances: List of affordance tags
            attention_weight: Attention weight
        """
        shape = {
            "type": "Pass3Output",
            "fields": {
                "affordances": f"List[str] ({len(affordances)} items)",
                "attention_weight": "float",
            },
        }

        sample_data = {
            "affordances": affordances,
            "attention_weight": attention_weight,
        }

        snapshot = DataSnapshot(
            stage="pass3_affordances",
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            shape=shape,
            sample_data=sample_data,
        )

        self._add_snapshot(symbol, snapshot)

    def observe_pass4_output(
        self,
        symbol: str,
        context: Any,  # CognitiveSymbolContext
    ) -> None:
        """Observe Pass 4 output (CognitiveSymbolContext).

        Args:
            symbol: Symbol ID
            context: CognitiveSymbolContext object
        """
        shape = {
            "type": "CognitiveSymbolContext",
            "fields": {
                "symbol": "str",
                "cognitive_role": "CognitiveRole",
                "stability": "StabilityAssessment",
                "affordances": f"List[str] ({len(context.affordances)} items)",
                "attention_weight": "float",
                "llm_context_block": "LLMContextBlock",
                "percentile_ranks": f"dict[{len(context.percentile_ranks)} keys]",
            },
        }

        sample_data = {
            "symbol": context.symbol,
            "cognitive_role_type": context.cognitive_role.type,
            "stability_class": context.stability.stability_class,
            "attention_weight": context.attention_weight,
            "summary": context.llm_context_block.summary,
            "hints_count": len(context.llm_context_block.hints),
        }

        snapshot = DataSnapshot(
            stage="pass4_final_context",
            timestamp=datetime.now().isoformat(),
            symbol=symbol,
            shape=shape,
            sample_data=sample_data,
        )

        self._add_snapshot(symbol, snapshot)

    def _add_snapshot(self, symbol: str, snapshot: DataSnapshot) -> None:
        """Add snapshot to trace for symbol."""
        if symbol not in self.traces:
            self.traces[symbol] = FlowTrace(symbol=symbol)
        self.traces[symbol].add_snapshot(snapshot)

    def write_trace(self, symbol: str) -> Path:
        """Write trace for symbol to file.

        Args:
            symbol: Symbol ID

        Returns:
            Path to written trace file
        """
        if symbol not in self.traces:
            raise ValueError(f"No trace found for symbol: {symbol}")

        trace = self.traces[symbol]
        safe_symbol = symbol.replace("sym::", "").replace("/", "_")
        output_path = self.output_dir / f"{safe_symbol}.json"

        with open(output_path, "w") as f:
            json.dump(trace.to_dict(), f, indent=2)

        return output_path

    def write_all_traces(self) -> List[Path]:
        """Write all traces to files.

        Returns:
            List of paths to written trace files
        """
        return [self.write_trace(symbol) for symbol in self.traces.keys()]

    def get_trace(self, symbol: str) -> Optional[FlowTrace]:
        """Get trace for symbol.

        Args:
            symbol: Symbol ID

        Returns:
            FlowTrace if exists, None otherwise
        """
        return self.traces.get(symbol)

    def print_trace_summary(self, symbol: str) -> None:
        """Print summary of trace for symbol.

        Args:
            symbol: Symbol ID
        """
        trace = self.get_trace(symbol)
        if not trace:
            print(f"No trace found for: {symbol}")
            return

        print(f"\n=== Flow Trace: {symbol} ===")
        print(f"Stages captured: {len(trace.snapshots)}")
        print()

        for snapshot in trace.snapshots:
            print(f"[{snapshot.stage}]")
            print(f"  Type: {snapshot.shape['type']}")
            print(f"  Fields: {snapshot.shape['fields']}")
            if snapshot.sample_data:
                print(f"  Sample: {json.dumps(snapshot.sample_data, indent=4)}")
            print()
