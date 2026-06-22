# C4 Entry Points — I/O & Filesystem Sink

## Entry Point Summary

| # | Symbol | Role | Strategy |
|---|--------|------|----------|
| 1 | `sym::Path` | SINK | converge_inward |
| 2 | `sym::exists` | SINK | converge_inward |
| 3 | `sym::info` | SINK | converge_inward |
| 4 | `sym::_ensure_lds_tools` | SINK | converge_inward |
| 5 | `sym::open_unix_connection` | SINK | converge_inward |

---

## Entry Point 1: `sym::Path`

**Role:** SINK

**Description:** Pathlib filesystem path abstraction. Provides path manipulation (join, resolve, parent, name, suffix, stem), path validation, and iteration operations. Used ubiquitously across the codebase for filesystem interaction.

**Upstream Callers:** C0, C1, C2, C5

---

## Entry Point 2: `sym::exists`

**Role:** SINK

**Description:** Checks whether a file or directory exists at the given path. Wraps `os.path.exists()` and `pathlib.Path.exists()`.

**Upstream Callers:** C0, C1, C2, C5

---

## Entry Point 3: `sym::info`

**Role:** SINK

**Description:** Retrieves file metadata including size, modification time, permissions, and file type. Wraps `os.stat()` and provides structured output.

**Upstream Callers:** C0, C1, C5

---

## Entry Point 4: `sym::_ensure_lds_tools`

**Role:** SINK

**Description:** Ensures LDS (Language Development System) tools are available and properly configured. Checks for required binaries, downloads them if missing, and returns tool paths.

**Upstream Callers:** C0

---

## Entry Point 5: `sym::open_unix_connection`

**Role:** SINK

**Description:** Opens a Unix domain socket connection for inter-process communication. Creates the socket, connects to the specified path, and returns the connected socket handle.

**Upstream Callers:** C0, C5

---

## Discovery Strategy for C4 (Sink Archetype)

Since C4 is a **sink** archetype, exploration follows a **converge_inward** strategy:

1. **Identify upstream callers** — trace backward from sink entry points to find all callers
2. **Map convergence paths** — document which upstream centers flow into each entry point
3. **Document boundary contracts** — record the I/O interfaces and their contracts
4. **No outward expansion** — sink symbols typically have no significant callees within the center

### Priority Upstream Centers to Trace

| Priority | Center | Coupling Score | Entry Points Used |
|----------|--------|---------------|-------------------|
| 1 | C0 | 116.8 | Path, exists, info, _ensure_lds_tools, open_unix_connection |
| 2 | C1 | 124.2 | Path, exists, info |
| 3 | C5 | SC1 (tight) | Path, info, open_unix_connection |
| 4 | C2 | 41.1 | Path, exists |
