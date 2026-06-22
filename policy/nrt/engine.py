"""NRT Policy Engine - Pure breach detection implementation.

@module quro.policy.nrt.engine
@intent Pure implementation of NRT breach detection logic.
"""

import re
from typing import List
from types import (
    NRTResult,
    ShadowRule,
    CrossSTAConflict,
    PatchSuggestion,
    BreachCheckRequest,
)
from protocol import NRTPolicy


class NRTEngine:
    """Pure NRT breach detection engine.

    Evaluates NPL predicates against shadow atoms without I/O.
    """

    def check_breach(
        self,
        request: BreachCheckRequest,
        atoms: List[dict],
        rules: List[ShadowRule],
    ) -> NRTResult:
        """Check shadow atoms against NRT rules.

        Args:
            request: Breach check request
            atoms: List of atom dicts
            rules: List of compiled rules

        Returns:
            NRTResult with breach status
        """
        # If no rules, return CLEAR
        if not rules:
            return NRTResult(
                symbol=request.symbol,
                qss_path=request.qss_path,
                qra_path=request.qra_path,
                breach_type="CLEAR",
                predicate="",
                note="No rules to evaluate",
                severity="INFO",
            )

        # Evaluate each rule
        for rule in rules:
            passed, error_msg = self.evaluate_predicate(rule.predicate, atoms)
            if not passed:
                return NRTResult(
                    symbol=request.symbol,
                    qss_path=request.qss_path,
                    qra_path=request.qra_path,
                    breach_type="CRITICAL_LOGIC_BREACH",
                    predicate=rule.predicate,
                    note=error_msg or rule.note,
                    severity=rule.severity,
                )

        # All rules passed
        return NRTResult(
            symbol=request.symbol,
            qss_path=request.qss_path,
            qra_path=request.qra_path,
            breach_type="CLEAR",
            predicate="",
            note="All invariants satisfied",
            severity="INFO",
        )

    def evaluate_predicate(
        self,
        predicate: str,
        atoms: List[dict],
    ) -> tuple[bool, str]:
        """Evaluate a single NPL predicate against atoms.

        Args:
            predicate: NPL predicate string
            atoms: List of atom dicts

        Returns:
            (passed, error_message) tuple
        """
        pred = predicate.strip()

        # Form: "no ACQ(X)"
        m = re.match(r"^no ACQ\(([^)]+)\)$", pred)
        if m:
            target = m.group(1)
            for a in atoms:
                if a["op"] in ("ACQ", "ACQUIRE") and a["arg"] == target:
                    return False, (
                        f"Found ACQ({target}) at L{a['line']} but predicate forbids any acquisition"
                    )
            return True, ""

        # Form: "REL(X) count == ACQ(X) count"
        m = re.match(r"^REL\(([^)]+)\) count == ACQ\(([^)]+)\) count$", pred)
        if m:
            rel_arg, acq_arg = m.group(1), m.group(2)
            acq_count = sum(
                1 for a in atoms if a["op"] in ("ACQ", "ACQUIRE") and a["arg"] == acq_arg
            )
            rel_count = sum(
                1 for a in atoms if a["op"] in ("REL", "RELEASE") and a["arg"] == rel_arg
            )
            if acq_count != rel_count:
                return (
                    False,
                    f"ACQ({acq_arg}) count={acq_count} != REL({rel_arg}) count={rel_count}",
                )
            return True, ""

        # Form: "AWT(X) not in ACQ"
        m = re.match(r"^AWT\((.+)\) not in ACQ$", pred)
        if m:
            return self._check_awt_not_in_acq(atoms, m.group(1))

        # Form: "ACQ(X) must have REL[f:Y]"
        m = re.match(r"^ACQ\(([^)]+)\) must have REL\[f:(\w+)\]$", pred)
        if m:
            return self._simulate_lock_lifecycle(
                atoms, m.group(1), require_finally=True, finally_ann=m.group(2)
            )

        # Form: "ACQ(X) must have REL"
        m = re.match(r"^ACQ\(([^)]+)\) must have REL$", pred)
        if m:
            return self._simulate_lock_lifecycle(
                atoms, m.group(1), require_finally=False, finally_ann=""
            )

        # Unknown predicate - treat as passed to avoid false positives
        if not re.search(r"[A-Z]{3}\(", pred):
            return True, ""

        return True, ""

    def detect_cross_sta_conflicts(
        self,
        atoms_by_symbol: dict[str, List[dict]],
        edges: List[tuple[str, str]],
    ) -> List[CrossSTAConflict]:
        """Detect cross-symbol state conflicts.

        Args:
            atoms_by_symbol: Map of symbol name to atom list
            edges: List of (from_symbol, to_symbol) edges

        Returns:
            List of detected conflicts
        """
        conflicts: List[CrossSTAConflict] = []
        pairs: set[tuple[str, str]] = set()

        # Build bidirectional pairs from edges
        for from_sym, to_sym in edges:
            if from_sym and to_sym:
                pairs.add((from_sym, to_sym))
                pairs.add((to_sym, from_sym))

        for sym_a, sym_b in pairs:
            atoms_a = atoms_by_symbol.get(sym_a, [])
            atoms_b = atoms_by_symbol.get(sym_b, [])

            # Collect STA variables declared by A
            sta_vars_a = {
                a["arg"] for a in atoms_a if a["op"] in ("STA", "STATE") and a["arg"]
            }
            if not sta_vars_a:
                continue

            # Collect ACQ resources held by A
            acq_a = {
                a["arg"] for a in atoms_a if a["op"] in ("ACQ", "ACQUIRE") and a["arg"]
            }

            # Check if B writes any of those vars without holding a matching ACQ
            acq_b = {
                a["arg"] for a in atoms_b if a["op"] in ("ACQ", "ACQUIRE") and a["arg"]
            }
            sta_vars_b = {
                a["arg"] for a in atoms_b if a["op"] in ("STA", "STATE") and a["arg"]
            }

            for var in sta_vars_a & sta_vars_b:
                # Conflict if B accesses var but doesn't hold any ACQ that A holds
                if not (acq_a & acq_b):
                    conflict = CrossSTAConflict(
                        symbol_a=sym_a,
                        symbol_b=sym_b,
                        variable=var,
                        note=(
                            f"'{sym_b}' accesses shared state '{var}' (also held by '{sym_a}') "
                            f"without a common ACQ guard. Potential data race."
                        ),
                    )
                    if conflict not in conflicts:
                        conflicts.append(conflict)

        return conflicts

    def generate_patch_suggestion(
        self,
        symbol: str,
        atoms: List[dict],
        missing_resource: str,
    ) -> PatchSuggestion | None:
        """Generate auto-fix patch suggestion.

        Args:
            symbol: Symbol name
            atoms: List of atom dicts
            missing_resource: Resource missing REL

        Returns:
            PatchSuggestion if fixable, None otherwise
        """
        last_acq_line: int | None = None
        last_line_seen: int = 0

        for a in atoms:
            if a.get("line"):
                last_line_seen = a["line"]
            if a["op"] in ("ACQ", "ACQUIRE") and a["arg"] == missing_resource:
                last_acq_line = a["line"]
            elif a["op"] in ("REL", "RELEASE") and a["arg"] == missing_resource:
                last_acq_line = None  # matched — reset

        if last_acq_line is None:
            return None  # could not locate unmatched ACQ

        insert_line = last_line_seen if last_line_seen > last_acq_line else last_acq_line
        return PatchSuggestion(
            symbol=symbol,
            insert_after_line=insert_line,
            atom_to_insert=f"REL[{missing_resource}]",
            rationale=(
                f"ACQ({missing_resource}) at L{last_acq_line} has no matching REL. "
                f"Insert REL[{missing_resource}] in a finally block after L{insert_line}."
            ),
        )

    # ------------------------------------------------------------------
    # Private Helpers
    # ------------------------------------------------------------------

    def _simulate_lock_lifecycle(
        self,
        atoms: List[dict],
        acq_arg: str,
        require_finally: bool,
        finally_ann: str,
    ) -> tuple[bool, str]:
        """Stateful simulation: scan atom stream and enforce ACQ→REL pairing."""
        lock_stack: list[int] = []

        for a in atoms:
            op = a["op"]
            if op in ("ACQ", "ACQUIRE") and a["arg"] == acq_arg:
                lock_stack.append(a["line"])

            elif op in ("REL", "RELEASE") and a["arg"] == acq_arg and lock_stack:
                acq_line = lock_stack.pop()
                if require_finally:
                    ann = a.get("ann", "")
                    expected = f"f:{finally_ann}"
                    if ann != expected:
                        return (
                            False,
                            f"ACQ({acq_arg}) at L{acq_line} has REL at L{a['line']} "
                            f"but the release is not finally-guarded "
                            f"(got ann='{ann}', expected '{expected}'). "
                            f"Did you forget a finally block?",
                        )

            elif op in ("RET", "RETURN") and lock_stack:
                acq_line = lock_stack[0]
                return (
                    False,
                    f"Found ACQ({acq_arg}) at L{acq_line}, "
                    f"but reached RET at L{a['line']} without a corresponding REL. "
                    f"Did you forget a finally block?",
                )

        # EOF: any frames still open are orphaned
        if lock_stack:
            acq_line = lock_stack[0]
            return (
                False,
                f"Found ACQ({acq_arg}) at L{acq_line}, "
                f"but reached EOF without a corresponding REL. "
                f"Did you forget a finally block?",
            )

        return True, ""

    def _check_awt_not_in_acq(
        self,
        atoms: List[dict],
        awt_arg: str,
    ) -> tuple[bool, str]:
        """Check that AWT(X) does not occur inside ACQ scope."""
        lock_depth = 0

        for a in atoms:
            op = a["op"]
            if op in ("ACQ", "ACQUIRE"):
                lock_depth += 1
            elif op in ("REL", "RELEASE"):
                lock_depth = max(0, lock_depth - 1)
            elif op in ("AWT", "AWAIT") and a["arg"] == awt_arg:
                if lock_depth > 0:
                    return (
                        False,
                        f"Found AWT({awt_arg}) at L{a['line']} inside ACQ scope (depth={lock_depth}). "
                        f"This can cause deadlock.",
                    )

        return True, ""
