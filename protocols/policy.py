"""
Policy Protocol - Data-only configuration contract

@module quro.protocols.policy
@intent Enforce policy declarative invariant
@constraint Data-only, no executable logic

INVARIANT: Policy is Declarative
- NO methods (except dataclass defaults)
- NO control flow (if/else, loops)
- NO side effects
- NO kernel state mutation
- ONLY data fields (weights, thresholds, flags)
"""

from typing import Protocol, runtime_checkable, Any


@runtime_checkable
class PolicyProtocol(Protocol):
    """
    Policy configuration contract.

    Policy MUST be data-only configuration, NOT executable logic.

    MUST NOT:
    - Contain methods (except __init__, __repr__, __eq__)
    - Contain control flow (if/else, for, while)
    - Perform side effects
    - Mutate kernel state
    - Import kernel modules

    MUST:
    - Be immutable (frozen dataclass)
    - Contain only primitive types or nested configs
    - Be serializable (JSON, YAML)
    """

    # Policy fields are defined by implementations
    # This protocol only enforces the constraint: data-only, no methods
    pass


# Example of valid policy (for documentation):
"""
from dataclasses import dataclass

@dataclass(frozen=True)
class PruneConfig:
    min_weight: float = 0.02
    max_hops: int = 5
    max_nodes_visited: int = 2000

@dataclass(frozen=True)
class BoostConfig:
    jaccard_floor: float = 0.05
    jaccard_ceiling: float = 0.95

@dataclass(frozen=True)
class CQEPolicy:
    prune: PruneConfig
    boost: BoostConfig
    # ... more configs

    # ✅ ALLOWED: Class methods that return new instances
    @classmethod
    def default(cls) -> "CQEPolicy":
        return cls(prune=PruneConfig(), boost=BoostConfig())

    # ❌ FORBIDDEN: Methods that perform logic
    def apply(self, data):  # ❌ NO
        ...

    # ❌ FORBIDDEN: Methods with side effects
    def save_to_file(self, path):  # ❌ NO
        ...
"""
