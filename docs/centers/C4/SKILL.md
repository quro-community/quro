---
name: quro-center-C4
description: "Explore and maintain documentation for Quro semantic center C4 (High fan-in sink: terminal layer, often I/O or persistence, 284 symbols). Loads parameters from metadata.json. SKILL.md is READ-ONLY — never self-patch."
version: 1.0.0
metadata:
  center_id: C4
  center_uuid: C4-ce2d9b151581
  archetype: sink
  size: 284
  entry_strategy: converge_inward
  coupled_centers: [C0, C1, C2, C5]
  coupling_clusters: [SC1]
  entry_points:
    - "sym::Path"
    - "sym::exists"
    - "sym::info"
    - "sym::_ensure_lds_tools"
    - "sym::open_unix_connection"
---

# C4: I/O & Filesystem Sink

> **READ-ONLY:** This file is a parameter snapshot. Do not self-patch.
> To update exploration strategy, write to `index.md` or `agent_logs.md`.

## Center Profile

| Parameter | Value |
|-----------|-------|
| Center ID | C4 |
| Archetype | sink |
| Size | 284 symbols |
| Entry strategy | converge_inward |
| Coupled centers | C0, C1, C2, C5 |
| Coupling clusters | SC1 (tight with C5) |
| Entry points | `sym::Path`, `sym::exists`, `sym::info`, `sym::_ensure_lds_tools`, `sym::open_unix_connection` |
