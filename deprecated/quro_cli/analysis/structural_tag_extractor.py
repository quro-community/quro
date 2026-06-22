"""
Deterministic structural tag extraction for CQE atom foundation.

@module quro_cli.analysis.structural_tag_extractor
@intent Extract stable, closed-vocabulary tags from AST signals and source patterns,
replacing LLM-generated open-vocabulary tags as the primary tag source for CQE.

Design: docs/designs/55-deterministic-atom-foundation.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple


# ── Closed vocabulary: AST signal → CQE category token ──────────────────────

# Each entry: (category_token, signal_patterns)
# signal_patterns are compiled regexes matched against source code.
# First match wins — order determines priority when signals overlap.
_CATEGORY_RULES: List[Tuple[str, re.Pattern]] = [
    # Async: kind-level (passed separately) OR await keyword in source
    ("async", re.compile(r"\bawait\b")),
    # Lock primitives
    ("lock", re.compile(
        r"\b(asyncio\.)?Lock\b|\bRLock\b|\bSemaphore\b|\bthreading\.Lock\b"
    )),
    # RAII: context manager protocol
    ("raii", re.compile(r"__enter__|__exit__|with\s+self\b")),
    # Error handling
    ("error", re.compile(
        r"\bexcept\b|\braise\b|\btry\s*:|\bException\b|\btraceback\b"
    )),
    # Database
    ("database", re.compile(
        r"\basyncpg\b|\bpsycopg\b|\bsqlalchemy\b|\bSELECT\b|\bINSERT\b|\btransaction\b"
    )),
    # Network
    ("network", re.compile(
        r"\brequests\.|\bhttpx\.|\baiohttp\.|\bsocket\.|\burllib|\btcp\b|\budp\b"
    )),
    # Filesystem
    ("filesystem", re.compile(
        r"\bPath\(|\.read_text|\.write_text|\bos\.path\b|\bshutil\b"
    )),
    # Hash / checksum
    ("hash", re.compile(
        r"\bhashlib\b|\bsha256\b|\bmd5\b|checksum|\bdigest\b"
    )),
    # Parsing
    ("parse", re.compile(
        r"\bast\.parse\b|\bre\.compile\b|\btokenize\b|\bjson\.loads\b|\byaml\.safe_load\b"
    )),
    # Security
    ("security", re.compile(
        r"\bauth\b|\bencrypt\b|\bdecrypt\b|\bhashlib\b|password|\btoken\b"
    )),
    # Signal handling
    ("signal", re.compile(
        r"\bSIGINT\b|\bSIGTERM\b|\bsignal\.|\batexit\b"
    )),
    # IO-bound
    ("io_bound", re.compile(
        r"\baiofiles\b|\.read_text|\.write_text|\.stream\(|\.buffer\b"
    )),
    # VRAM control (Ollama-specific)
    ("vram_control", re.compile(
        r"vram|\bloadModel\b|\bunloadModel\b|\bGPU\b|\bollama\b"
    )),
    # Atomic / concurrency primitives
    ("atomic", re.compile(
        r"\bLock\b|\bRLock\b|\bEvent\b|\bCondition\b|atomic"
    )),
    # Generator
    ("generator", re.compile(r"\byield\b")),
    # Decorator: function with callable decorators
    ("decorator", re.compile(r"")),  # Populated from AST decorators field
]

# ── Canonical tag set: single source of truth for the closed vocabulary ────────
# Used by VocabularyStore to derive the authoritative tag list.
# Includes all _CATEGORY_RULES tokens plus entry_point (determined by name/decorator).
CANONICAL_TAGS: FrozenSet[str] = frozenset(
    tag for tag, _ in _CATEGORY_RULES
) | frozenset({"entry_point"})

# Memory pattern: separate rule (not in CQE _CATEGORY_INVARIANTS but useful)
_MEMORY_PATTERN = re.compile(
    r"\bmalloc\b|\bfree\(|\bgc\.collect\b|\bweakref\b|\bmmap\b"
)

# Entry point patterns
_ENTRY_POINT_NAMES: FrozenSet[str] = frozenset({
    "main", "cli", "run", "start", "serve",
})
_ENTRY_POINT_DECORATORS: FrozenSet[str] = frozenset({
    "click.command", "click.group", "app.route", "router.get",
    "router.post", "router.put", "router.delete",
})

# Role inference patterns
_COORDINATOR_NAME_PARTS: FrozenSet[str] = frozenset({
    "orchestrat", "manager", "coordinator", "dispatcher", "scheduler",
    "controller", "handler", "broker", "mediator",
})
_TRANSFORMER_NAME_PARTS: FrozenSet[str] = frozenset({
    "transform", "convert", "mapper", "encoder", "decoder",
    "serialize", "deserialize", "normalize", "sanitize",
})
_CONFIG_FILE_NAMES: FrozenSet[str] = frozenset({
    "config.py", "settings.py", "constants.py", "defaults.py",
})
_CORE_MODULE_PARTS: FrozenSet[str] = frozenset({
    "engine", "registry", "daemon", "kernel", "core",
})

# Roles
ROLE_UNKNOWN = "unknown"
ROLE_RESOURCE_MANAGER = "resource_manager"
ROLE_IO_HANDLER = "io_handler"
ROLE_COORDINATOR = "coordinator"
ROLE_TRANSFORMER = "transformer"
ROLE_CONFIGURATION = "configuration"
ROLE_CONTAINER = "container"
ROLE_CORE_INFRASTRUCTURE = "core_infrastructure"


@dataclass(frozen=True)
class StructuralTags:
    """Immutable result of structural tag extraction.

    @intent Represent the output of deterministic tag extraction with
    provenance tracking for observability.
    """
    tags: Tuple[str, ...] = ()
    role: str = ROLE_UNKNOWN
    source: str = "structural"  # 'structural' | 'llm' | 'merged'

    def to_dict(self) -> Dict[str, object]:
        """Convert to scanner-compatible dict (immutable-safe new object)."""
        return {
            "tags": list(self.tags),
            "role": self.role,
            "source": self.source,
        }


def extract_tags(
    *,
    kind: str = "",
    source_code: str = "",
    symbol_name: str = "",
    file_path: str = "",
    decorators: Optional[List[str]] = None,
    call_count: int = 0,
) -> StructuralTags:
    """Extract deterministic tags from structural signals.

    This is the primary tag source for CQE. It produces stable,
    closed-vocabulary tokens that map directly to CQE category atoms.

    Args:
        kind: AST symbol kind (function, async_function, class, method).
        source_code: Full source code of the symbol body (no truncation).
        symbol_name: Name of the symbol.
        file_path: Relative file path (for config detection).
        decorators: List of decorator names from AST.
        call_count: Number of functions this symbol calls (for coordinator detection).

    Returns:
        StructuralTags with closed-vocabulary tags and inferred role.
    """
    tags_set: set[str] = set()

    # ── Kind-level signals (most reliable, from AST node type) ──
    if kind == "async_function":
        tags_set.add("async")

    # ── Source-level pattern matching ──
    for category_token, pattern in _CATEGORY_RULES:
        # Skip decorator — handled separately from AST decorators field
        if category_token == "decorator":
            continue
        if pattern.search(source_code):
            tags_set.add(category_token)

    # ── Memory pattern (supplementary) ──
    if _MEMORY_PATTERN.search(source_code):
        tags_set.add("memory")

    # ── Decorator tag (from AST, not regex) ──
    if decorators:
        for dec in decorators:
            if dec and dec.strip():
                tags_set.add("decorator")
                break

    # ── Entry point detection ──
    if symbol_name in _ENTRY_POINT_NAMES:
        tags_set.add("entry_point")
    if decorators:
        for dec in decorators:
            if dec in _ENTRY_POINT_DECORATORS:
                tags_set.add("entry_point")
                break

    # ── Infer role ──
    role = _infer_role(
        kind=kind,
        tags=tags_set,
        symbol_name=symbol_name,
        file_path=file_path,
        call_count=call_count,
        decorators=decorators,
    )

    # Return as immutable tuple (sorted for deterministic ordering)
    return StructuralTags(
        tags=tuple(sorted(tags_set)),
        role=role,
        source="structural",
    )


def _infer_role(
    *,
    kind: str,
    tags: set[str],
    symbol_name: str,
    file_path: str,
    call_count: int,
    decorators: Optional[List[str]],
) -> str:
    """Infer role from structural signals.

    Priority-ordered: first matching rule wins.
    """
    name_lower = symbol_name.lower()

    # Resource manager: context manager or lock/Semaphore management
    if kind == "class" and ("raii" in tags or "lock" in tags or "atomic" in tags):
        return ROLE_RESOURCE_MANAGER

    # IO handler: has filesystem/network/database signals
    io_tags = {"filesystem", "network", "database", "io_bound"}
    if tags & io_tags:
        return ROLE_IO_HANDLER

    # Coordinator: calls many functions or name suggests orchestration
    if call_count >= 5:
        return ROLE_COORDINATOR
    for part in _COORDINATOR_NAME_PARTS:
        if part in name_lower:
            return ROLE_COORDINATOR

    # Transformer: has parse tag or name suggests transformation
    if "parse" in tags:
        return ROLE_TRANSFORMER
    for part in _TRANSFORMER_NAME_PARTS:
        if part in name_lower:
            return ROLE_TRANSFORMER

    # Configuration: in config files or name suggests config
    file_basename = file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path
    if file_basename in _CONFIG_FILE_NAMES:
        return ROLE_CONFIGURATION
    if "config" in name_lower or "constant" in name_lower:
        return ROLE_CONFIGURATION

    # Container: class with no behavioral tags (data-only)
    if kind == "class" and len(tags) == 0:
        return ROLE_CONTAINER

    # Core infrastructure: engine/registry/daemon modules or naming
    for part in _CORE_MODULE_PARTS:
        if part in name_lower:
            return ROLE_CORE_INFRASTRUCTURE

    return ROLE_UNKNOWN


def merge_with_llm_tags(
    structural: StructuralTags,
    llm_tags: Optional[List[str]],
) -> StructuralTags:
    """Merge LLM-generated tags as extras on top of structural tags.

    Structural tags are never overridden — LLM tags are appended
    only if they add new vocabulary. This produces a 'merged' source
    for observability.

    Args:
        structural: Primary structural tags (authoritative).
        llm_tags: Optional LLM-generated tags (additive only).

    Returns:
        New StructuralTags with LLM extras appended.
    """
    if not llm_tags:
        return structural

    base_set = set(structural.tags)
    extras = []
    for tag in llm_tags:
        if tag not in base_set and isinstance(tag, str) and len(tag) >= 2:
            extras.append(tag)
            base_set.add(tag)

    if not extras:
        return structural

    return StructuralTags(
        tags=tuple(sorted(base_set)),
        role=structural.role,  # Role always comes from structural
        source="merged",
    )
