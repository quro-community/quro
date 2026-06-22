"""
Canonical Layer - Deterministic token resolution (from v2, unchanged)

@module quro.core.cqe.canonical
@intent Map raw strings to valid atoms deterministically
@constraint Pure logic, no LLM, no guessing

INVARIANT: Deterministic resolution
- Same input → same output
- No randomness
- No external API calls
- Bounded edit distance (max 1)

Copied from quro_sovereign/cqe_v2/canonical_layer.py (unchanged)
"""

from __future__ import annotations

from typing import Dict, List, Set
from core.cqe.types import CanonicalResult


class CanonicalLayer:
    """
    Deterministic Canonicalization Layer (No LLM, No Guessing).
    Maps raw string inputs to valid objects (Atoms) in Ob(C).

    From v2: unchanged
    """
    def __init__(self, symbol_table: List[str], aliases: Dict[str, List[str]] = None, max_edit_distance: int = 1):
        """
        :param symbol_table: ALL valid atom names (Ob(C))
        :param aliases: Persistent alias mapping e.g., {"ConfigManager": ["config", "cfg"]}
        :param max_edit_distance: strict bound (recommended: 1)
        """
        self.symbols: Set[str] = set(symbol_table)
        self._symbols_lower: Dict[str, str] = {
            s.lower(): s for s in symbol_table
        }
        self.max_dist: int = max_edit_distance

        # Build reverse alias map for O(1) lookup
        self.alias_map: Dict[str, str] = {}
        if aliases:
            for canonical, alias_list in aliases.items():
                if canonical in self.symbols:
                    for alias in alias_list:
                        self.alias_map[self._normalize(alias)] = canonical

    # ---------- Public API ----------
    def resolve(self, query: str) -> CanonicalResult:
        q = self._normalize(query)

        # 1. Exact match (fast path)
        if q in self.symbols:
            return CanonicalResult("exact", token=q)

        # 1.5 Persistent Alias match
        if q in self.alias_map:
            return CanonicalResult("alias", token=self.alias_map[q])

        # 1.6 Prefix fallback: bare token → cat::{token} or sym::{token}
        #    The symbol table stores full atom IDs (cat::async, sym::LlmGuard)
        #    but callers often pass bare tokens from suggest mode.
        prefixed = self._try_prefix_fallback(q)
        if prefixed:
            return CanonicalResult("exact", token=prefixed)

        # 2. Bounded candidate search
        candidates = self._find_candidates(q)

        if not candidates:
            return CanonicalResult("not_found", candidates=[])

        if len(candidates) == 1:
            return CanonicalResult("corrected", token=candidates[0])

        # multiple candidates -> deterministic refusal
        return CanonicalResult("ambiguous", candidates=candidates)

    # ---------- Prefix Fallback ----------
    def _try_prefix_fallback(self, query: str) -> str | None:
        """Try cat::{query} then sym::{query} as exact matches.

        Uses case-insensitive lookup so 'AsyncLock' resolves to 'sym::AsyncLock'.
        Returns the original-cased symbol from the table.
        """
        for prefix in ("cat::", "sym::"):
            key = prefix + query
            if key in self.symbols:
                return key
            # Case-insensitive: query was _normalize'd to lowercase
            match = self._symbols_lower.get(key)
            if match:
                return match
        return None

    # ---------- Core Logic ----------
    def _normalize(self, s: str) -> str:
        """
        Strict normalization only:
        - lowercase
        - strip spaces
        - NO stemming, NO semantic rewrite
        """
        return s.strip().lower()

    def _find_candidates(self, query: str) -> List[str]:
        result = []
        for sym in self.symbols:
            if self._edit_distance_leq(query, sym, self.max_dist):
                result.append(sym)
        return sorted(result)  # deterministic ordering

    # ---------- Deterministic Edit Distance (bounded) ----------
    def _edit_distance_leq(self, a: str, b: str, k: int) -> bool:
        """
        Early-exit Levenshtein (bounded by k)
        Deterministic, no heuristics.
        """
        if abs(len(a) - len(b)) > k:
            return False

        # DP with pruning
        prev = list(range(len(b) + 1))

        for i in range(1, len(a) + 1):
            curr = [i] + [0] * len(b)
            min_row = curr[0]

            for j in range(1, len(b) + 1):
                cost = 0 if a[i - 1] == b[j - 1] else 1
                curr[j] = min(
                    prev[j] + 1,        # deletion
                    curr[j - 1] + 1,    # insertion
                    prev[j - 1] + cost  # substitution
                )
                min_row = min(min_row, curr[j])

            if min_row > k:
                return False  # early prune

            prev = curr

        return prev[-1] <= k
