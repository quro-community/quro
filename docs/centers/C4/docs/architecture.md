# C4 Architecture — I/O & Filesystem Sink

## Overview

Center C4 is a **sink** archetype (284 symbols) that provides the **filesystem and I/O terminal layer** for the Quro codebase. It serves as the convergence point for all file system operations (path resolution, existence checks, metadata queries), LDS tool initialization, and Unix socket connections.

C4 sits in a tight coupling cluster **SC1** with C5 (must change together) and is coupled to C0 (116.8), C1 (124.2), C2 (41.1).

## Layer Architecture

```
      C0 (Hub) ────┐
      C1 (Fanout) ──┤
      C2 (Fanout) ──┤
      C5 (Hub) ─────┤
                    │
                    ▼
┌─────────────────────────────────────┐
│         Entry Layer                 │
│  Path │ exists │ info │             │
│  _ensure_lds_tools                  │
│  open_unix_connection               │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│     Filesystem Operations           │
│  Path resolution                    │
│  Existence checks                   │
│  File metadata (stat, info)         │
│  Directory listing                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│     IPC / Tool Init                 │
│  LDS tool bootstrap                 │
│  Unix socket connection             │
│  Process management                 │
└─────────────────────────────────────┘
```

## Component Breakdown

### 1. Entry Points
| Symbol | Role | Description |
|--------|------|-------------|
| `sym::Path` | SINK | Pathlib filesystem path abstraction |
| `sym::exists` | SINK | File/directory existence check |
| `sym::info` | SINK | File metadata info retrieval |
| `sym::_ensure_lds_tools` | SINK | LDS tool initialization and setup |
| `sym::open_unix_connection` | SINK | Unix domain socket connection |

### 2. Filesystem Layer
- **Path** — Wraps `pathlib.Path` for filesystem path operations (join, resolve, parent, etc.)
- **exists** — Checks if a path exists on the filesystem
- **info** — Retrieves file metadata (size, mtime, permissions, type)

### 3. IPC / Tool Init Layer
- **_ensure_lds_tools** — Bootstraps LDS (Language Development System) tooling, ensuring required binaries and configurations are available
- **open_unix_connection** — Opens a Unix domain socket connection for inter-process communication

## Coupling Context

- **C0** (score 116.8): Core orchestration hub flowing into C4 for file I/O
- **C1** (score 124.2): Utility layer flowing into C4 for filesystem operations
- **C2** (score 41.1): Utility layer with lighter filesystem dependency
- **C5** (score via SC1): Tight coupling cluster SC1 — must change together
