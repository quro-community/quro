"""Core-symbol coverage computation for centers documentation.

@module quro.coverage
@intent Define what counts as a "core symbol" of a center and how much of it
is documented, replacing the misleading documented/total_symbols metric.

A symbol is CORE if it is any of:
  - an entry point of the center (from metadata.json)
  - a high-energy attractor (forward_magnitude >= HIGH_ENERGY_THRESHOLD)
  - a structural coupling bridge symbol for this center
  - explicitly listed in metadata.json "core_modules"

A symbol is DOCUMENTED if its id appears in any docs/*.md under the center,
or in the center's index.md "Core Symbols" table.

Coverage = documented_core / total_core.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

HIGH_ENERGY_THRESHOLD = 20.0  # forward magnitude; matches C0 index "High (fwd>20)" band

# Symbol-id pattern as it appears in docs: sym::Name::file::line or sym::Name
_SYMBOL_RE = re.compile(r"sym::[A-Za-z0-9_]+(?:::[A-Za-z0-9_]+)*(?:::\d+)?")


def _load_center_metadata(meta_path: Path) -> Dict[str, Any]:
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_semantic_centers(workspace: Path) -> Dict[str, Any]:
    sc_path = workspace / ".quro_context" / "tda" / "phase3_5" / "semantic_centers.json"
    if not sc_path.exists():
        return {}
    try:
        return json.loads(sc_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_forward_magnitudes(workspace: Path) -> Dict[str, float]:
    """Map symbol id -> forward_magnitude from phase2_5 anisotropic fields."""
    fields_path = workspace / ".quro_context" / "tda" / "phase2_5" / "anisotropic_fields.jsonl"
    out: Dict[str, float] = {}
    if not fields_path.exists():
        return out
    try:
        with fields_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                sym = rec.get("symbol")
                mag = rec.get("forward_magnitude")
                if sym and isinstance(mag, (int, float)):
                    out[sym] = float(mag)
    except Exception:
        pass
    return out


def _center_member_symbols(
    center_id: str, semantic_centers: Dict[str, Any]
) -> Set[str]:
    """Best-effort set of symbols belonging to a center.

    semantic_centers.json stores entry points but not full membership rosters.
    We approximate membership via the structural_coupling bridge symbols that
    involve this center, plus entry points. Full membership would require the
    center detection output; this is sufficient for coverage scoping.
    """
    syms: Set[str] = set()
    for c in semantic_centers.get("centers", []):
        if c.get("id") == center_id:
            for ep in c.get("topology", {}).get("entry_points", []):
                if isinstance(ep, dict) and ep.get("symbol"):
                    syms.add(ep["symbol"])
    sc = semantic_centers.get("structural_coupling", {})
    for cc in sc.get("coupled_centers", []):
        if cc.get("center_a") == center_id or cc.get("center_b") == center_id:
            for b in cc.get("bridge_symbols", []):
                syms.add(b)
    return syms


def _bridge_symbols_for(center_id: str, semantic_centers: Dict[str, Any]) -> Set[str]:
    syms: Set[str] = set()
    for cc in semantic_centers.get("structural_coupling", {}).get("coupled_centers", []):
        if cc.get("center_a") == center_id or cc.get("center_b") == center_id:
            syms.update(cc.get("bridge_symbols", []) or [])
    return syms


def compute_core_symbols(
    center_id: str,
    metadata: Dict[str, Any],
    semantic_centers: Dict[str, Any],
    forward_mags: Dict[str, float],
    member_scope: Set[str],
) -> List[Tuple[str, str, float]]:
    """Return sorted [(symbol, role, forward_mag), ...] for a center's core set.

    role ∈ {entry, attractor, bridge, declared}. A symbol may qualify on
    multiple criteria; we keep the highest-precedence role label.
    """
    core: Dict[str, Tuple[str, float]] = {}

    # 1. Entry points
    for ep in metadata.get("entry_points", []) or []:
        if isinstance(ep, str):
            core[ep] = ("entry", forward_mags.get(ep, 0.0))

    # 2. High-energy attractors within this center's scope
    for sym, mag in forward_mags.items():
        if mag < HIGH_ENERGY_THRESHOLD:
            continue
        # Scope: only symbols that belong to this center. If we have no
        # member scope, fall back to all high-energy symbols (rare).
        if member_scope and sym not in member_scope:
            continue
        if sym not in core:
            core[sym] = ("attractor", mag)

    # 3. Bridge symbols
    for sym in _bridge_symbols_for(center_id, semantic_centers):
        if sym not in core:
            core[sym] = ("bridge", forward_mags.get(sym, 0.0))

    # 4. Explicitly declared core modules
    for sym in metadata.get("core_modules", []) or []:
        if isinstance(sym, str) and sym not in core:
            core[sym] = ("declared", forward_mags.get(sym, 0.0))

    # Sort: attractors by energy desc, then entries, then bridges
    role_order = {"entry": 0, "attractor": 1, "bridge": 2, "declared": 3}
    return sorted(
        [(s, role, mag) for s, (role, mag) in core.items()],
        key=lambda x: (role_order.get(x[1], 9), -x[2], x[0]),
    )


def _documented_symbols(center_dir: Path) -> Set[str]:
    """Collect every symbol id mentioned in the center's docs/*.md + index.md."""
    documented: Set[str] = set()
    candidates = [center_dir / "index.md"]
    docs_dir = center_dir / "docs"
    if docs_dir.is_dir():
        candidates.extend(sorted(docs_dir.glob("*.md")))
    for path in candidates:
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        documented.update(_SYMBOL_RE.findall(text))
    return documented


def compute_center_coverage_row(
    center_dir: Path,
    meta_path: Path,
    index_path: Path,
    *,
    workspace: Optional[Path] = None,
    semantic_centers: Optional[Dict[str, Any]] = None,
    forward_mags: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """Compute a single center's coverage row for the index/checker.

    Artifacts (semantic_centers.json, anisotropic_fields.jsonl) are loaded
    once by the caller and passed in for batch efficiency; if omitted we
    load them from `workspace` (default: two levels above the docs root).
    """
    metadata = _load_center_metadata(meta_path)
    center_id = metadata.get("center_id") or center_dir.name

    if semantic_centers is None or forward_mags is None:
        ws = workspace or _infer_workspace(center_dir)
        if semantic_centers is None:
            semantic_centers = _load_semantic_centers(ws) if ws else {}
        if forward_mags is None:
            forward_mags = _load_forward_magnitudes(ws) if ws else {}

    member_scope = _center_member_symbols(center_id, semantic_centers)
    core = compute_core_symbols(
        center_id, metadata, semantic_centers, forward_mags, member_scope
    )
    documented = _documented_symbols(center_dir)

    core_ids = [s for s, _, _ in core]
    doc_core = [s for s in core_ids if s in documented]
    missing = [s for s in core_ids if s not in documented]

    total = len(core_ids)
    doc = len(doc_core)
    pct = (doc / total) if total else 1.0

    # Role summary + first entry point for the index table
    role = metadata.get("archetype") or (
        next((c.get("topology", {}).get("pattern") for c in semantic_centers.get("centers", [])
              if c.get("id") == center_id), "-")
    )
    entry = core_ids[0] if core_ids else (metadata.get("entry_points") or ["-"])[0]

    return {
        "id": center_id,
        "role": _short_role(metadata),
        "archetype": role,
        "entry": entry,
        "core_count": total,
        "doc_count": doc,
        "coverage_pct": pct,
        "coverage": f"{doc}/{total} ({pct:.0%})",
        "missing_core": missing,
        "core_symbols": [
            {"symbol": s, "role": r, "energy": m} for s, r, m in core
        ],
    }


def _short_role(metadata: Dict[str, Any]) -> str:
    """One-line role label from metadata.json doc_generation or archetype."""
    arch = metadata.get("archetype", "-")
    return {
        "hub": "Hub",
        "fanout": "Fanout",
        "sink": "Sink",
        "chain": "Chain",
    }.get(arch, arch.capitalize() if arch else "-")


def _infer_workspace(center_dir: Path) -> Optional[Path]:
    """Infer the workspace root from a docs/centers/<Cn> path.

    Layout: <workspace>/docs/centers/<Cn>  →  workspace = parents[3]
    """
    # parents[0]=<Cn>, [1]=centers, [2]=docs, [3]=workspace
    try:
        ws = center_dir.parents[3]
        if (ws / ".quro_context").is_dir():
            return ws
    except IndexError:
        pass
    return None


__all__ = [
    "HIGH_ENERGY_THRESHOLD",
    "compute_core_symbols",
    "compute_center_coverage_row",
]
