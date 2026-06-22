"""
Python implementation of compact_context for skeleton generation.

@module quro_cli.compact_context
@intent Generate code skeletons without calling node_server/Bazel
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional


_INTENT_RULES = [
    # Order matters: more specific intents first to avoid keyword overlap
    # (keywords, level, alpha)
    (["bug", "fix", "debug", "crash", "traceback"], "FULL", 0.95),
    (["understand", "explain", "describe", "summarize", "how does"], "SUMMARY", 0.30),
    (["dependencies", "dependency", "import", "call graph", "trace dep"], "HIDDEN", 0.10),
    (["refactor", "rename", "move", "extract", "inline"], "SKELETON", 0.80),
    (["architecture", "audit", "overview", "structure"], "SKELETON", 0.60),
    (["design"], "SUMMARY", 0.30),
]

_DEFAULT_LEVEL = "SKELETON"
_DEFAULT_ALPHA = 0.70


def classify_intent(
    task_intent: str,
    hysteresis: Optional[PhaseHysteresis] = None,
) -> tuple[str, float]:
    """Classify task intent and return (compression_level, precision_target).

    Args:
        task_intent: Natural language task description.
        hysteresis: Optional PhaseHysteresis gate. When provided, the
                    proposed level is filtered through the hysteresis gate
                    to prevent phase flip-flopping on borderline queries.

    Returns:
        (level, alpha) where level is FULL | SKELETON | SUMMARY | HIDDEN
        and alpha is the precision target in [0, 1].
    """
    if not task_intent:
        raw_level = _DEFAULT_LEVEL
        raw_alpha = _DEFAULT_ALPHA
    else:
        intent_lower = task_intent.lower()
        raw_level = _DEFAULT_LEVEL
        raw_alpha = _DEFAULT_ALPHA

        for keywords, level, alpha in _INTENT_RULES:
            if any(kw in intent_lower for kw in keywords):
                raw_level = level
                raw_alpha = alpha
                break

    if hysteresis is not None:
        gated = hysteresis.evaluate(raw_level)
        if gated.value != raw_level:
            # Recompute alpha for the gated level
            for keywords, level, alpha in _INTENT_RULES:
                if level == gated.value:
                    return (gated.value, alpha)
            return (gated.value, _DEFAULT_ALPHA)

    return (raw_level, raw_alpha)


def generate_skeleton(source_code: str, language: str = "python") -> str:
    """
    Generate skeleton from source code.

    Skeleton includes:
    - Function/class signatures
    - Docstrings
    - Type annotations
    - No function bodies (replaced with ...)

    Args:
        source_code: Source code text
        language: Programming language (python, typescript, javascript)

    Returns:
        Skeleton code as string
    """
    if language == "python":
        return _generate_python_skeleton(source_code)
    elif language in ("typescript", "javascript"):
        return _generate_ts_skeleton(source_code)
    else:
        # Fallback: return first 500 chars
        return source_code[:500] + "\n..."


def _generate_python_skeleton(source: str) -> str:
    """Generate Python skeleton."""
    lines = source.split('\n')
    skeleton_lines = []

    in_function = False
    in_class = False
    indent_level = 0
    function_indent = 0

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.lstrip()
        current_indent = len(line) - len(stripped)

        # Keep imports
        if stripped.startswith(('import ', 'from ')):
            skeleton_lines.append(line)
            i += 1
            continue

        # Keep class definitions
        if stripped.startswith('class '):
            skeleton_lines.append(line)
            in_class = True
            indent_level = current_indent
            i += 1
            continue

        # Keep function/method definitions
        if stripped.startswith(('def ', 'async def ')):
            skeleton_lines.append(line)
            in_function = True
            function_indent = current_indent

            # Look for docstring
            i += 1
            if i < len(lines):
                next_line = lines[i].lstrip()
                if next_line.startswith(('"""', "'''")):
                    # Multi-line docstring
                    quote = '"""' if next_line.startswith('"""') else "'''"
                    skeleton_lines.append(lines[i])
                    i += 1

                    # Find end of docstring
                    while i < len(lines):
                        skeleton_lines.append(lines[i])
                        if quote in lines[i] and lines[i].strip() != quote:
                            i += 1
                            break
                        i += 1

                    # Add ... for function body
                    skeleton_lines.append(' ' * (function_indent + 4) + '...')
                    in_function = False
                else:
                    # No docstring, just add ...
                    skeleton_lines.append(' ' * (function_indent + 4) + '...')
                    in_function = False
            else:
                skeleton_lines.append(' ' * (function_indent + 4) + '...')
                in_function = False
            continue

        # Keep decorators
        if stripped.startswith('@'):
            skeleton_lines.append(line)
            i += 1
            continue

        # Keep type annotations (TypedDict, NamedTuple, etc.)
        if stripped.startswith(('class ', 'TypedDict', 'NamedTuple')):
            skeleton_lines.append(line)
            i += 1
            continue

        # Skip everything else (function bodies, etc.)
        i += 1

    return '\n'.join(skeleton_lines)


def _generate_ts_skeleton(source: str) -> str:
    """Generate TypeScript/JavaScript skeleton."""
    lines = source.split('\n')
    skeleton_lines = []

    in_function = False
    brace_count = 0

    for line in lines:
        stripped = line.lstrip()

        # Keep imports/exports
        if stripped.startswith(('import ', 'export ', 'from ')):
            skeleton_lines.append(line)
            continue

        # Keep interface/type definitions
        if stripped.startswith(('interface ', 'type ', 'enum ')):
            skeleton_lines.append(line)
            # Keep until closing brace
            brace_count = line.count('{') - line.count('}')
            if brace_count > 0:
                in_function = True
            continue

        if in_function:
            skeleton_lines.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count <= 0:
                in_function = False
            continue

        # Keep function signatures
        if re.match(r'^\s*(export\s+)?(async\s+)?function\s+\w+', stripped):
            skeleton_lines.append(line)
            continue

        # Keep class definitions
        if stripped.startswith('class '):
            skeleton_lines.append(line)
            continue

        # Keep method signatures (inside classes)
        if re.match(r'^\s*(public|private|protected|async)?\s*\w+\s*\(', stripped):
            skeleton_lines.append(line)
            continue

    return '\n'.join(skeleton_lines)


def compact_context(
    file_path: str,
    task_intent: str = "",
    force_level: str | None = None
) -> dict:
    """
    Python implementation of compact_context.

    Args:
        file_path: Path to source file
        task_intent: Task description for intent-aware compression
        force_level: Override compression level (SKELETON, SUMMARY, FULL, HIDDEN)

    Returns:
        Dict with compressedView key
    """
    path = Path(file_path)

    if not path.exists():
        return {
            "compressedView": f"# File not found: {file_path}",
            "error": "File not found"
        }

    try:
        source_code = path.read_text(encoding='utf-8')
    except Exception as e:
        return {
            "compressedView": f"# Error reading file: {e}",
            "error": str(e)
        }

    # Detect language
    suffix = path.suffix.lower()
    if suffix == '.py':
        language = 'python'
    elif suffix in ('.ts', '.tsx'):
        language = 'typescript'
    elif suffix in ('.js', '.jsx'):
        language = 'javascript'
    else:
        language = 'unknown'

    # Determine compression level
    if force_level:
        level = force_level
    elif task_intent:
        level, _alpha = classify_intent(task_intent)
    else:
        level = _DEFAULT_LEVEL

    if level == "SKELETON":
        skeleton = generate_skeleton(source_code, language)
        return {
            "compressedView": skeleton,
            "level": "SKELETON",
            "language": language
        }
    elif level == "SUMMARY":
        summary = source_code[:200] + "\n..."
        return {
            "compressedView": summary,
            "level": "SUMMARY",
            "language": language
        }
    elif level == "HIDDEN":
        # HIDDEN: only signatures, no imports or docstrings
        if language == "python":
            lines = source_code.split('\n')
            sig_lines = [l for l in lines
                         if l.lstrip().startswith(('class ', 'def ', 'async def '))]
            hidden = '\n'.join(sig_lines) if sig_lines else "# no signatures found"
        elif language in ("typescript", "javascript"):
            lines = source_code.split('\n')
            sig_lines = [l for l in lines
                         if re.match(r'^\s*(export\s+)?(async\s+)?function\s+\w+', l.lstrip())
                         or l.lstrip().startswith(('interface ', 'type ', 'class '))]
            hidden = '\n'.join(sig_lines) if sig_lines else "# no signatures found"
        else:
            hidden = "# HIDDEN level not supported for " + language
        return {
            "compressedView": hidden,
            "level": "HIDDEN",
            "language": language
        }
    else:  # FULL
        return {
            "compressedView": source_code,
            "level": "FULL",
            "language": language
        }
