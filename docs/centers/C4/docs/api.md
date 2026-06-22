# C4 API Surface — I/O & Filesystem Sink

## Entry Points

### `Path`
- **Role:** SINK
- **Description:** Pathlib filesystem path abstraction. Supports join, resolve, parent, exists, and other path operations.
- **Returns:** `pathlib.Path` object

### `exists`
- **Role:** SINK
- **Description:** Checks whether a file or directory exists at the given path.
- **Signature:** `exists(path: str | Path) -> bool`

### `info`
- **Role:** SINK
- **Description:** Retrieves file metadata (size, modification time, permissions, type).
- **Signature:** `info(path: str | Path) -> Dict[str, Any]`
- **Returns:** Dict with keys: `size`, `mtime`, `mode`, `type`, `is_dir`, `is_file`

### `_ensure_lds_tools`
- **Role:** SINK
- **Description:** Ensures LDS (Language Development System) tools are available. Downloads/installs if missing.
- **Signature:** `_ensure_lds_tools() -> Dict[str, str]`
- **Returns:** Dict mapping tool names to binary paths

### `open_unix_connection`
- **Role:** SINK
- **Description:** Opens a Unix domain socket connection.
- **Signature:** `open_unix_connection(path: str | Path) -> socket`
- **Returns:** Connected socket object

## Key Symbols with TDA Roles

| Symbol | Role | Description |
|--------|------|-------------|
| Path | SINK | Filesystem path abstraction |
| exists | SINK | File existence check |
| info | SINK | File metadata retrieval |
| _ensure_lds_tools | SINK | LDS tool initialization |
| open_unix_connection | SINK | Unix socket connection |
