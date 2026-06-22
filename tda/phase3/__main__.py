"""
Phase-3 Main Orchestrator

Coordinates the four-pass cognitive compilation pipeline.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

from ..phase2.schema import SymbolManifoldState
from .pass1_role_interpreter import RoleInterpreter
from .pass2_risk_mapper import RiskStabilityMapper
from .pass3_affordance_engine import CognitiveAffordanceEngine
from .pass4_context_formatter import ContextInjectionFormatter


class Phase3Orchestrator:
    """Orchestrates the four-pass Phase-3 cognitive compilation pipeline."""

    def __init__(self, manifold_states_path: Path, output_path: Path):
        self.manifold_states_path = manifold_states_path
        self.output_path = output_path

        # Initialize passes
        self.role_interpreter = RoleInterpreter()
        self.risk_mapper = RiskStabilityMapper()
        self.affordance_engine = CognitiveAffordanceEngine()
        self.context_formatter = ContextInjectionFormatter()

    def run(self) -> None:
        """Run the complete Phase-3 pipeline."""
        start_time = datetime.now()
        print(f"[Phase-3] Starting cognitive compilation pipeline...")
        print(f"[Phase-3] Input: {self.manifold_states_path}")
        print(f"[Phase-3] Output: {self.output_path}")
        print()

        # Load manifold states
        manifold_states = self._load_manifold_states()
        print(f"[Phase-3] Loaded {len(manifold_states)} manifold states")
        print()

        # Process each symbol through 4 passes
        print("=" * 60)
        print("COGNITIVE COMPILATION")
        print("=" * 60)

        cognitive_contexts = []
        for sms in tqdm(manifold_states, desc="Compiling cognitive contexts"):
            # Pass 1: Role Interpretation
            cognitive_role = self.role_interpreter.interpret(sms)

            # Pass 2: Risk Mapping
            stability = self.risk_mapper.map_stability(sms)

            # Pass 3: Affordance Detection
            affordances, attention_weight = self.affordance_engine.detect_affordances(sms)

            # Pass 4: Context Formatting
            csc = self.context_formatter.format_context(
                sms, cognitive_role, stability, affordances, attention_weight
            )

            cognitive_contexts.append(csc)

        # Write output
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, 'w') as f:
            for csc in cognitive_contexts:
                f.write(csc.model_dump_json() + '\n')

        print()
        print(f"[Phase-3] Wrote {len(cognitive_contexts)} CSC records to {self.output_path}")
        print()

        # Statistics
        self._print_statistics(cognitive_contexts)

        # Summary
        duration = (datetime.now() - start_time).total_seconds()
        print("=" * 60)
        print("PHASE-3 COMPLETE")
        print("=" * 60)
        print(f"Duration: {duration:.2f} seconds")
        print(f"Output: {self.output_path}")
        print()

    def _load_manifold_states(self) -> list:
        """Load manifold states from Phase-2 output."""
        manifold_states = []
        with open(self.manifold_states_path) as f:
            for line in f:
                data = json.loads(line)
                sms = SymbolManifoldState(**data)
                manifold_states.append(sms)
        return manifold_states

    def _print_statistics(self, cognitive_contexts: list) -> None:
        """Print compilation statistics."""
        print("=" * 60)
        print("STATISTICS")
        print("=" * 60)

        # Cognitive role distribution
        role_counts = {}
        for csc in cognitive_contexts:
            role = csc.cognitive_role.type
            role_counts[role] = role_counts.get(role, 0) + 1

        print("Cognitive Role Distribution:")
        for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
            pct = count / len(cognitive_contexts) * 100
            print(f"  {role}: {count} ({pct:.1f}%)")
        print()

        # Stability class distribution
        stability_counts = {}
        for csc in cognitive_contexts:
            stability = csc.stability.stability_class
            stability_counts[stability] = stability_counts.get(stability, 0) + 1

        print("Stability Class Distribution:")
        for stability, count in sorted(stability_counts.items(), key=lambda x: -x[1]):
            pct = count / len(cognitive_contexts) * 100
            print(f"  {stability}: {count} ({pct:.1f}%)")
        print()

        # Mutation risk distribution
        risk_counts = {}
        for csc in cognitive_contexts:
            risk = csc.stability.mutation_risk
            risk_counts[risk] = risk_counts.get(risk, 0) + 1

        print("Mutation Risk Distribution:")
        for risk, count in sorted(risk_counts.items(), key=lambda x: -x[1]):
            pct = count / len(cognitive_contexts) * 100
            print(f"  {risk}: {count} ({pct:.1f}%)")
        print()

        # Top affordances
        affordance_counts = {}
        for csc in cognitive_contexts:
            for affordance in csc.affordances:
                affordance_counts[affordance] = affordance_counts.get(affordance, 0) + 1

        print("Top Affordances:")
        for affordance, count in sorted(affordance_counts.items(), key=lambda x: -x[1])[:10]:
            pct = count / len(cognitive_contexts) * 100
            print(f"  {affordance}: {count} ({pct:.1f}%)")
        print()

        # Average attention weight
        avg_attention = sum(csc.attention_weight for csc in cognitive_contexts) / len(cognitive_contexts)
        print(f"Average Attention Weight: {avg_attention:.3f}")
        print()


def main():
    """CLI entry point."""
    # Default paths
    workspace_root = Path.cwd()
    manifold_states_path = workspace_root / ".quro_context" / "tda" / "phase2" / "manifold_states.jsonl"
    output_path = workspace_root / ".quro_context" / "tda" / "phase3" / "cognitive_contexts.jsonl"

    # Check if manifold states exist
    if not manifold_states_path.exists():
        print(f"[Phase-3] Error: Phase-2 manifold states not found: {manifold_states_path}", file=sys.stderr)
        print(f"[Phase-3] Run Phase-2 first: python -m quro.tda.phase2", file=sys.stderr)
        sys.exit(1)

    # Run pipeline
    orchestrator = Phase3Orchestrator(manifold_states_path, output_path)
    orchestrator.run()


if __name__ == "__main__":
    main()
