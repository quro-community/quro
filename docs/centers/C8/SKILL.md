---
type: CenterSkill
name: quro-center-C8
description: "Explore and maintain documentation for Quro semantic center C8 (MinHash LSH, Sink, 139 symbols). Loads parameters from metadata.json. SKILL.md is READ-ONLY — never self-patch."
version: 1.0.0
metadata:
  center_id: C8
  center_uuid: C8-a3b4c5d6
  archetype: sink
  size: 139
  entry_strategy: upstream-first
  coupled_centers: [C0, C1, C3]
  coupling_clusters: [SC70]
  entry_points:
    - "sym::MinHashLSH::lsh_engine::28"
    - "sym::MinHashLSH"
    - "sym::to_dict"
---

# C8: MinHash LSH (High Fan-in Sink)

> **READ-ONLY:** This file is a parameter snapshot. Do not self-patch.
> To update exploration strategy, write to `index.md` or `agent_logs.md`.

## Center Profile

| Parameter | Value |
|-----------|-------|
| Center ID | C8 |
| Archetype | sink |
| Size | 139 symbols |
| Entry strategy | upstream-first |
| Coupled centers | C0, C1, C3 |
| Coupling clusters | SC70 |
| Entry points | `sym::MinHashLSH::lsh_engine::28`, `sym::MinHashLSH`, `sym::to_dict` |
