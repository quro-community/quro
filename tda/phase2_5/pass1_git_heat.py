"""Pass 1: Git Heat Extraction

@module quro.tda.phase2_5.pass1_git_heat
@intent Extract modification frequency from git history to compute "heat" (kinetic energy).

        High heat = frequently modified = volatile = high kinetic energy
        Low heat = stable = low kinetic energy

        Formula: heat_score = tanh(commits_30d / 10) * 0.6 + tanh(lines_changed / 100) * 0.4
"""

import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GitHeatMetrics:
    """Git-based heat metrics for a symbol.

    Attributes:
        symbol: Symbol ID (e.g., 'sym::LlmGuard')
        file_path: Source file path
        commits_30d: Number of commits touching this file in last 30 days
        lines_changed_30d: Total lines changed in last 30 days
        authors: Number of unique authors
        last_modified: Last modification timestamp
        heat_score: Normalized heat score [0, 1]
    """
    symbol: str
    file_path: str
    commits_30d: int
    lines_changed_30d: int
    authors: int
    last_modified: str
    heat_score: float


def get_git_log(repo_path: Path, days: int = 30) -> List[Dict]:
    """Get git log for the last N days.

    Args:
        repo_path: Repository root path
        days: Number of days to look back

    Returns:
        List of commit dicts with file changes
    """
    since_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        # Get commit log with file stats
        result = subprocess.run(
            [
                "git",
                "log",
                f"--since={since_date}",
                "--numstat",
                "--pretty=format:%H|%an|%ad",
                "--date=iso",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )

        commits = []
        current_commit = None

        for line in result.stdout.split("\n"):
            if not line.strip():
                continue

            if "|" in line:
                # Commit header: hash|author|date
                parts = line.split("|")
                current_commit = {
                    "hash": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "files": [],
                }
                commits.append(current_commit)
            elif current_commit and "\t" in line:
                # File stat: added\tdeleted\tfilename
                parts = line.split("\t")
                if len(parts) >= 3:
                    added = parts[0] if parts[0] != "-" else "0"
                    deleted = parts[1] if parts[1] != "-" else "0"
                    filename = parts[2]
                    current_commit["files"].append({
                        "filename": filename,
                        "added": int(added),
                        "deleted": int(deleted),
                    })

        logger.info("Extracted %d commits from last %d days", len(commits), days)
        return commits

    except subprocess.CalledProcessError as e:
        logger.warning("Failed to get git log: %s", e)
        return []
    except Exception as e:
        logger.error("Error parsing git log: %s", e)
        return []


def compute_file_heat(file_path: str, commits: List[Dict]) -> Dict:
    """Compute heat metrics for a file.

    Args:
        file_path: Relative file path
        commits: List of commit dicts

    Returns:
        Dict with heat metrics
    """
    commits_touching_file = 0
    lines_changed = 0
    authors = set()
    last_modified = None

    for commit in commits:
        for file_change in commit["files"]:
            if file_change["filename"] == file_path:
                commits_touching_file += 1
                lines_changed += file_change["added"] + file_change["deleted"]
                authors.add(commit["author"])
                if last_modified is None:
                    last_modified = commit["date"]

    # Compute heat score using tanh normalization
    import math
    commit_component = math.tanh(commits_touching_file / 10.0) * 0.6
    lines_component = math.tanh(lines_changed / 100.0) * 0.4
    heat_score = commit_component + lines_component

    return {
        "commits_30d": commits_touching_file,
        "lines_changed_30d": lines_changed,
        "authors": len(authors),
        "last_modified": last_modified or "unknown",
        "heat_score": round(heat_score, 4),
    }


def extract_git_heat(
    workspace_root: Path,
    registry_db_path: Path,
    output_path: Path,
) -> Dict[str, GitHeatMetrics]:
    """Extract git heat metrics for all symbols.

    Args:
        workspace_root: Workspace root (git repo)
        registry_db_path: Path to registry.db
        output_path: Output path for symbol_heat.json

    Returns:
        Dict mapping symbol → GitHeatMetrics
    """
    logger.info("Extracting git heat from %s", workspace_root)

    # Get git log
    commits = get_git_log(workspace_root, days=30)
    if not commits:
        logger.warning("No git commits found, heat scores will be zero")

    # Load symbols from registry
    from index_builder.adapters.sqlite import SQLiteRegistryAdapter
    adapter = SQLiteRegistryAdapter(db_path=registry_db_path)
    all_nodes = adapter.get_all_nodes()
    symbols = [n for n in all_nodes if n.type == "symbol"]

    logger.info("Computing heat for %d symbols", len(symbols))

    heat_metrics: Dict[str, GitHeatMetrics] = {}

    for symbol_node in symbols:
        # Get file path from metadata
        metadata = symbol_node.metadata or {}
        file_path = metadata.get("file_path", "")

        if not file_path:
            # No file path, assign zero heat
            heat_metrics[symbol_node.id] = GitHeatMetrics(
                symbol=symbol_node.id,
                file_path="",
                commits_30d=0,
                lines_changed_30d=0,
                authors=0,
                last_modified="unknown",
                heat_score=0.0,
            )
            continue

        # Make path relative to workspace root
        try:
            rel_path = Path(file_path).relative_to(workspace_root)
        except ValueError:
            rel_path = Path(file_path)

        # Compute heat for this file
        heat = compute_file_heat(str(rel_path), commits)

        heat_metrics[symbol_node.id] = GitHeatMetrics(
            symbol=symbol_node.id,
            file_path=str(rel_path),
            commits_30d=heat["commits_30d"],
            lines_changed_30d=heat["lines_changed_30d"],
            authors=heat["authors"],
            last_modified=heat["last_modified"],
            heat_score=heat["heat_score"],
        )

    # Statistics
    high_heat = sum(1 for m in heat_metrics.values() if m.heat_score >= 0.7)
    medium_heat = sum(1 for m in heat_metrics.values() if 0.3 <= m.heat_score < 0.7)
    low_heat = sum(1 for m in heat_metrics.values() if m.heat_score < 0.3)

    logger.info(
        "Git heat computed: %d symbols (high: %d, medium: %d, low: %d)",
        len(heat_metrics), high_heat, medium_heat, low_heat,
    )

    # Write to file
    output_data = {
        "metadata": {
            "source": "git_log",
            "days_analyzed": 30,
            "total_commits": len(commits),
            "total_symbols": len(heat_metrics),
            "high_heat_count": high_heat,
            "medium_heat_count": medium_heat,
            "low_heat_count": low_heat,
        },
        "metrics": {
            symbol: {
                "file_path": m.file_path,
                "commits_30d": m.commits_30d,
                "lines_changed_30d": m.lines_changed_30d,
                "authors": m.authors,
                "last_modified": m.last_modified,
                "heat_score": m.heat_score,
            }
            for symbol, m in heat_metrics.items()
        }
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    logger.info("Wrote git heat metrics to %s", output_path)
    return heat_metrics
