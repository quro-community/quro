---
type: CenterSkill
name: quro-center-C2
description: "Explore and maintain documentation for Quro semantic center C2 (Leaf-dominated fanout: utility layer, 624 symbols). Loads parameters from metadata.json. SKILL.md is READ-ONLY — never self-patch."
version: 1.0.0
metadata:
  center_id: C2
  center_uuid: C2-d03c60e4
  archetype: fanout
  size: 624
  entry_strategy: bottom-up
  coupled_centers: [C0]
  coupling_clusters: []
  entry_points:
    - "sym::select_traversal_mode"
    - "sym::FlowObserver::flow_observer::53"
    - "sym::to_dict::flow_observer::37"
---

# C2: Leaf-dominated Fanout — Utility Layer

> **READ-ONLY:** This file is a parameter snapshot. Do not self-patch.
> To update exploration strategy, write to `index.md` or `agent_logs.md`.

## Center Profile

| Parameter | Value |
|-----------|-------|
| Center ID | C2 |
| Archetype | fanout |
| Size | 624 symbols |
| Entry strategy | bottom-up |
| Coupled centers | C0 |
| Coupling clusters | none |
| Entry points | `sym::select_traversal_mode`, `sym::FlowObserver::flow_observer::53`, `sym::to_dict::flow_observer::37` |
