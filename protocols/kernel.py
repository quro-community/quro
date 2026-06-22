"""
Kernel Protocol - Unified contract for all kernels (CQE, LSH, Morph)

@module quro.protocols.kernel
@intent Enforce kernel purity invariant
@constraint Pure function - no side effects allowed

INVARIANT: Kernel is Pure
- NO file I/O
- NO database access
- NO logging
- NO global state mutation
- NO policy mutation
"""

from typing import Protocol, Any, runtime_checkable


@runtime_checkable
class KernelProtocol(Protocol):
    """
    Unified kernel contract for CQE, LSH, Morph.

    All kernels must implement this interface as a PURE FUNCTION.

    MUST NOT:
    - Perform I/O (file, network, database)
    - Mutate input arguments
    - Access global state
    - Call logging functions
    - Modify policy configuration

    MUST:
    - Be deterministic (same input → same output)
    - Return immutable results
    - Handle errors as return values (not exceptions for control flow)
    """

    def query(
        self,
        graph: Any,      # Graph data structure (protocol-agnostic)
        input: Any,      # Query input (kernel-specific)
        policy: Any      # Policy configuration (read-only)
    ) -> Any:
        """
        Execute pure query.

        Args:
            graph: Graph data structure (e.g., GraphProtocol for CQE)
            input: Query input (e.g., entry_token for CQE)
            policy: Policy configuration (read-only, data-only)

        Returns:
            Result object (kernel-specific, immutable)

        Raises:
            ValueError: Only for invalid input (not for control flow)
        """
        ...
