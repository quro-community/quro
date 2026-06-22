"""panorama_builder.py — Build panorama.json v2 (Reference-Only Semantic Layer).

Panorama v2 Contract:
  - reference, not define
  - point, not explain
  - compress, not narrate
  - no natural language, no upstream semantics duplication

Data source: PostgreSQL (quro_db), NOT registry.db or shadows.
Output: .quro_context/panorama.json
Schema: quro.panorama.v2
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from collections import defaultdict

try:
    import asyncpg

    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

from quro_cli.config import QURO_DB_URL

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROJ_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJ_ROOT / ".quro_context" / "panorama.json"

# PostgreSQL connection
PG_DSN = QURO_DB_URL

# ---------------------------------------------------------------------------
# Domain classification rules (Design 55: structural-tag-driven)
# ---------------------------------------------------------------------------
# Domains are now derived from structural tag combinations, not LLM tags or file paths.
# Each domain represents a coherent concern area in the codebase.

DOMAIN_RULES = [
    {
        "id": "concurrency_safety",
        "match": lambda s: (
            "lock" in s.get("tags", [])
            or "atomic" in s.get("tags", [])
            or "raii" in s.get("tags", [])
        ),
        "risk_level": "high",
        "active_risks": ["orphan_lock_on_sigint", "lock_without_raii", "race_condition"],
    },
    {
        "id": "vram_sovereignty",
        "match": lambda s: "vram_control" in s.get("tags", []),
        "risk_level": "high",
        "active_risks": ["vram_leak", "model_unload_race"],
    },
    {
        "id": "data_persistence",
        "match": lambda s: (
            "database" in s.get("tags", [])
            or "filesystem" in s.get("tags", [])
        ),
        "risk_level": "medium",
        "active_risks": ["connection_leak", "file_handle_leak"],
    },
    {
        "id": "async_coordination",
        "match": lambda s: (
            "async" in s.get("tags", [])
            and ("io_bound" in s.get("tags", []) or "network" in s.get("tags", []))
            and "vram_control" not in s.get("tags", [])
        ),
        "risk_level": "medium",
        "active_risks": ["async_without_timeout", "cancel_exception_swallow"],
    },
    {
        "id": "error_resilience",
        "match": lambda s: "error" in s.get("tags", []),
        "risk_level": "medium",
        "active_risks": ["bare_except", "exception_swallow", "error_without_context"],
    },
    {
        "id": "security_boundary",
        "match": lambda s: (
            "security" in s.get("tags", [])
            or "hash" in s.get("tags", [])
        ),
        "risk_level": "high",
        "active_risks": ["weak_hash", "password_in_log", "token_exposure"],
    },
    {
        "id": "signal_handling",
        "match": lambda s: "signal" in s.get("tags", []),
        "risk_level": "medium",
        "active_risks": ["sigint_without_cleanup", "signal_handler_async"],
    },
    {
        "id": "data_transformation",
        "match": lambda s: (
            "parse" in s.get("tags", [])
            or "generator" in s.get("tags", [])
        ),
        "risk_level": "low",
        "active_risks": [],
    },
    {
        "id": "entry_points",
        "match": lambda s: (
            "entry_point" in s.get("tags", [])
            or "decorator" in s.get("tags", [])
        ),
        "risk_level": "low",
        "active_risks": [],
    },
]

# Risk level ordering for attention sort
_RISK_ORDER = {"high": 0, "medium": 1, "low": 2, "none": 3}


def parse_tags(raw: Any) -> List[str]:
    """Parse tags from JSON string or list."""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def classify_domain(sym: Dict[str, Any]) -> Optional[str]:
    """Classify symbol into first matching domain."""
    for rule in DOMAIN_RULES:
        if rule["match"](sym):
            return rule["id"]
    return None


def select_anchor(members: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Select symbol with highest confidence as domain anchor."""
    if not members:
        return None
    return max(members, key=lambda s: s.get("confidence", 0))


# ---------------------------------------------------------------------------
# NRT invariant ref extraction
# ---------------------------------------------------------------------------


def _extract_invariant_refs(project_root: Path) -> List[Dict[str, str]]:
    """Parse .nrt files and extract CRITICAL rule refs with symbols.

    Returns list of {"ref": "nrt:SYMBOL", "symbols": [...]}.
    Only CRITICAL entries for symbols in NRT files are included.
    Capped at 20 entries to keep panorama concise.
    """
    nrt_dir = project_root / ".quro_context" / "nrt_rules"
    if not nrt_dir.exists():
        return []

    refs = []
    for nrt_file in sorted(nrt_dir.glob("*.nrt")):
        symbol_name = nrt_file.stem
        try:
            text = nrt_file.read_text(encoding="utf-8")
            if "@SEVERITY:CRITICAL" in text:
                refs.append({"ref": f"nrt:{symbol_name}", "symbols": [symbol_name]})
        except Exception:
            continue
        if len(refs) >= 20:
            break

    return refs


# ---------------------------------------------------------------------------
# Pitfall ref extraction
# ---------------------------------------------------------------------------


def _extract_risk_refs(
    domains: List[Dict[str, Any]],
    project_root: Path,
) -> List[Dict[str, Any]]:
    """Map active risks to pitfall archive IDs.

    Returns list of {"risk": str, "domain": str, "pitfall": str | null}.
    Matches by domain ID in pitfall categories field.
    """
    pitfall_path = project_root / ".quro_context" / "pitfall_archive.jsonl"

    # Build domain → pitfall_id index from archive categories
    domain_to_pitfall: Dict[str, str] = {}
    if pitfall_path.exists():
        try:
            for line in pitfall_path.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                entry = json.loads(line)
                categories = entry.get("categories", [])
                pid = entry.get("id", "")
                for domain in domains:
                    if (
                        domain["id"] in categories
                        and domain["id"] not in domain_to_pitfall
                    ):
                        domain_to_pitfall[domain["id"]] = pid
        except Exception:
            pass

    results = []
    for domain in domains:
        for risk in domain["active_risks"]:
            # Use domain-level pitfall lookup as primary, fall back to None
            pitfall_id = domain_to_pitfall.get(domain["id"])
            results.append(
                {
                    "risk": risk,
                    "domain": domain["id"],
                    "pitfall": pitfall_id,
                }
            )
    return results


# ---------------------------------------------------------------------------
# Synapse cycle injection
# ---------------------------------------------------------------------------


def _inject_synapse_alerts(
    hubs: List[Dict[str, Any]], project_root: Path
) -> List[Dict[str, Any]]:
    """Inject deadlock_risk and cycle_paths from project_synapse.json."""
    synapse_path = project_root / ".quro_context" / "project_synapse.json"
    if not synapse_path.exists():
        return hubs

    try:
        graph = json.loads(synapse_path.read_text(encoding="utf-8"))
        cycles = graph.get("cycles", [])
    except Exception:
        return hubs

    result = []
    for hub in hubs:
        involved = [c for c in cycles if hub["symbol"] in c]
        result.append(
            {
                **hub,
                "deadlock_risk": len(involved) > 0,
                "cycle_paths": involved,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


async def load_symbols_pg() -> List[Dict[str, Any]]:
    """Load symbols from PostgreSQL V2 symbols table."""
    if not HAS_ASYNCPG:
        logger.error("asyncpg not installed, cannot query PostgreSQL")
        return []

    pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=3)
    try:
        rows = await pool.fetch("""
            SELECT
                s.canonical_uid AS uid,
                f.file_path,
                s.symbol_name,
                s.role,
                s.tags,
                s.confidence
            FROM symbols s
            JOIN files f ON s.file_id = f.id
            WHERE s.deprecated_at IS NULL
              AND s.confidence > 0
        """)
        symbols = []
        for r in rows:
            symbols.append(
                {
                    "uid": r["uid"],
                    "file_path": r["file_path"] or "",
                    "symbol_name": r["symbol_name"] or "",
                    "role": r["role"] or "unknown",
                    "tags": parse_tags(r["tags"]),
                    "confidence": float(r["confidence"] or 0),
                }
            )
        return symbols
    finally:
        await pool.close()


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build_panorama_sync(
    symbols: List[Dict[str, Any]], project_root: Path
) -> Dict[str, Any]:
    """Build panorama v2 from symbols list.

    Schema: quro.panorama.v2 — Reference-Only Semantic Layer.
    No NLP, no prose, no upstream duplication.
    """
    file_set = set(s["file_path"] for s in symbols if s["file_path"])

    # --- Classify domains ---
    domain_map: Dict[str, List[Dict]] = {r["id"]: [] for r in DOMAIN_RULES}
    for sym in symbols:
        domain_id = classify_domain(sym)
        if domain_id:
            domain_map[domain_id].append(sym)

    # Build domain entries (v2: no intent, no file, no related_docs)
    domains = []
    for rule in DOMAIN_RULES:
        members = domain_map.get(rule["id"], [])
        anchor = select_anchor(members)
        if not anchor:
            continue

        # Entry tokens: top 4 symbols by confidence
        sorted_members = sorted(members, key=lambda s: s["confidence"], reverse=True)
        entry_tokens = [s["symbol_name"] for s in sorted_members[:4]]

        # Tags: merge unique tags from top members
        all_tags: list[str] = []
        seen_tags: set[str] = set()
        for s in sorted_members[:5]:
            for t in s.get("tags", []):
                if t not in seen_tags:
                    all_tags.append(t)
                    seen_tags.add(t)

        domains.append(
            {
                "id": rule["id"],
                "anchor": anchor["symbol_name"],
                "entry_tokens": entry_tokens,
                "member_count": len(members),
                "risk_level": rule["risk_level"],
                "active_risks": rule["active_risks"],
                "tags": all_tags,
            }
        )

    # --- Attention: sorted by risk_level ---
    attention = sorted(
        [{"domain": d["id"], "risk_level": d["risk_level"]} for d in domains],
        key=lambda x: _RISK_ORDER.get(x["risk_level"], 9),
    )

    # --- Invariant refs from NRT rules ---
    invariant_refs = _extract_invariant_refs(project_root)

    # --- Risk refs with pitfall archive links ---
    risk_refs = _extract_risk_refs(domains, project_root)

    # --- Hubs (cross-domain centrality) ---
    BEHAVIORAL_TAGS = {
        "lock",
        "raii",
        "async",
        "vram_control",
        "io_bound",
        "resource_manager",
    }
    total_domains = len(domains) or 1

    hub_candidates = []
    for sym in symbols:
        crossed = [r["id"] for r in DOMAIN_RULES if r["match"](sym)]
        if not crossed:
            continue
        base = len(crossed) / total_domains
        behavioral_hits = len([t for t in sym["tags"] if t in BEHAVIORAL_TAGS])
        behavioral_weight = (
            min(behavioral_hits / len(BEHAVIORAL_TAGS), 1) * 0.5
            if behavioral_hits > 0
            else 0
        )
        type_penalty = (
            0.4 if sym["role"] == "core_infrastructure" and behavioral_hits == 0 else 0
        )
        centrality = max(0, base + behavioral_weight - type_penalty)

        hub_candidates.append(
            {
                "symbol": sym["symbol_name"],
                "crosses_domains": crossed,
                "centrality": round(centrality, 2),
                "deadlock_risk": False,
                "cycle_paths": [],
            }
        )

    hubs = sorted(hub_candidates, key=lambda h: h["centrality"], reverse=True)[:5]
    hubs = _inject_synapse_alerts(hubs, project_root)

    return {
        "$schema": "quro.panorama.v2",
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": "postgresql",
            "symbol_count": len(symbols),
            "file_count": len(file_set),
        },
        "attention": attention,
        "invariant_refs": invariant_refs,
        "risk_refs": risk_refs,
        "domains": domains,
        "hubs": hubs,
    }


async def build_panorama():
    """Main async entry point."""
    logger.info("Loading symbols from PostgreSQL (%s)...", PG_DSN)
    symbols = await load_symbols_pg()
    logger.info("Loaded %d symbols", len(symbols))

    result = build_panorama_sync(symbols, PROJ_ROOT)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(
        "Built panorama v2: %d symbols, %d domains, %d hubs, %d invariant_refs, %d risk_refs → %s",
        result["meta"]["symbol_count"],
        len(result["domains"]),
        len(result["hubs"]),
        len(result["invariant_refs"]),
        len(result["risk_refs"]),
        OUTPUT_PATH,
    )


def main():
    import asyncio

    asyncio.run(build_panorama())


if __name__ == "__main__":
    main()
