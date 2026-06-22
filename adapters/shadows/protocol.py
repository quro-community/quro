"""Shadow Adapter Protocol - Pure function contract.

@module quro.adapters.shadows.protocol
@intent Define the contract for Shadow adapter implementations.
"""

from typing import Protocol, Optional
from pathlib import Path
from .types import ShadowFile, ShadowReadRequest, ShadowWriteRequest


class ShadowAdapter(Protocol):
    """Pure function contract for Shadow adapters.

    Invariant: All methods perform I/O (file operations).

    Implementations MUST:
    - Use frozen dataclasses for inputs/outputs
    - Handle file I/O errors gracefully
    - Return None for not-found cases
    - Be async (file I/O)
    """

    async def setup(self) -> None:
        """Initialize adapter (e.g., create shadow directories).

        Called once after adapter creation.
        """
        ...

    async def read_shadow(
        self,
        request: ShadowReadRequest
    ) -> Optional[ShadowFile]:
        """Read shadow file from filesystem.

        Args:
            request: Shadow read request (frozen dataclass)

        Returns:
            ShadowFile if found, None otherwise

        Invariant: Returns None if file doesn't exist or parse fails.
        """
        ...

    async def write_shadow(
        self,
        request: ShadowWriteRequest
    ) -> ShadowFile:
        """Write shadow file to filesystem.

        Args:
            request: Shadow write request (frozen dataclass)

        Returns:
            ShadowFile that was written

        Invariant: Creates parent directories if needed.
        """
        ...

    async def delete_shadow(self, file_path: str) -> bool:
        """Delete shadow file from filesystem.

        Args:
            file_path: Path to shadow file (relative to shadows directory)

        Returns:
            True if deleted, False if not found
        """
        ...

    async def list_shadows(self) -> tuple[str, ...]:
        """List all shadow files in the shadows directory.

        Returns:
            Tuple of shadow file paths (relative to shadows directory)

        Invariant: Returns empty tuple if no shadows exist.
        """
        ...

    async def compute_checksum(self, source_bytes: bytes) -> str:
        """Compute CRC32 checksum of source bytes.

        Args:
            source_bytes: Source file content

        Returns:
            8-character hex string (CRC32 checksum)
        """
        ...
