# Landing Hints - Quick Reference Guide

**For**: Developers and AI agents using Quro TDA navigation  
**Purpose**: Understand how to use landing hints to quickly find relevant code

---

## What Are Landing Hints?

Landing hints are **selective code entry points** that guide you to the most important symbols in a TDA trajectory path. Instead of reading all files in a path, landing hints tell you which 2-3 symbols are most worth inspecting.

---

## How to Use Landing Hints

### 1. Query a Trajectory

```python
from quro_v3.tda.phase4.trajectory_planner import TrajectoryPlanner, TrajectoryRequest

planner = TrajectoryPlanner(tda_path)
request = TrajectoryRequest(
    start='sym::scan',
    goal='sym::execute',
    intent='understand scan to execute flow'
)
plan = planner.plan_trajectory(request)
```

### 2. Check Landing Hints

```python
if plan and plan.landing_hints:
    for hint in plan.landing_hints:
        print(f"Check: {hint['file']}:{hint['line']}")
        print(f"Why: {', '.join(hint['why_here'])}")
```

### 3. Read Only the Suggested Files

Instead of reading all files in the path, focus on the top-ranked hints:

```python
# Top hint is most important
top_hint = plan.landing_hints[0]
# Read this file first: top_hint['file'] at line top_hint['line']
```

---

## Understanding the Output

### Landing Hint Structure

```json
{
  "symbol": "sym::build_offline_index",
  "file": "quro_sovereign/cqe_index_pipeline.py",
  "line": 315,
  "priority": 0.87,
  "why_here": ["high_energy", "high_fanout", "convergence_point"]
}
```

### Fields

- **symbol**: Symbol ID from the path
- **file**: Absolute path to the source file
- **line**: Line number where symbol is defined
- **priority**: Score [0, 1+] indicating importance (higher = more important)
- **why_here**: List of reasons why this symbol is worth inspecting

### Reasons Explained

| Reason | Meaning | Threshold |
|--------|---------|-----------|
| `high_energy` | High semantic importance in the graph | Energy > 1.3× average |
| `high_fanout` | Central hub with many outgoing connections | Out-degree > 15 |
| `convergence_point` | Bottleneck where many paths converge | In/out ratio > 2.0 |
| `early_path` | Near the start of the trajectory | Position ≤ 2 |

---

## Workflow Examples

### Example 1: Understanding a Pipeline

**Goal**: Understand how the indexing pipeline works

```python
request = TrajectoryRequest(
    start='sym::CQEIndexPipeline',
    goal='sym::build_offline_index',
    intent='understand indexing pipeline'
)
plan = planner.plan_trajectory(request)

# Landing hints tell you:
# 1. Start at build_offline_index (high_energy, high_fanout)
# 2. Then check AliasMergeEngine (convergence_point)
# 3. Skip the rest unless needed
```

**Result**: Read 2 files instead of 10+

---

### Example 2: Debugging a Bug

**Goal**: Find where a bug originates

```python
request = TrajectoryRequest(
    start='sym::error_handler',
    goal='sym::root_cause',
    intent='trace error to source'
)
plan = planner.plan_trajectory(request)

# Landing hints prioritize:
# - High energy nodes (likely important logic)
# - Convergence points (where errors aggregate)
# - Early path nodes (closer to root cause)
```

**Result**: Faster bug localization

---

### Example 3: Code Review

**Goal**: Review changes in a feature branch

```python
request = TrajectoryRequest(
    start='sym::new_feature_entry',
    goal='sym::core_logic',
    intent='review feature implementation'
)
plan = planner.plan_trajectory(request)

# Landing hints show:
# - Critical integration points (high_fanout)
# - Core logic nodes (high_energy)
# - Skip boilerplate and utilities
```

**Result**: Focus review on high-impact code

---

## Best Practices

### ✅ Do

1. **Trust the top hint** - It's usually the most important
2. **Read reasons** - They explain why a node matters
3. **Use as guidance** - Not strict rules
4. **Combine with path** - Hints are selected from the path

### ❌ Don't

1. **Don't ignore the path** - Hints are a subset, not a replacement
2. **Don't assume execution order** - Hints are ranked by importance, not call order
3. **Don't expect 100% coverage** - Hints are selective by design
4. **Don't treat as ground truth** - Always verify in actual code

---

## Integration with MCP

### MCP Tool: `tda_plan_trajectory`

```json
{
  "start": "sym::scan",
  "goal": "sym::execute",
  "intent": "understand scan to execute flow"
}
```

**Response includes**:
```json
{
  "path": [...],
  "total_energy": 1.20,
  "coherence": 0.85,
  "landing_hints": [
    {
      "symbol": "sym::scan",
      "file": "quro_cli/scanner.py",
      "line": 295,
      "priority": 0.792,
      "why_here": ["high_fanout", "early_path"]
    }
  ]
}
```

---

## Troubleshooting

### No Landing Hints Returned

**Possible causes**:
1. No path found between start and goal
2. Path is empty
3. Symbols not in field data

**Solution**: Check that `plan` is not None and `plan.path` is not empty

### File Shows "unknown:0"

**Cause**: Symbol metadata not found in registry database

**Solution**: 
- Ensure registry.db is up to date
- Re-run indexing if needed
- Symbol may be synthetic (not in source code)

### Priority Scores Seem Low

**Normal**: Scores typically range 0.4-0.9

**High scores (>0.8)**: Very important nodes  
**Medium scores (0.5-0.8)**: Important nodes  
**Low scores (<0.5)**: Less critical nodes

---

## Performance Notes

- **Computation**: <5ms per trajectory
- **Token overhead**: ~150 tokens per hint (3 hints = ~450 tokens)
- **Database queries**: 1 query per symbol (cached)
- **Memory**: <1KB per trajectory

---

## Related Documentation

- [Design 98: Landing Hint System](./98-Design-Landing-Hint-System.md)
- [Implementation Summary](./98-Implementation-Summary.md)
- [CLAUDE.md: Semantic Graph Interpretation Guide](../../CLAUDE.md)

---

## Quick Tips

💡 **Start with the top hint** - It has the highest priority for a reason

💡 **Check reasons** - They explain the scoring rationale

💡 **Use with path context** - Hints are most useful when you understand the overall trajectory

💡 **Iterate if needed** - If top hints don't help, check the next ones or read the full path

💡 **Combine with grep** - Use hints to narrow down, then grep for specific patterns
