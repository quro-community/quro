"""Registry Adapter Protocol - Pure function contract.

@module quro.adapters.registry.protocol
@intent Define the contract for Registry adapter implementations.
"""

from typing import Protocol, Optional, List, Dict, Any
from .types import (
    FileRecord,
    SymbolRecord,
    MorphismRecord,
    SymbolInsertRequest,
    MorphismInsertRequest
)


class RegistryAdapter(Protocol):
    """Pure function contract for Registry adapters.

    Invariant: All methods perform I/O (database operations).

    Implementations MUST:
    - Use frozen dataclasses for inputs/outputs
    - Handle database errors gracefully
    - Return None for not-found cases
    - Be async (database I/O)
    """

    async def setup(self) -> None:
        """Initialize adapter (e.g., cache morphism types).

        Called once after adapter creation.
        """
        ...

    async def insert_symbol(
        self,
        request: SymbolInsertRequest
    ) -> SymbolRecord:
        """Insert or update symbol in registry.

        Args:
            request: Symbol insert request (frozen dataclass)

        Returns:
            SymbolRecord with assigned ID and canonical_uid

        Invariant: Upserts on conflict (file_id, symbol_name).
        """
        ...

    async def get_symbol_by_name(
        self,
        symbol_name: str
    ) -> Optional[SymbolRecord]:
        """Get symbol by name (highest confidence).

        Args:
            symbol_name: Symbol name to lookup

        Returns:
            SymbolRecord if found, None otherwise

        Invariant: Returns highest confidence symbol if multiple matches.
        """
        ...

    async def get_symbol_by_uid(
        self,
        canonical_uid: str
    ) -> Optional[SymbolRecord]:
        """Get symbol by canonical UID.

        Args:
            canonical_uid: Canonical UID to lookup

        Returns:
            SymbolRecord if found, None otherwise
        """
        ...

    async def query_symbols(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[SymbolRecord]:
        """Query symbols with filters.

        Args:
            filters: Filter conditions (e.g., {'language': 'python', 'symbol_type': 'function'})
            limit: Maximum results to return

        Returns:
            List of SymbolRecord matching filters

        Invariant: Returns empty list if no matches.
        """
        ...

    async def insert_morphism(
        self,
        request: MorphismInsertRequest
    ) -> Optional[MorphismRecord]:
        """Insert or update morphism edge.

        Args:
            request: Morphism insert request (frozen dataclass)

        Returns:
            MorphismRecord with assigned ID, or None if symbols not found

        Invariant: Upserts on conflict (from_symbol_id, to_symbol_id, morphism_type_id).
        """
        ...

    async def get_morphisms_from(
        self,
        symbol_name: str,
        morphism_type: Optional[str] = None
    ) -> List[MorphismRecord]:
        """Get outgoing morphisms from symbol.

        Args:
            symbol_name: Source symbol name
            morphism_type: Optional filter by morphism type

        Returns:
            List of MorphismRecord

        Invariant: Returns empty list if symbol not found.
        """
        ...

    async def get_morphisms_to(
        self,
        symbol_name: str,
        morphism_type: Optional[str] = None
    ) -> List[MorphismRecord]:
        """Get incoming morphisms to symbol.

        Args:
            symbol_name: Target symbol name
            morphism_type: Optional filter by morphism type

        Returns:
            List of MorphismRecord

        Invariant: Returns empty list if symbol not found.
        """
        ...

    async def build_reverse_index(self) -> Dict[str, List[str]]:
        """Build reverse index: bare_name → [canonical_uids].

        Returns:
            Dict mapping bare symbol names to canonical UIDs

        Invariant: Critical for CQE morphism resolution.
        """
        ...
