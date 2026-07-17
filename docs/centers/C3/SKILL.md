---
type: CenterSkill
name: quro-center-C3
description: "Explore and maintain documentation for Quro semantic center C3 (Semantic Analysis and CQE Refinement Hub, hub, 290 symbols). Loads parameters from metadata.json. SKILL.md is READ-ONLY — never self-patch."
version: 1.0.0
metadata:
  center_id: C3
  center_uuid: C3-e5f7a2b9
  archetype: hub
  size: 290
  entry_strategy: top-down
  coupled_centers: [C0, C1, C2, C4, C5, C6, C7, C8, C9]
  coupling_clusters: [SC38]
  entry_points:
    - "sym::classify_node_role::upstream_navigator::325"
    - "sym::SemanticCQERefiner::refiner::128"
    - "sym::GateResult::types::13"
    - "sym::call_tool"
    - "sym::scan_workspace"
---

# C3: Semantic Analysis and CQE Refinement Hub

> **READ-ONLY:** This file is a parameter snapshot. Do not self-patch.
> To update exploration strategy, write to `index.md` or `agent_logs.md`.

## Center Profile

| Parameter | Value |
|-----------|-------|
| Center ID | C3 |
| Archetype | hub |
| Size | 290 symbols |
| Entry strategy | top-down |
| Coupled centers | C0, C1, C2, C4, C5, C6, C7, C8, C9 |
| Coupling clusters | SC38 |
| Entry points | `sym::classify_node_role::upstream_navigator::325`, `sym::SemanticCQERefiner::refiner::128`, `sym::GateResult::types::13`, `sym::call_tool`, `sym::scan_workspace` |
