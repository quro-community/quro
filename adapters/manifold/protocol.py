"""Manifold Adapter Protocol - Pure function contract.

@module quro.adapters.manifold.protocol
@intent Define the contract for Manifold adapter implementations.
"""

from typing import Protocol, Optional, List
from .types import ManifoldNode, NodeInsertRequest


class ManifoldAdapter(Protocol):
    """Pure function contract for Manifold adapters.

    Invariant: All methods perform I/O (database operations).

    Implementations MUST:
    - Use frozen dataclasses for inputs/outputs
    - Handle database errors gracefully
    - Return None for not-found cases
    - Be async (database I/O)
    """

    async def setup(self) -> None:
        """Initialize adapter (e.g., create tables).

        Called once after adapter creation.
        """
        ...

    async def upsert_node(
        self,
        request: NodeInsertRequest
    ) -> ManifoldNode:
        """Insert or update manifold node.

        Args:
            request: Node insert request (frozen dataclass)

        Returns:
            ManifoldNode with current state

        Invariant: Upserts on conflict (symbol_uid).
        """
        ...

    async def get_node(
        self,
        symbol_uid: str
    ) -> Optional[ManifoldNode]:
        """Get manifold node by symbol UID.

        Args:
            symbol_uid: Symbol UID to lookup

        Returns:
            ManifoldNode if found, None otherwise
        """
        ...

    async def get_all_nodes(self) -> List[ManifoldNode]:
        """Get all manifold nodes.

        Returns:
            List of ManifoldNode (empty if none exist)

        Invariant: Returns empty list if no nodes.
        """
        ...

    async def delete_node(self, symbol_uid: str) -> bool:
        """Delete manifold node by symbol UID.

        Args:
            symbol_uid: Symbol UID to delete

        Returns:
            True if deleted, False if not found
        """
        ...
