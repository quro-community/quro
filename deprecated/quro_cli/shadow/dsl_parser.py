"""
DSL Atom Parser for Shadow Draft System

Parses and validates DSL atoms for the Neural Compiler.
Atoms represent concurrent operations: ACQ, AWT, REL, STA, CALL, EMIT, GEN.
"""
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class AtomType(Enum):
    """DSL atom types"""
    ACQ = "ACQ"      # Acquire lock/resource
    AWT = "AWT"      # Await coroutine
    REL = "REL"      # Release lock
    STA = "STA"      # Business logic slot
    CALL = "CALL"    # Call async method
    EMIT = "EMIT"    # Emit event/signal
    GEN = "GEN"      # Async generator yield
    CONT = "CONT"    # Yield control (cooperative)


@dataclass
class Atom:
    """Parsed DSL atom"""
    type: AtomType
    resource: str
    line: int
    flags: Dict[str, Any]

    def __repr__(self) -> str:
        flags_str = f"[{','.join(f'{k}:{v}' for k, v in self.flags.items())}]" if self.flags else ""
        return f"{self.type.value}({self.resource}){flags_str}"


@dataclass
class ExecutionGraph:
    """Execution graph for atom sequence"""
    atoms: List[Atom]
    resources: Set[str]
    acquire_release_pairs: List[Tuple[int, int]]  # (acquire_idx, release_idx)
    await_points: List[int]  # Indices of AWT atoms
    business_logic_slots: List[int]  # Indices of STA atoms


class DSLAtomParser:
    """Parser for DSL atom strings"""

    # Atom pattern: TYPE(resource)[flags]
    # Resource can contain nested parentheses (e.g., fetch())
    ATOM_PATTERN = re.compile(
        r'^([A-Z]+)\((.+?)\)(?:\[([^\]]+)\])?$'
    )

    def __init__(self):
        """Initialize DSL atom parser"""
        self.valid_atom_types = {t.value for t in AtomType}

    def parse_atom(self, atom_str: str, line: int = 0) -> Optional[Atom]:
        """
        Parse single atom string

        Args:
            atom_str: Atom string (e.g., "ACQ(lock)", "AWT(fetch())[f:Y]")
            line: Line number in sequence

        Returns:
            Parsed Atom or None if invalid
        """
        atom_str = atom_str.strip()

        match = self.ATOM_PATTERN.match(atom_str)
        if not match:
            logger.error(f"Invalid atom format: {atom_str}")
            return None

        atom_type_str, resource, flags_str = match.groups()

        # Validate atom type
        if atom_type_str not in self.valid_atom_types:
            logger.error(f"Invalid atom type: {atom_type_str}")
            return None

        atom_type = AtomType(atom_type_str)

        # Parse flags
        flags = {}
        if flags_str:
            for flag in flags_str.split(','):
                if ':' in flag:
                    key, value = flag.split(':', 1)
                    flags[key.strip()] = value.strip()

        return Atom(
            type=atom_type,
            resource=resource.strip(),
            line=line,
            flags=flags
        )

    def parse_sequence(self, atom_strings: List[str]) -> List[Atom]:
        """
        Parse sequence of atom strings

        Args:
            atom_strings: List of atom strings

        Returns:
            List of parsed Atoms
        """
        atoms = []
        for i, atom_str in enumerate(atom_strings):
            atom = self.parse_atom(atom_str, line=i)
            if atom:
                atoms.append(atom)
            else:
                logger.warning(f"Skipping invalid atom at line {i}: {atom_str}")

        return atoms

    def validate_sequence(self, atoms: List[Atom]) -> Tuple[bool, List[str]]:
        """
        Validate atom sequence for correctness

        Checks:
        - ACQ/REL pairing
        - No double acquire
        - No release without acquire
        - Resource naming consistency

        Args:
            atoms: List of parsed atoms

        Returns:
            (is_valid, error_messages)
        """
        errors = []
        acquired_resources = {}  # resource -> acquire_line

        for i, atom in enumerate(atoms):
            if atom.type == AtomType.ACQ:
                # Check for double acquire
                if atom.resource in acquired_resources:
                    errors.append(
                        f"Line {i}: Double acquire of '{atom.resource}' "
                        f"(first acquired at line {acquired_resources[atom.resource]})"
                    )
                else:
                    acquired_resources[atom.resource] = i

            elif atom.type == AtomType.REL:
                # Check for release without acquire
                if atom.resource not in acquired_resources:
                    errors.append(
                        f"Line {i}: Release of '{atom.resource}' without prior acquire"
                    )
                else:
                    # Valid release
                    del acquired_resources[atom.resource]

        # Check for unreleased resources
        for resource, acquire_line in acquired_resources.items():
            errors.append(
                f"Resource '{resource}' acquired at line {acquire_line} but never released"
            )

        return len(errors) == 0, errors

    def build_execution_graph(self, atoms: List[Atom]) -> ExecutionGraph:
        """
        Build execution graph from atom sequence

        Args:
            atoms: List of parsed atoms

        Returns:
            ExecutionGraph with resources and control flow
        """
        resources = set()
        acquire_release_pairs = []
        await_points = []
        business_logic_slots = []

        # Track acquire/release pairs
        acquire_stack = {}  # resource -> acquire_index

        for i, atom in enumerate(atoms):
            if atom.type == AtomType.ACQ:
                resources.add(atom.resource)
                acquire_stack[atom.resource] = i

            elif atom.type == AtomType.REL:
                if atom.resource in acquire_stack:
                    acquire_idx = acquire_stack[atom.resource]
                    acquire_release_pairs.append((acquire_idx, i))
                    del acquire_stack[atom.resource]

            elif atom.type == AtomType.AWT:
                await_points.append(i)

            elif atom.type == AtomType.STA:
                business_logic_slots.append(i)

        return ExecutionGraph(
            atoms=atoms,
            resources=resources,
            acquire_release_pairs=acquire_release_pairs,
            await_points=await_points,
            business_logic_slots=business_logic_slots
        )

    def detect_potential_deadlocks(self, graph: ExecutionGraph) -> List[Dict[str, Any]]:
        """
        Detect potential deadlock patterns in execution graph

        Checks for:
        - Multiple resources acquired in different orders
        - Await inside lock (potential blocking)

        Args:
            graph: Execution graph

        Returns:
            List of potential deadlock warnings
        """
        warnings = []

        # Check for await inside lock
        for acquire_idx, release_idx in graph.acquire_release_pairs:
            acquire_atom = graph.atoms[acquire_idx]

            # Check if any await points are between acquire and release
            awaits_inside = [
                i for i in graph.await_points
                if acquire_idx < i < release_idx
            ]

            if awaits_inside:
                warnings.append({
                    "type": "await_inside_lock",
                    "resource": acquire_atom.resource,
                    "acquire_line": acquire_idx,
                    "release_line": release_idx,
                    "await_lines": awaits_inside,
                    "severity": "high",
                    "message": f"Await inside lock '{acquire_atom.resource}' may cause deadlock"
                })

        # Check for multiple resource acquisition
        if len(graph.resources) > 1:
            warnings.append({
                "type": "multiple_resources",
                "resources": list(graph.resources),
                "severity": "medium",
                "message": f"Multiple resources acquired: {', '.join(graph.resources)}. "
                          "Ensure consistent ordering to avoid deadlock."
            })

        return warnings

    def generate_python_skeleton(self, graph: ExecutionGraph, class_name: str = "GeneratedClass") -> str:
        """
        Generate Python skeleton code from execution graph

        Args:
            graph: Execution graph
            class_name: Name of generated class

        Returns:
            Python code as string
        """
        lines = []
        lines.append(f"class {class_name}:")
        lines.append("    async def execute(self):")
        lines.append("        \"\"\"Generated from DSL atoms\"\"\"")

        indent = "        "

        for atom in graph.atoms:
            if atom.type == AtomType.ACQ:
                lines.append(f"{indent}async with self.{atom.resource}:")
                indent += "    "

            elif atom.type == AtomType.REL:
                # REL is implicit in Python async with
                indent = indent[:-4]
                lines.append(f"{indent}# REL({atom.resource})")

            elif atom.type == AtomType.AWT:
                lines.append(f"{indent}await {atom.resource}")

            elif atom.type == AtomType.STA:
                lines.append(f"{indent}# [SLOT:begin:sta_{atom.resource}]")
                lines.append(f"{indent}pass  # Business logic here")
                lines.append(f"{indent}# [SLOT:end:sta_{atom.resource}]")

            elif atom.type == AtomType.CALL:
                lines.append(f"{indent}await self.{atom.resource}()")

            elif atom.type == AtomType.EMIT:
                lines.append(f"{indent}# [SLOT:begin:emit_{atom.resource}]")
                lines.append(f"{indent}pass  # Emit event: {atom.resource}")
                lines.append(f"{indent}# [SLOT:end:emit_{atom.resource}]")

            elif atom.type == AtomType.GEN:
                lines.append(f"{indent}yield {atom.resource}")

            elif atom.type == AtomType.CONT:
                lines.append(f"{indent}await asyncio.sleep(0)  # Yield control")

        return "\n".join(lines)

    def generate_typescript_skeleton(self, graph: ExecutionGraph, class_name: str = "GeneratedClass") -> str:
        """
        Generate TypeScript skeleton code from execution graph

        Args:
            graph: Execution graph
            class_name: Name of generated class

        Returns:
            TypeScript code as string
        """
        lines = []
        lines.append(f"class {class_name} {{")
        lines.append("  async execute(): Promise<void> {")
        lines.append("    // Generated from DSL atoms")

        indent = "    "

        for atom in graph.atoms:
            if atom.type == AtomType.ACQ:
                lines.append(f"{indent}await this.{atom.resource}.acquire();")
                lines.append(f"{indent}try {{")
                indent += "  "

            elif atom.type == AtomType.REL:
                indent = indent[:-2]
                lines.append(f"{indent}}} finally {{")
                lines.append(f"{indent}  this.{atom.resource}.release();")
                lines.append(f"{indent}}}")

            elif atom.type == AtomType.AWT:
                lines.append(f"{indent}await {atom.resource};")

            elif atom.type == AtomType.STA:
                lines.append(f"{indent}// [SLOT:begin:sta_{atom.resource}]")
                lines.append(f"{indent}// Business logic here")
                lines.append(f"{indent}// [SLOT:end:sta_{atom.resource}]")

            elif atom.type == AtomType.CALL:
                lines.append(f"{indent}await this.{atom.resource}();")

            elif atom.type == AtomType.EMIT:
                lines.append(f"{indent}// [SLOT:begin:emit_{atom.resource}]")
                lines.append(f"{indent}// Emit event: {atom.resource}")
                lines.append(f"{indent}// [SLOT:end:emit_{atom.resource}]")

        lines.append("  }")
        lines.append("}")

        return "\n".join(lines)
