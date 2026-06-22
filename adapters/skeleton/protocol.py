"""Skeleton Adapter Protocol - Pure function contract.

@module quro.adapters.skeleton.protocol
@intent Define the contract for Skeleton adapter implementations.
"""

from typing import Protocol, Optional
from .types import SkeletonGraph, GraphInsertRequest


class SkeletonAdapter(Protocol):
    """Pure function contract for Skeleton adapters.

    Invariant: All methods perform I/O (file/database operations).

    Implementations MUST:
    - Use frozen dataclasses for inputs/outputs
    - Handle I/O errors gracefully
    - Return None for not-found cases
    - Be async (I/O operations)
    """

    async def setup(self) -> None:
        """Initialize adapter (e.g., create directories/tables).

        Called once after adapter creation.
        """
        ...

    async def save_graph(
        self,
        request: GraphInsertRequest
    ) -> SkeletonGraph:
        """Save complete skeleton graph snapshot.

        Args:
            request: Graph insert request (frozen dataclass)

        Returns:
            SkeletonGraph with timestamp and checksum

        Invariant: Appends to JSONL (append-only log).
        """
        ...

    async def load_graph(self) -> Optional[SkeletonGraph]:
        """Load latest skeleton graph snapshot.

        Returns:
            SkeletonGraph if exists, None otherwise

        Invariant: Reads last line from JSONL (most recent snapshot).
        """
        ...

    async def delete_graph(self) -> bool:
        """Delete all graph data.

        Returns:
            True if deleted, False if nothing to delete

        Invariant: Removes JSONL file.
        """
        ...
