# Quro — Categorical Knowledge System with CQE

> **Codebase is terrain. CQE is a map index. TDA is the topography.**

Quro is an AI-driven codebase analysis platform that models software projects as a **semantic topology** — mapping symbols, dependencies, and call patterns into a navigable knowledge graph. It powers LLM-native code exploration through topological data analysis (TDA) and a convergence-guaranteed CQE (Code Query Engine).

---

## 1. What Quro Does

Quro turns any codebase into a **semantic knowledge system** through a multi-phase pipeline:

```
Source Code
    │
    ▼
┌─────────────────────────────────────────────────┐
│  ① Scan (Phase 1)                               │
│  ├─ Extract symbols, types, imports, signatures  │
│  └─ Build symbol registry                        │
├─────────────────────────────────────────────────┤
│  ② Index & Enrich (Phase 1–2)                    │
│  ├─ Build CQE graph (weighted semantic edges)    │
│  ├─ MI scoring (mutual information)              │
│  ├─ Role classification (controller, worker, …)  │
│  ├─ Intent detection (I/O, network, db, …)       │
│  ├─ Path entropy & hub pressure analysis         │
│  └─ Hub normalization & pruning                  │
├─────────────────────────────────────────────────┤
│  ③ TDA Pipeline (Phase 2–3.5)                   │
│  ├─ Energy field computation                     │
│  ├─ Anisotropic field generation                 │
│  ├─ Attractor/repeller/saddle detection          │
│  ├─ Semantic center discovery                    │
│  └─ Codebase hologram construction               │
├─────────────────────────────────────────────────┤
│  ④ CQE Graph Evolution (iterative)               │
│  ├─ Fix Plan + Invariants repair cycle           │
│  ├─ Stability filtering & deduplication          │
│  └─ Converges to fixed point (proven)            │
├─────────────────────────────────────────────────┤
│  ⑤ Trajectory Planning (Phase 4)                 │
│  ├─ Start→Goal path planning                     │
│  ├─ Landing hints (selective entry points)       │
│  └─ Beam-search exploration                      │
├─────────────────────────────────────────────────┤
│  ⑥ AI Agent Interface (MCP)                      │
│  └─ 3-tool surface: landscape / navigate / lookup│
└─────────────────────────────────────────────────┘
```

### Concrete Outputs

| Output | Format | Description |
|--------|--------|-------------|
| `registry.db` | SQLite | Symbol registry with types, roles, intent tags |
| `cqe_index.db` | SQLite | CQE semantic graph (weighted edges, MI scores) |
| `tda_index.db` | SQLite | TDA analysis index |
| `quro_tda.duckdb` | DuckDB | TDA analytics warehouse |
| `tda/phase2/manifold_states.jsonl` | JSONL | Manifold state projections |
| `tda/phase2_5/anisotropic_fields.jsonl` | JSONL | Directional field vectors per symbol |
| `tda/phase2_5/edge_weights.json` | JSON | TDA-adjusted edge weights |
| `tda/phase2_5/structural_metrics.json` | JSON | Structural graph metrics |
| `tda/phase3_5/semantic_centers.json` | JSON | Automatically discovered semantic centers |
| `tda/phase3_5/codebase_hologram.json` | JSON | Global codebase structure hologram |
| `cqe_reflections.jsonl` | JSONL | CQE query reflection history for MI adjustment |
| `tda_mi_scores.json` | JSON | TDA-derived MI scores |

---

## 2. Quick Start

### 2.1 Requirements

* Python >= 3.11
* pip

### 2.2 Installation

```bash
# Clone the repository
git clone <repo-url> quro
cd quro

# Install Quro (Development Mode)
pip install -e ".[dev]"

# Or install runtime dependencies only
pip install -e .

```

### 2.3 CLI Usage

The `quro` CLI provides full functionality including scanning, TDA pipeline, semantic query, and path planning.

```bash
# Scan the current project and build the symbol index
quro scan

# Run the full TDA data pipeline (Required, takes a few minutes)
quro tda pipeline all

# CQE semantic query (Explore related symbols starting from a specific symbol)
quro cqe query sym::main --tau 0.1

# TDA path planning (Optimal semantic path from A to B)
quro tda plan sym::main sym::EventLogWriter --intent "find logging"

# Beam search exploration
quro tda explore sym::main --steps 5 --beam-width 5

# View the semantic center map
quro centers list
quro centers show C0

# View all commands
quro --help

```

### 2.4 MCP Server Usage

Integrate Quro as an MCP service in LLM clients (e.g., Claude Desktop, opencode):

```bash
# Method 1: stdio mode (MCP standard transport)
python -m quro_mcp

# Method 2: Set the project root directory
QURO_PROJECT_ROOT=/path/to/your/project python -m quro_mcp

```

**MCP Client Configuration Example** (e.g., `opencode.json` / `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "quro": {
      "command": "python",
      "args": ["-m", "quro_mcp"],
      "env": {
        "QURO_PROJECT_ROOT": "/path/to/your/project"
      }
    }
  }
}

```

Once started, the LLM can interact with Quro through 3 MCP tools:

| Tool | Functionality |
| --- | --- |
| `quro_landscape` | Code map overview: Routing recommendations, area overviews, coupling analysis, and attractor detection. |
| `quro_navigate` | Navigation between symbols: Next-step candidates, upstream sources, path planning, role classification, and field vectors. |
| `quro_lookup` | Symbol resolution: Check symbol/category details, lists, statistics, and CQE semantic queries. |

> **Tip**: Before the first use, you must run `quro scan` and `quro tda pipeline all` in the target project's root directory to build the index.

---

## 3. Scale & Scope

| Metric | Value |
|--------|-------|
| Python source files | ~240 |
| Lines of Python code | ~43,000 |
| Package directories | 51 |
| Semantic centers (C0–C8) | 9 |
| Total indexed symbols | ~3,500+ |
| Database engines | SQLite, DuckDB |
| External integrations | MCP (Model Context Protocol), CLI, asyncpg |

### Semantic Centers (Topology-Discovered Modules)

Quro is decomposed into **9 semantic centers** (C0–C8), each isolated by coupling analysis:

| Center | Archetype | Symbols | Role |
|--------|-----------|---------|------|
| **C0** | Hub | 919 | Core orchestration — `QuroV3Service`, pipeline coordination |
| **C1** | Fanout | 670 | Storage adapters, SQLite graph persistence, visualization |
| **C2** | Fanout | 624 | Traversal mode selection, flow observers, dict helpers |
| **C3** | Hub | 290 | Semantic analysis, CQE refinement, MCP dispatch, workspace scan |
| **C4** | Sink | 284 | Filesystem I/O, Unix socket connections, LDS tools |
| **C5** | Hub | 187 | Policy layer — path grammar, trust weights |
| **C6** | Chain | 176 | Symbol metadata, validation gates, structural tags |
| **C7** | Chain | 139 | Shadow/draft tooling, TypeScript analyzer lifecycle |
| **C8** | Sink | 139 | MinHash LSH indexing for code similarity search |

> Full center details: [docs/centers/](docs/centers/)

---

## 4. How Codebase Becomes a Landscape

```
Source Code                              Landscape (Topological Map)
===========                              ===========================

  .py files         ① AST Parse         semantic centers (C0–C9)
  imports           ──────────►         hub / fanout / chain / sink
  function defs     ② Symbol Extract    coupling scores
  class defs        ──────────►         tight-coupling clusters
  type annotations                       bridge symbols & shared sinks
       │             ③ Graph Build              │
       │             ──────────►                 │
       │             call edges +                │
       │             MI weights                  │
       │                    │                    │
       │             ④ TDA Pipeline              │
       │             ──────────►                 │
       │             energy fields               │
       │             anisotropic vectors         │
       │             attractor detection         │
       │             center partitioning         │
       │                    │                    │
       └────────────────────┘────────────────────┘
```

**Pipeline in plain words:**

1. **Scan** — AST parser walks every `.py` file, extracts symbols (functions, classes, methods), their types, signatures, imports, and call relationships.
2. **Graph** — Call edges become a directed graph. Mutual information (MI) scores weigh each edge: how much does knowing symbol A tell you about symbol B? Roles are classified (controller, worker, I/O, etc.) and intents tagged.
3. **TDA** — Topological Data Analysis treats the graph as a physical system: compute energy fields (analogous to potential energy in physics), anisotropic field vectors (directional "flow"), then detect attractors (hubs), repellers, and saddles. Semantic centers emerge by partitioning the graph at low-coupling boundaries.
4. **Landscape** — The result is a navigable map: 10 regions (C0–C9) with known archetypes, entry points, coupling scores, and traversal hints. The raw output below is what an LLM agent sees on first contact.

---

### Raw `quro_landscape` Output

<details>
<summary>Click to expand — full JSON returned by the MCP landscape tool</summary>

```json
{
  "routing": {
    "instruction": "Choose a region before reading code. Start with recommended region, then explore neighbors.",
    "recommended": [
      {
        "region": "C0",
        "reason": "Hub center with 3 entry points",
        "confidence": 0.95,
        "entry_points": [
          "sym::QuroV3Service::service::81",
          "sym::get_all_nodes::memory::108",
          "sym::enrich::types::55"
        ]
      }
    ]
  },
  "regions": [
    {
      "id": "C0", "role": "hub", "size": 793,
      "hint": "High fan-out hub: orchestration layer, start from top entry points and expand outward to callers"
    },
    {
      "id": "C1", "role": "fanout", "size": 666,
      "hint": "Leaf-dominated fanout: utility layer, expand outward from leaf entry points"
    },
    {
      "id": "C2", "role": "fanout", "size": 595,
      "hint": "Leaf-dominated fanout: utility layer, expand outward from leaf entry points"
    },
    {
      "id": "C3", "role": "hub", "size": 290,
      "hint": "High fan-out hub: orchestration layer, start from top entry points and expand outward to callers"
    },
    {
      "id": "C4", "role": "sink", "size": 284,
      "hint": "High fan-in sink: terminal layer, often I/O or persistence, navigate upstream first then converge"
    },
    {
      "id": "C5", "role": "hub", "size": 189,
      "hint": "High fan-out hub: orchestration layer, start from top entry points and expand outward to callers"
    },
    {
      "id": "C6", "role": "chain", "size": 162,
      "hint": "Balanced chain: transitional layer, traverse sequentially following the call chain"
    },
    {
      "id": "C7", "role": "chain", "size": 153,
      "hint": "Balanced chain: transitional layer, traverse sequentially following the call chain"
    },
    {
      "id": "C8", "role": "sink", "size": 148,
      "hint": "High fan-in sink: terminal layer, often I/O or persistence, navigate upstream first then converge"
    },
    {
      "id": "C9", "role": "fanout", "size": 74,
      "hint": "Leaf-dominated fanout: utility layer, expand outward from leaf entry points"
    }
  ],
  "structure": {
    "summary": "5 tight_coupling clusters detected, 5 cross-module. 36 coupled center pairs.",
    "clusters": [
      { "id": "SC1", "size": 632, "archetype": "tight_coupling", "centers": ["C4","C5"] },
      { "id": "SC38", "size": 821, "archetype": "tight_coupling", "centers": ["C0","C1","C3","C7","C9"] },
      { "id": "SC40", "size": 718, "archetype": "tight_coupling", "centers": ["C2","C8"] },
      { "id": "SC250", "size": 8, "archetype": "tight_coupling", "centers": [] },
      { "id": "SC886", "size": 5, "archetype": "tight_coupling", "centers": [] }
    ],
    "couplings": [
      { "center_a": "C0", "center_b": "C1", "score": 219.27, "mechanism": "10 bridge symbols flowing to 10 shared sinks" },
      { "center_a": "C0", "center_b": "C2", "score": 139.7 },
      { "center_a": "C0", "center_b": "C3", "score": 564.64 },
      { "center_a": "C0", "center_b": "C4", "score": 116.8 },
      { "center_a": "C0", "center_b": "C5", "score": 90.13 },
      { "center_a": "C0", "center_b": "C7", "score": 141.35 },
      { "center_a": "C0", "center_b": "C8", "score": 43.23 },
      { "center_a": "C0", "center_b": "C9", "score": 154.03 },
      { "center_a": "C1", "center_b": "C2", "score": 145.19 },
      { "center_a": "C1", "center_b": "C3", "score": 563.32 },
      { "center_a": "C1", "center_b": "C4", "score": 124.21 },
      { "center_a": "C1", "center_b": "C5", "score": 145.76 },
      { "center_a": "C1", "center_b": "C7", "score": 212.99 },
      { "center_a": "C1", "center_b": "C8", "score": 68.23 },
      { "center_a": "C1", "center_b": "C9", "score": 227.77 },
      { "center_a": "C2", "center_b": "C3", "score": 186.13 },
      { "center_a": "C2", "center_b": "C4", "score": 41.05 },
      { "center_a": "C2", "center_b": "C5", "score": 98.05 },
      { "center_a": "C2", "center_b": "C7", "score": 148.89 },
      { "center_a": "C2", "center_b": "C8", "score": 43.68 }
    ],
    "details_hint": "Use quro_landscape{center_id} or quro_navigate for deep exploration"
  },
  "total_symbols": 3354,
  "partition_coverage": 1.0
}
```

</details>

---

## 5. Key Algorithms & Guides

| Document | Description |
|----------|-------------|
| [TDA System Guide](docs/guides/tda-system-guide.md) | Topological Data Analysis — 3-layer architecture: Observation → Inference → Trajectory Planning |
| [TDA Physics & Math Theories](docs/guides/tda-physics-math-theories.md) | Differential geometry, energy models, and their code-navigation mappings |
| [Landing Hints Guide](docs/guides/landing-hints-guide.md) | Selective code entry points for efficient LLM traversal |
| [CQE Graph Convergence Proof (ZH)](docs/guides/ZH/cqe-graph-evolution-proof.md) | 收敛性证明 —— 为什么 CQE 修复系统不会无限循环 |
| [CQE Graph Convergence Proof (EN)](docs/guides/EN/cqe-graph-evolution-proof.md) | Convergence proof — why the CQE repair system always terminates |

---

## 6. License

This project is released under the **Unlicense** — free and unencumbered software released into the public domain.

See [LICENSE.txt](LICENSE.txt) for the full text.

---

## 7. Disclaimer

本软件按"原样"提供，不带有任何明示或暗示的担保。由于代码全由 AI 生成，作者未进行完备的生产环境测试。使用者需自行承担因运行本软件而导致的任何风险、损失或数据损坏。作者对代码的准确性、安全性和有效性不承担任何法律责任。

This software is provided "as is", without warranty of any kind, express or implied. Since all code is generated by AI, the authors have not performed comprehensive production testing. Users assume all risks, losses, or data corruption resulting from running this software. The authors assume no legal liability for the accuracy, security, or fitness of the code.

---

## 8. Acknowledgments

This project is entirely AI-driven. We thank the following large language models for providing core ideas, architectural design, and all code implementation (in no particular order):

- **Claude**
- **Gemini**
- **ChatGPT**
- **DeepSeek**
- **GLM**

Thank you to these technologies for their major contributions to this project.
