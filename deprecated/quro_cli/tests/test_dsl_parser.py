"""
Tests for DSL atom parser.
"""
import pytest
from quro_cli.shadow.dsl_parser import (
    DSLAtomParser,
    Atom,
    AtomType,
    ExecutionGraph
)


@pytest.fixture
def parser():
    """Create DSL parser"""
    return DSLAtomParser()


def test_parse_simple_atom(parser):
    """Test parsing simple atom"""
    atom = parser.parse_atom("ACQ(lock)", line=0)

    assert atom is not None
    assert atom.type == AtomType.ACQ
    assert atom.resource == "lock"
    assert atom.line == 0
    assert atom.flags == {}


def test_parse_atom_with_flags(parser):
    """Test parsing atom with flags"""
    atom = parser.parse_atom("AWT(fetch())[f:Y,timeout:5]", line=1)

    assert atom is not None
    assert atom.type == AtomType.AWT
    assert atom.resource == "fetch()"
    assert atom.flags == {"f": "Y", "timeout": "5"}


def test_parse_invalid_atom(parser):
    """Test parsing invalid atom"""
    atom = parser.parse_atom("INVALID", line=0)
    assert atom is None


def test_parse_invalid_atom_type(parser):
    """Test parsing invalid atom type"""
    atom = parser.parse_atom("INVALID(resource)", line=0)
    assert atom is None


def test_parse_sequence(parser):
    """Test parsing atom sequence"""
    atoms = parser.parse_sequence([
        "ACQ(lock)",
        "STA(work)",
        "REL(lock)"
    ])

    assert len(atoms) == 3
    assert atoms[0].type == AtomType.ACQ
    assert atoms[1].type == AtomType.STA
    assert atoms[2].type == AtomType.REL


def test_validate_valid_sequence(parser):
    """Test validating valid sequence"""
    atoms = parser.parse_sequence([
        "ACQ(lock)",
        "STA(work)",
        "REL(lock)"
    ])

    is_valid, errors = parser.validate_sequence(atoms)
    assert is_valid
    assert len(errors) == 0


def test_validate_double_acquire(parser):
    """Test detecting double acquire"""
    atoms = parser.parse_sequence([
        "ACQ(lock)",
        "ACQ(lock)",
        "REL(lock)"
    ])

    is_valid, errors = parser.validate_sequence(atoms)
    assert not is_valid
    assert any("Double acquire" in e for e in errors)


def test_validate_release_without_acquire(parser):
    """Test detecting release without acquire"""
    atoms = parser.parse_sequence([
        "REL(lock)",
        "STA(work)"
    ])

    is_valid, errors = parser.validate_sequence(atoms)
    assert not is_valid
    assert any("without prior acquire" in e for e in errors)


def test_validate_unreleased_resource(parser):
    """Test detecting unreleased resource"""
    atoms = parser.parse_sequence([
        "ACQ(lock)",
        "STA(work)"
    ])

    is_valid, errors = parser.validate_sequence(atoms)
    assert not is_valid
    assert any("never released" in e for e in errors)


def test_build_execution_graph(parser):
    """Test building execution graph"""
    atoms = parser.parse_sequence([
        "ACQ(lock1)",
        "AWT(fetch())",
        "STA(work)",
        "REL(lock1)"
    ])

    graph = parser.build_execution_graph(atoms)

    assert len(graph.atoms) == 4
    assert "lock1" in graph.resources
    assert len(graph.acquire_release_pairs) == 1
    assert graph.acquire_release_pairs[0] == (0, 3)
    assert graph.await_points == [1]
    assert graph.business_logic_slots == [2]


def test_detect_await_inside_lock(parser):
    """Test detecting await inside lock"""
    atoms = parser.parse_sequence([
        "ACQ(lock)",
        "AWT(fetch())",
        "REL(lock)"
    ])

    graph = parser.build_execution_graph(atoms)
    warnings = parser.detect_potential_deadlocks(graph)

    assert len(warnings) > 0
    assert any(w["type"] == "await_inside_lock" for w in warnings)


def test_detect_multiple_resources(parser):
    """Test detecting multiple resources"""
    atoms = parser.parse_sequence([
        "ACQ(lock1)",
        "ACQ(lock2)",
        "REL(lock2)",
        "REL(lock1)"
    ])

    graph = parser.build_execution_graph(atoms)
    warnings = parser.detect_potential_deadlocks(graph)

    assert len(warnings) > 0
    assert any(w["type"] == "multiple_resources" for w in warnings)


def test_generate_python_skeleton(parser):
    """Test generating Python skeleton"""
    atoms = parser.parse_sequence([
        "ACQ(lock)",
        "STA(work)",
        "REL(lock)"
    ])

    graph = parser.build_execution_graph(atoms)
    skeleton = parser.generate_python_skeleton(graph, "TestClass")

    assert "class TestClass:" in skeleton
    assert "async def execute(self):" in skeleton
    assert "async with self.lock:" in skeleton
    assert "[SLOT:begin:sta_work]" in skeleton


def test_generate_typescript_skeleton(parser):
    """Test generating TypeScript skeleton"""
    atoms = parser.parse_sequence([
        "ACQ(lock)",
        "STA(work)",
        "REL(lock)"
    ])

    graph = parser.build_execution_graph(atoms)
    skeleton = parser.generate_typescript_skeleton(graph, "TestClass")

    assert "class TestClass {" in skeleton
    assert "async execute(): Promise<void> {" in skeleton
    assert "await this.lock.acquire();" in skeleton
    assert "try {" in skeleton
    assert "finally {" in skeleton


def test_atom_repr(parser):
    """Test atom string representation"""
    atom = parser.parse_atom("ACQ(lock)[f:Y]", line=0)
    repr_str = repr(atom)

    assert "ACQ(lock)" in repr_str
    assert "f:Y" in repr_str


def test_parse_all_atom_types(parser):
    """Test parsing all atom types"""
    atom_strings = [
        "ACQ(lock)",
        "AWT(fetch())",
        "REL(lock)",
        "STA(work)",
        "CALL(process)",
        "EMIT(event)",
        "GEN(data)",
        "CONT(label)"
    ]

    atoms = parser.parse_sequence(atom_strings)
    assert len(atoms) == 8

    expected_types = [
        AtomType.ACQ,
        AtomType.AWT,
        AtomType.REL,
        AtomType.STA,
        AtomType.CALL,
        AtomType.EMIT,
        AtomType.GEN,
        AtomType.CONT
    ]

    for atom, expected_type in zip(atoms, expected_types):
        assert atom.type == expected_type


def test_complex_execution_graph(parser):
    """Test complex execution graph"""
    atoms = parser.parse_sequence([
        "ACQ(lock1)",
        "ACQ(lock2)",
        "AWT(fetch())",
        "STA(process)",
        "CALL(save)",
        "REL(lock2)",
        "REL(lock1)"
    ])

    graph = parser.build_execution_graph(atoms)

    assert len(graph.resources) == 2
    assert len(graph.acquire_release_pairs) == 2
    assert len(graph.await_points) == 1
    assert len(graph.business_logic_slots) == 1
