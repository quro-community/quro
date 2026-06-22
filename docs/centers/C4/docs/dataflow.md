# C4 Dataflow — I/O & Filesystem Sink

## Primary Data Flows

### Flow 1: Path Resolution

```
Upstream Center  ──►  sym::Path
  (C0/C1/C2/C5)        │
                       ├──► Path resolution (join, resolve, parent)
                       ├──► Path validation
                       └──► Return resolved Path to caller
```

### Flow 2: File Existence Check

```
Upstream Center  ──►  sym::exists
  (C0/C1/C2/C5)        │
                       ├──► OS stat() call
                       ├──► Returns True/False
                       └──► Return result to caller
```

### Flow 3: File Metadata Info

```
Upstream Center  ──►  sym::info
  (C0/C1/C2/C5)        │
                       ├──► OS stat() call
                       ├──► Returns file metadata dict
                       └──► Return info to caller
```

### Flow 4: LDS Tool Initialization

```
Upstream Center  ──►  sym::_ensure_lds_tools
  (C0)                  │
                       ├──► Check LDS binary availability
                       ├──► Download/install if missing
                       └──► Return tool paths to caller
```

### Flow 5: Unix Socket Connection

```
Upstream Center  ──►  sym::open_unix_connection
  (C0/C5)               │
                       ├──► Create Unix socket
                       ├──► Establish connection
                       └──► Return connection handle to caller
```

## Cross-Center Data Flow

```
C0 (Orchestration Hub) ──► C4: Path, exists, info, _ensure_lds_tools, open_unix_connection
C1 (Fanout)            ──► C4: Path, exists, info
C2 (Fanout)            ──► C4: Path, exists
C5 (Hub, SC1 cluster)  ──► C4: Path, info, open_unix_connection
```

**Direction:** All flows are **inward** (upstream centers → C4). C4 is a pure sink — it does not emit flows to other centers.

## Data Ownership

| Data | Owner | Format | Location |
|------|-------|--------|----------|
| File paths | C4 Callers | pathlib.Path | Filesystem |
| File metadata | C4 Callers | Dict | In-memory |
| LDS tool state | C4 | Binary/config | Filesystem |
| Unix sockets | C4 | Socket | /tmp/.quro/ |
