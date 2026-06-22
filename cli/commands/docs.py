"""Docs Commands — discover, index, and verify shipped documentation.

@module quro.cli.commands.docs
@intent The req-5 discovery mechanism (docs path) plus the coverage gate
(docs check-coverage) and index builder (docs build-index).

`docs path` is the single entry point that links the skill set to the
installed documentation location, in both editable and wheel installs.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from cli.base import BaseCommand


# ---------------------------------------------------------------------------
# docs_root resolution — used by `docs path` and imported by other tooling
# ---------------------------------------------------------------------------

def docs_root() -> Optional[Path]:
    """Resolve the quro documentation directory.

    Preference order:
      1. Repo source tree (editable install / dev): <repo>/docs
      2. Wheel install: <site-packages>/docs  (docs ships as a Python package)
      3. Sys.path scan: any entry with docs/centers/
    Returns None if not found.
    """
    # Editable install: the cli module lives in <repo>/cli/commands/,
    # so parents[2] → <repo>, then <repo>/docs
    repo_docs = Path(__file__).resolve().parents[2] / "docs"
    if (repo_docs / "centers").is_dir():
        return repo_docs

    # Wheel install: docs is a Python package in site-packages/.
    # Try importlib first, then sys.path scan.
    import sys as _sys
    try:
        import docs as _docs
        p = Path(_docs.__path__[0])
        if (p / "centers").is_dir():
            return p
    except Exception:
        pass

    for entry in _sys.path:
        if not entry:
            continue
        candidate = Path(entry) / "docs"
        if (candidate / "centers").is_dir():
            return candidate

    return None


# ---------------------------------------------------------------------------
# quro docs path
# ---------------------------------------------------------------------------

class DocsPathCommand(BaseCommand):
    """Print the installed documentation index path."""

    def get_name(self) -> str:
        return "docs path"

    def get_help(self) -> str:
        return "Print the installed documentation root (links skill set → docs)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--center",
            help="Print the path to a specific center's directory instead",
        )
        parser.add_argument(
            "--skill",
            action="store_true",
            help="Print the skill-set root (docs/skills) instead",
        )

    def execute(self, args: argparse.Namespace) -> int:
        root = docs_root()
        if root is None:
            print(
                "[Error] Quro docs not found. Expected <repo>/docs or "
                "<site-packages>/quro_docs/.",
                file=sys.stderr,
            )
            return 1

        if args.skill:
            target = root / "skills"
        elif args.center:
            target = root / "centers" / args.center
        else:
            # Default: print the docs root (always present). The master
            # index lives at centers/index.md — point at it if it exists.
            target = root

        if not target.exists():
            print(f"[Error] Path does not exist: {target}", file=sys.stderr)
            return 1

        print(str(target))
        if not args.center and not args.skill:
            idx = root / "centers" / "index.md"
            hint = (
                f"  (master index: {idx})"
                if idx.exists()
                else "  (run `quro docs build-index` to create centers/index.md)"
            )
            print(hint, file=sys.stderr)
        return 0


# ---------------------------------------------------------------------------
# quro docs build-index   — regenerate docs/centers/index.md
# ---------------------------------------------------------------------------

class DocsBuildIndexCommand(BaseCommand):
    """Regenerate the master centers documentation index."""

    def get_name(self) -> str:
        return "docs build-index"

    def get_help(self) -> str:
        return "Regenerate docs/centers/index.md from per-center metadata"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--docs-root",
            type=Path,
            default=None,
            help="Docs root (default: auto-resolved via docs path)",
        )

    def execute(self, args: argparse.Namespace) -> int:
        root = args.docs_root or docs_root()
        if root is None:
            print("[Error] Could not resolve docs root.", file=sys.stderr)
            return 1

        centers_dir = root / "centers"
        if not centers_dir.is_dir():
            print(f"[Error] No centers directory at {centers_dir}", file=sys.stderr)
            return 1

        # Import lazily to avoid loading coverage machinery unless needed
        from cli.coverage import compute_center_coverage_row

        rows = []
        for cdir in sorted(centers_dir.iterdir()):
            if not cdir.is_dir() or not cdir.name.startswith("C"):
                continue
            meta_path = cdir / "metadata.json"
            index_path = cdir / "index.md"
            row = compute_center_coverage_row(cdir, meta_path, index_path)
            rows.append(row)

        out = centers_dir / "index.md"
        _write_centers_index(out, rows)
        print(f"[build-index] Wrote {out} ({len(rows)} centers)")
        return 0


def _write_centers_index(out_path: Path, rows: list) -> None:
    """Write the master centers index markdown from computed rows."""
    lines = [
        "# Quro Documentation Index",
        "",
        "> Maintained index of all shipped documentation. The skill set points here.",
        "> Regenerate: `quro docs build-index`.",
        "",
        "## By Center",
        "",
        "| Center | Role | Archetype | Core coverage | Entry |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| [{r['id']}]({r['id']}/index.md) | {r['role']} | {r['archetype']} "
            f"| {r['coverage']} | `{r['entry']}` |"
        )
    lines += [
        "",
        "## By Topic",
        "- Onboarding: ../skills/onboarding.md",
        "- Usage: ../skills/usage.md",
        "- Maintenance: ../skills/maintenance.md",
        "- CLI reference: ../skills/reference/cli-reference.md",
        "- MCP reference: ../skills/reference/mcp-reference.md",
        "- Coverage metrics: ../skills/reference/coverage-metrics.md",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# quro docs check-coverage
# ---------------------------------------------------------------------------

class DocsCheckCoverageCommand(BaseCommand):
    """Report core-symbol documentation coverage per center."""

    def get_name(self) -> str:
        return "docs check-coverage"

    def get_help(self) -> str:
        return "Report core-symbol coverage per center (CI gate)"

    def configure_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--docs-root",
            type=Path,
            default=None,
            help="Docs root (default: auto-resolved)",
        )
        parser.add_argument(
            "--workspace",
            type=Path,
            default=Path.cwd(),
            help="Workspace root for TDA artifacts (default: cwd)",
        )
        parser.add_argument(
            "--min",
            type=float,
            default=0.0,
            help="Minimum coverage to pass (exit non-zero if any center below)",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            help="Output as JSON",
        )

    def execute(self, args: argparse.Namespace) -> int:
        from cli.coverage import compute_center_coverage_row

        root = args.docs_root or docs_root()
        if root is None:
            print("[Error] Could not resolve docs root.", file=sys.stderr)
            return 1

        centers_dir = root / "centers"
        rows = []
        for cdir in sorted(centers_dir.iterdir()):
            if not cdir.is_dir() or not cdir.name.startswith("C"):
                continue
            row = compute_center_coverage_row(
                cdir, cdir / "metadata.json", cdir / "index.md"
            )
            rows.append(row)

        if args.json:
            print(json.dumps(rows, indent=2))
            return 0

        print(f"{'Center':<8}{'Core':>6}{'Doc':>6}{'Pct':>8}  Missing")
        print("-" * 60)
        worst = 1.0
        for r in rows:
            pct = r["coverage_pct"]
            worst = min(worst, pct)
            missing = ", ".join(r["missing_core"][:5]) or "-"
            print(
                f"{r['id']:<8}{r['core_count']:>6}{r['doc_count']:>6}"
                f"{pct:>7.0%}  {missing}"
            )
        print()
        if worst < args.min:
            print(
                f"[FAIL] Worst coverage {worst:.0%} below threshold {args.min:.0%}",
                file=sys.stderr,
            )
            return 1
        print(f"[OK] {len(rows)} centers checked. Worst: {worst:.0%}")
        return 0


__all__ = [
    "DocsPathCommand",
    "DocsBuildIndexCommand",
    "DocsCheckCoverageCommand",
    "docs_root",
]
