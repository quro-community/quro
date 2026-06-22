# C4 Dependencies — I/O & Filesystem Sink

## Internal Dependency Graph

```
sym::Path
    ├──► pathlib (stdlib)
    └──► os (stdlib)

sym::exists
    ├──► os.path (stdlib)
    └──► pathlib (stdlib)

sym::info
    ├──► os.stat (stdlib)
    ├──► pathlib (stdlib)
    └──► time (stdlib)

sym::_ensure_lds_tools
    ├──► subprocess (stdlib)
    ├──► os (stdlib)
    ├──► urllib / requests
    └──► pathlib (stdlib)

sym::open_unix_connection
    ├──► socket (stdlib)
    └──► pathlib (stdlib)
```

## Cross-Center Dependencies

### C0 (Core Orchestration Hub) — coupling score: 116.8
- **Usage:** C0 calls into C4 for path resolution, file I/O, and LDS tool setup

### C1 (Utility Layer) — coupling score: 124.2
- **Usage:** C1 uses C4 for filesystem path and existence operations

### C2 (Utility Layer) — coupling score: 41.1
- **Usage:** C2 uses C4 for lightweight path operations

### C5 (Hub — SC1 cluster) — coupling score: tight
- **Tight coupling cluster SC1** — C4 and C5 MUST change together
- **Shared concerns:** I/O paths, socket management, tool lifecycle

## External Dependencies

| Dependency | Usage | Scope |
|-----------|-------|-------|
| `pathlib` (stdlib) | Filesystem paths | Internal |
| `os` / `os.path` (stdlib) | File operations, stat | Internal |
| `socket` (stdlib) | Unix domain sockets | Internal |
| `subprocess` (stdlib) | LDS tool invocation | Internal |
| `time` (stdlib) | File timestamps | Internal |
| `urllib` / `requests` | LDS tool download | Internal |

## Dependency Direction

```
C0 ──► C4 ◄── C1
 │            │
 │            ▼
 └──► C4 ◄── C2
       │
       ▼
      C5 (SC1)
```

C4 is a **pure sink** — all edges point inward. Upstream centers (C0, C1, C2, C5) depend on C4 for I/O operations.
