---
type: CenterSkill
name: quro-center-C0
description: "Explore and maintain documentation for Quro semantic center C0 (Core Orchestration Layer, Hub, 919 symbols). Loads parameters from metadata.json. SKILL.md is READ-ONLY — never self-patch."
version: 1.0.0
metadata:
  center_id: C0
  center_uuid: C0-a1b2c3d4
  archetype: hub
  size: 919
  entry_strategy: top-down
  coupled_centers: [C1, C3, C4, C5, C6, C7, C8]
  coupling_clusters: [SC70]
  entry_points:
    - "sym::QuroV3Service::service::81"
    - "sym::enrich::types::55"
    - "sym::get_all_nodes::memory::108"
---

# C0: Core Orchestration Layer

> **READ-ONLY:** This file is a parameter snapshot. Do not self-patch.
> To update exploration strategy, write to `index.md` or `agent_logs.md`.

## Center Profile

| Parameter | Value |
|-----------|-------|
| Center ID | C0 |
| Archetype | hub |
| Size | 919 symbols |
| Entry strategy | top-down |
| Coupled centers | C1, C3, C4, C5, C6, C7, C8 |
| Coupling clusters | SC70 |
| Entry points | `sym::QuroV3Service::service::81`, `sym::enrich::types::55`, `sym::get_all_nodes::memory::108` |
