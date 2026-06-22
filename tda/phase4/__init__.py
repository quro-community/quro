"""Phase 4: Trajectory Planning and Analysis

@module quro.tda.phase4
@intent Provides trajectory planning, analysis, and simulation capabilities.

Includes:
- ExplorationEngine: Beam search with step-level decisions (Phase 4 v2, default)
- TrajectoryPlanner: A* pathfinding (legacy, backward compat)
- TrajectorySimulator: Path-level memory and coherence analysis
- Alternative path generation using Yen's algorithm
- Quality assessment and trajectory comparison
"""

import logging

# Design 85: Trajectory Simulator (coherence analysis)
from .trajectory_simulator import (
    TrajectoryAnalysis,
    TrajectorySimulator,
    TrajectoryState,
)

# Phase 4 v2: Beam Search Exploration Engine
from .trajectory_planner import (
    ExplorationEngine,
    ExplorationResult,
    StepDecision,
    CandidateDecision,
    RejectedNode,
    PathResult,
)

# Design 86: Trajectory Planner (A* pathfinding, legacy)
from .trajectory_planner import (
    FieldData,
    TrajectoryConstraints,
    TrajectoryPlan,
    TrajectoryPlanner,
    TrajectoryRequest,
)

# Design 86: Trajectory Analysis (quality assessment)
from .trajectory_analysis import (
    TrajectoryAnalyzer,
    TrajectoryComparison,
    TrajectoryQuality,
)

# Design 86: Alternative Paths (k-shortest paths)
from .alternative_paths import AlternativePathGenerator

# Design 86: Escape Mechanism (sink handling)
from .escape_mechanism import EscapeMechanism

# Design 86: Intent Encoder (natural language to vector)
from .intent_encoder import IntentEncoder

logger = logging.getLogger(__name__)

__all__ = [
    # Phase 4 v2
    "ExplorationEngine",
    "ExplorationResult",
    "StepDecision",
    "CandidateDecision",
    "RejectedNode",
    "PathResult",
    # Legacy
    "TrajectorySimulator",
    "TrajectoryState",
    "TrajectoryAnalysis",
    "TrajectoryPlanner",
    "TrajectoryRequest",
    "TrajectoryPlan",
    "TrajectoryConstraints",
    "FieldData",
    "TrajectoryAnalyzer",
    "TrajectoryQuality",
    "TrajectoryComparison",
    "AlternativePathGenerator",
    "EscapeMechanism",
    "IntentEncoder",
]

