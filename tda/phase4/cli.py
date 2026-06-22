"""CLI command for trajectory planning

@module quro.tda.phase4.cli
@intent Provide command-line interface for trajectory planning and analysis.

Two modes:
  - explore (default, Phase 4 v2): Beam search with step-level decisions
  - plan (A*, legacy): Single optimal path using energy-based cost
"""

import json
import sys
from pathlib import Path

from tda.phase4 import (
    TrajectoryConstraints,
    TrajectoryPlanner,
    TrajectoryRequest,
)


def main():
    """CLI entry point for trajectory planning."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Plan trajectories through code using TDA semantic navigation"
    )
    parser.add_argument(
        "start",
        nargs="?",
        help="Start symbol (e.g., sym::main). Required for --plan mode.",
    )
    parser.add_argument(
        "goal",
        nargs="?",
        help="Goal symbol (e.g., sym::EventLogWriter). Required for --plan mode.",
    )
    parser.add_argument(
        "--intent",
        default="navigate to goal",
        help="Natural language intent (default: 'navigate to goal')",
    )
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Use A* planner (legacy mode). Requires start and goal.",
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=5,
        help="Max exploration steps for --explore mode (default: 5)",
    )
    parser.add_argument(
        "--beam-width",
        "-w",
        type=int,
        default=5,
        help="Beam width for --explore mode (default: 5)",
    )
    parser.add_argument(
        "--max-hops",
        type=int,
        default=20,
        help="Maximum path length (default: 20)",
    )
    parser.add_argument(
        "--max-energy",
        type=float,
        default=10.0,
        help="Maximum energy budget for --plan mode (default: 10.0)",
    )
    parser.add_argument(
        "--max-friction",
        type=float,
        default=0.8,
        help="Maximum friction threshold (default: 0.8)",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
        help="Workspace root directory (default: current directory)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Configure logging
    if args.debug:
        import logging
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    # Initialize planner
    tda_path = args.workspace / ".quro_context" / "tda"
    if not tda_path.exists():
        print(f"Error: TDA data not found at {tda_path}", file=sys.stderr)
        print("Run TDA pipeline first: python -m quro.tda.phase2", file=sys.stderr)
        sys.exit(1)

    planner = TrajectoryPlanner(tda_path)

    if args.debug:
        print(f"Loaded {len(planner.field_data.states)} symbols")

    if args.plan:
        # Legacy A* mode
        if not args.start or not args.goal:
            print("Error: --plan mode requires start and goal arguments", file=sys.stderr)
            sys.exit(1)

        constraints = TrajectoryConstraints(
            max_energy=args.max_energy,
            max_friction=args.max_friction,
            max_hops=args.max_hops,
        )
        request = TrajectoryRequest(
            start=args.start,
            goal=args.goal,
            intent=args.intent,
            constraints=constraints,
        )
        plan = planner.plan_trajectory(request)

        if not plan:
            print("No valid path found", file=sys.stderr)
            sys.exit(1)

        if args.json:
            quality = planner.assess_plan_quality(plan)
            print(json.dumps({
                "mode": "A* (legacy)",
                "path": plan.path,
                "total_energy": plan.total_energy,
                "avg_alignment": plan.avg_alignment,
                "risk_score": plan.risk_score,
                "coherence": plan.coherence,
                "is_valid": plan.is_valid,
                "quality": {
                    "overall_score": quality.overall_score,
                    "grade": quality.grade,
                    "safety_score": quality.safety_score,
                    "coherence_score": quality.coherence_score,
                    "intent_alignment_score": quality.intent_alignment_score,
                    "path_length_score": quality.path_length_score,
                }
            }, indent=2))
        else:
            print(f"A* (legacy mode):\n")
            print(f"  Route: {' → '.join(plan.path)}")
            print(f"  Energy: {plan.total_energy:.2f}")
            print(f"  Risk: {plan.risk_score:.2f}")
            print(f"  Coherence: {plan.coherence:.2f}")
            print(f"  Valid: {plan.is_valid}")
        return

    # Phase 4 v2: Beam search exploration (default)
    if not args.start:
        print("Error: start symbol required for --explore mode", file=sys.stderr)
        sys.exit(1)

    if args.debug:
        print(f"Start symbol exists: {args.start in planner.field_data.states}")
        if args.start in planner.field_data.states:
            neighbors = planner.field_data.get_neighbors(args.start)
            print(f"Start has {len(neighbors)} neighbors: {neighbors[:5]}")

    result = planner.explore(
        start=args.start,
        intent=args.intent,
        steps=args.steps,
        beam_width=args.beam_width,
        max_hops=args.max_hops,
    )

    if args.json:
        output = {
            "mode": "beam_search (v2)",
            "start": result.start,
            "intent": result.intent,
            "steps": len(result.decisions),
            "final_paths": [],
        }

        for i, path_result in enumerate(result.final_paths):
            output["final_paths"].append({
                "rank": i + 1,
                "path": path_result.path,
                "score": path_result.score,
                "confidence": path_result.confidence,
                "is_valid": path_result.is_valid,
                "landing_hints": path_result.landing_hints,
            })

        # Include step decisions for transparency
        output["decisions"] = [
            {
                "step": d.step,
                "current": d.current,
                "candidates": [
                    {
                        "node": c.node,
                        "score": c.score,
                        "energy_hint": c.energy_hint,
                        "is_attractor": c.is_attractor,
                        "friction": c.friction,
                    }
                    for c in d.candidates
                ],
                "rejected": [
                    {"node": r.node, "reasons": r.reasons}
                    for r in d.rejected
                ],
            }
            for d in result.decisions
        ]

        print(json.dumps(output, indent=2))
    else:
        print(f"Beam Search (Phase 4 v2):\n")
        print(f"Intent: {result.intent}")
        print(f"Steps: {len(result.decisions)}")
        print(f"Final paths: {len(result.final_paths)}\n")

        for i, path_result in enumerate(result.final_paths):
            print(f"Path {i+1} (score={path_result.score:.3f}, "
                  f"confidence={path_result.confidence:.3f}):")
            print(f"  Route: {' → '.join(path_result.path)}")
            print(f"  Valid: {path_result.is_valid}")
            if path_result.landing_hints:
                print(f"  Landing hints:")
                for hint in path_result.landing_hints[:3]:
                    print(f"    - {hint['symbol']} ({hint['file']}:{hint['line']}) "
                          f"[{', '.join(hint['why_here'])}]")
            print()

        # Show first step decision for transparency
        if result.decisions:
            first = result.decisions[0]
            print(f"Step 0 (from {first.current}):")
            print(f"  Candidates: {len(first.candidates)}")
            for c in first.candidates[:3]:
                tags = []
                if c.is_attractor:
                    tags.append("attractor")
                tags_str = f" ({', '.join(tags)})" if tags else ""
                print(f"    - {c.node}: score={c.score:.3f}, "
                      f"energy_hint={c.energy_hint:.2f}{tags_str}")
            print(f"  Rejected: {len(first.rejected)}")
            for r in first.rejected[:3]:
                print(f"    - {r.node}: {', '.join(r.reasons)}")


if __name__ == "__main__":
    main()

