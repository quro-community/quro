"""Shadow Adapter - Filesystem implementation.

@module quro.adapters.shadows.filesystem
@intent Filesystem implementation of ShadowAdapter protocol.
"""

import zlib
from pathlib import Path
from typing import Optional
from .types import ShadowFile, ShadowReadRequest, ShadowWriteRequest, DSLAtom
from .protocol import ShadowAdapter


# Operator abbreviation map (ACQUIRE → ACQ, etc.)
_OP_ABBREV: dict[str, str] = {
    "ACQUIRE": "ACQ",
    "AWAIT": "AWT",
    "CONT": "CNT",
    "EMIT": "EMT",
    "GEN": "GEN",
    "CALL": "CAL",
    "RELEASE": "REL",
    "STATE": "STA",
}
_ABBREV_OP: dict[str, str] = {v: k for k, v in _OP_ABBREV.items()}

_MAX_ATOMS = 50


class FileSystemShadow:
    """Filesystem implementation of ShadowAdapter.

    Reads/writes .qss shadow files in .quro_context/shadows/ directory.
    """

    def __init__(self, workspace_root: Path):
        """Initialize with workspace root.

        Args:
            workspace_root: Workspace root directory
        """
        self.workspace_root = Path(workspace_root)
        self.shadows_dir = self.workspace_root / ".quro_context" / "shadows"

    async def setup(self) -> None:
        """Initialize shadow directories."""
        self.shadows_dir.mkdir(parents=True, exist_ok=True)

    async def read_shadow(
        self,
        request: ShadowReadRequest
    ) -> Optional[ShadowFile]:
        """Read shadow file from filesystem.

        Args:
            request: Shadow read request (frozen dataclass)

        Returns:
            ShadowFile if found, None otherwise
        """
        shadow_path = self.shadows_dir / request.file_path

        if not shadow_path.exists():
            return None

        try:
            text = shadow_path.read_text(encoding="utf-8")
            return self._parse(text)
        except Exception:
            return None

    async def write_shadow(
        self,
        request: ShadowWriteRequest
    ) -> ShadowFile:
        """Write shadow file to filesystem.

        Args:
            request: Shadow write request (frozen dataclass)

        Returns:
            ShadowFile that was written
        """
        shadow_path = self.shadows_dir / request.file_path

        # Create parent directories
        shadow_path.parent.mkdir(parents=True, exist_ok=True)

        # Serialize and write
        text = self._serialize(request.shadow)
        shadow_path.write_text(text, encoding="utf-8")

        return request.shadow

    async def delete_shadow(self, file_path: str) -> bool:
        """Delete shadow file from filesystem.

        Args:
            file_path: Path to shadow file (relative to shadows directory)

        Returns:
            True if deleted, False if not found
        """
        shadow_path = self.shadows_dir / file_path

        if not shadow_path.exists():
            return False

        shadow_path.unlink()
        return True

    async def list_shadows(self) -> tuple[str, ...]:
        """List all shadow files in the shadows directory.

        Returns:
            Tuple of shadow file paths (relative to shadows directory)
        """
        if not self.shadows_dir.exists():
            return ()

        shadows = []
        for shadow_path in self.shadows_dir.rglob("*.qss"):
            rel_path = shadow_path.relative_to(self.shadows_dir)
            shadows.append(str(rel_path))

        return tuple(sorted(shadows))

    async def compute_checksum(self, source_bytes: bytes) -> str:
        """Compute CRC32 checksum of source bytes.

        Args:
            source_bytes: Source file content

        Returns:
            8-character hex string (CRC32 checksum)
        """
        return f"{zlib.crc32(source_bytes) & 0xFFFFFFFF:08x}"

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _serialize(self, shadow: ShadowFile) -> str:
        """Serialize a ShadowFile to .qss text."""
        lines: list[str] = [
            f"@S:{shadow.symbol};",
        ]
        for extra in shadow.extra_symbols:
            lines.append(f"@S:{extra};")
        lines += [
            f"@D:[{','.join(shadow.deps)}];",
            f"@CK:{shadow.checksum};",
        ]

        # Add behavioral tags if present
        if shadow.behavioral_tags:
            lines.append(f"@T:{','.join(shadow.behavioral_tags)};")

        # Add risk anchors if present
        if shadow.risk_anchors:
            lines.append(f"@R:{','.join(shadow.risk_anchors)};")

        # Add schema references if present
        if shadow.schema_refs:
            lines.append(f"@SCHEMA:{','.join(shadow.schema_refs)};")

        atoms = shadow.atoms
        truncated = shadow.truncated or len(atoms) > _MAX_ATOMS
        if len(atoms) > _MAX_ATOMS:
            atoms = atoms[:_MAX_ATOMS]

        for atom in atoms:
            abbrev = _OP_ABBREV.get(atom.op, atom.op)
            line = f"L{atom.line_hint}:{abbrev}({atom.resource})"
            if atom.in_finally is not None:
                flag = "Y" if atom.in_finally else "N"
                line += f"[f:{flag}]"
            line += ";"
            lines.append(line)

        for risk in shadow.risks:
            lines.append(f"L0:RISK({risk});")

        if truncated:
            lines.append("; TRUNCATED")

        return "\n".join(lines) + "\n"

    def _parse(self, text: str) -> ShadowFile:
        """Parse .qss text into a ShadowFile."""
        lines = [l.rstrip() for l in text.strip().splitlines()]
        if len(lines) < 3:
            raise ValueError("qss file must have at least 3 header lines")

        # Collect all @S lines (primary + extra_symbols)
        symbol_lines = [l for l in lines if l.startswith("@S:")]
        if not symbol_lines:
            raise ValueError("Missing required @S header")
        symbol = self._parse_header(symbol_lines[0], "@S:")
        extra_symbols: tuple[str, ...] = tuple(
            self._parse_header(l, "@S:") for l in symbol_lines[1:]
        )

        # @D and @CK follow all @S lines
        remaining = [l for l in lines if not l.startswith("@S:")]
        if len(remaining) < 2:
            raise ValueError("Missing @D or @CK header")
        deps_raw = self._parse_header(remaining[0], "@D:")
        checksum = self._parse_header(remaining[1], "@CK:")

        # Parse deps list: strip brackets
        deps_str = deps_raw.strip("[]")
        deps: tuple[str, ...] = tuple(d for d in deps_str.split(",") if d) if deps_str else ()

        # Parse optional @T (behavioral tags) and @R (risk anchors)
        behavioral_tags: tuple[str, ...] = ()
        risk_anchors: tuple[str, ...] = ()
        schema_refs: tuple[str, ...] = ()
        atom_start_idx = 2

        if len(remaining) > 2 and remaining[2].startswith("@T:"):
            tags_raw = self._parse_header(remaining[2], "@T:")
            behavioral_tags = tuple(t.strip() for t in tags_raw.split(",") if t.strip())
            atom_start_idx = 3

        if len(remaining) > atom_start_idx and remaining[atom_start_idx].startswith("@R:"):
            anchors_raw = self._parse_header(remaining[atom_start_idx], "@R:")
            risk_anchors = tuple(a.strip() for a in anchors_raw.split(",") if a.strip())
            atom_start_idx += 1

        if len(remaining) > atom_start_idx and remaining[atom_start_idx].startswith("@SCHEMA:"):
            schema_raw = self._parse_header(remaining[atom_start_idx], "@SCHEMA:")
            schema_refs = tuple(s.strip() for s in schema_raw.split(",") if s.strip())
            atom_start_idx += 1

        atoms: list[DSLAtom] = []
        risks: list[str] = []
        truncated = False

        for line in remaining[atom_start_idx:]:
            line = line.rstrip(";")
            if not line or line.startswith(";"):
                if "TRUNCATED" in line:
                    truncated = True
                continue

            # Parse: L<N>:<OP>(<Arg>)[<Ann>]
            try:
                colon_idx = line.index(":")
                line_no = int(line[1:colon_idx])  # strip leading 'L'
                rest = line[colon_idx + 1:]

                paren_open = rest.index("(")
                bracket_pos = rest.find("[")
                if bracket_pos != -1 and bracket_pos > paren_open:
                    paren_close = rest.rindex(")", paren_open, bracket_pos)
                else:
                    paren_close = rest.rindex(")")
                op_abbrev = rest[:paren_open]
                resource = rest[paren_open + 1:paren_close]
                annotation = rest[paren_close + 1:]

                if op_abbrev == "RISK":
                    risks.append(resource)
                    continue

                op = _ABBREV_OP.get(op_abbrev, op_abbrev)
                in_finally: bool | None = None
                if "[f:" in annotation:
                    flag_char = annotation[annotation.index("[f:") + 3]
                    in_finally = flag_char == "Y"

                atoms.append(DSLAtom(
                    op=op,  # type: ignore[arg-type]
                    resource=resource,
                    in_finally=in_finally,
                    line_hint=line_no,
                ))
            except (ValueError, IndexError) as exc:
                raise ValueError(f"Malformed qss atom line: {line!r}") from exc

        return ShadowFile(
            symbol=symbol,
            deps=deps,
            checksum=checksum,
            atoms=tuple(atoms),
            risks=tuple(risks),
            truncated=truncated,
            extra_symbols=extra_symbols,
            behavioral_tags=behavioral_tags,
            risk_anchors=risk_anchors,
            schema_refs=schema_refs,
        )

    def _parse_header(self, line: str, prefix: str) -> str:
        """Extract value from a header line like '@S:Foo;'."""
        if not line.startswith(prefix):
            raise ValueError(f"Expected line starting with {prefix!r}, got: {line!r}")
        return line[len(prefix):].rstrip(";")
