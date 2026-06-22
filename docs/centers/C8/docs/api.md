# C8 API Surface — MinHash LSH Sink

## Entry Points

### 1. `MinHashLSH` — `core/lsh/minhash.py:16`

Pure MinHash LSH kernel implementing `LSHKernel` protocol.

**TDA Role:** CONVERTER (forward_magnitude=2.41)

```python
class MinHashLSH:
    def __init__(self, config: LSHConfig):
        """Initialize with immutable config."""

    def compute_signature(self, tokens: Set[str]) -> LSHSignature:
        """Pure: tokens → LSH signature.
        Invariant: Same tokens → same signature (deterministic)."""

    def compute_similarity(self, sig1: LSHSignature, sig2: LSHSignature) -> float:
        """Pure: Jaccard similarity estimate ∈ [0.0, 1.0].
        Invariant: Symmetric."""

    # Internal (not part of protocol):
    def _hash_token(self, token: str) -> int: ...
    def _compute_minhash(self, token_hashes: List[int]) -> np.ndarray: ...
    def _compute_bands_from_signature(self, sig: np.ndarray) -> List[int]: ...
    def _hash_band(self, band_rows: np.ndarray) -> int: ...
    def _generate_hash_functions(self) -> List[Tuple[int, int]]: ...
```

### 2. `MinHashLSH` — `deprecated/quro_cli/analysis/lsh_engine.py:28`

Legacy MinHash LSH with broader API (used by CLI/MCP tools).

**TDA Role:** CONVERTER (forward_magnitude=8.76, in_degree=40, out_degree=30)

```python
class MinHashLSH:
    def __init__(self, config: Optional[LSHConfig] = None): ...
    def compute_minhash(self, tokens: Set[str]) -> np.ndarray: ...
    def compute_bands(self, signature: np.ndarray) -> List[int]: ...
    def jaccard_similarity(self, sig1: np.ndarray, sig2: np.ndarray) -> float: ...
    def signature_to_bytes(self, signature: np.ndarray) -> bytes: ...
    def signature_from_bytes(self, signature_bytes: bytes) -> np.ndarray: ...
    def compute_signature(self, text: str) -> bytes: ...
    def get_band_hashes(self, signature_bytes: bytes) -> List[int]: ...
    def tokenize_code(self, code: str) -> Set[str]: ...
    def extract_behavioral_tags(self, code: str, language: str = "python") -> Set[str]: ...
    def _hash_token(self, token: str) -> int: ...
    def _hash_band(self, band_rows: np.ndarray) -> int: ...
    def _generate_hash_functions(self) -> List[Tuple[int, int]]: ...
```

### 3. `to_dict` — `pipeline/cqe/stability.py:35`

Serialization helper on `StabilityState`.

**TDA Role:** TRANSIENT (forward_magnitude=0.0, out_degree=0)

```python
class StabilityState:
    def to_dict(self) -> dict:
        """Serialize state to JSON-compatible dict.
        Returns {applied_hashes, node_modified_counts, last_entropy_score, entropy_history}"""
```

## Supporting Types

### `LSHConfig` — `core/lsh/types.py:13` (immutable dataclass)

```python
@dataclass(frozen=True)
class LSHConfig:
    num_hashes: int = 128
    num_bands: int = 16
    threshold: float = 0.3
    @property
    def rows_per_band(self) -> int: ...
```

### `LSHSignature` — `core/lsh/types.py:44` (immutable dataclass)

```python
@dataclass(frozen=True)
class LSHSignature:
    hash_values: np.ndarray  # Shape: (num_hashes,), dtype: uint32
    bands: List[int]          # Band hashes (one per band)
    config: LSHConfig         # Config used to generate
    def to_bytes(self) -> bytes: ...
    @staticmethod
    def from_bytes(signature_bytes: bytes, config: LSHConfig) -> "LSHSignature": ...
```

### `LSHKernel` — `core/lsh/kernel.py:11` (Protocol)

```python
class LSHKernel(Protocol):
    def compute_signature(self, tokens: Set[str]) -> LSHSignature: ...
    def compute_similarity(self, sig1: LSHSignature, sig2: LSHSignature) -> float: ...
```

### `LSHIndex` — `deprecated/quro_cli/analysis/lsh_engine.py:334`

```python
class LSHIndex:
    def __init__(self, lsh_engine: MinHashLSH): ...
    def insert(self, item_id: str, signature: np.ndarray) -> None: ...
    def query(self, signature, threshold=None) -> List[Tuple[str, float]]: ...
    def remove(self, item_id: str) -> None: ...
    def size(self) -> int: ...
```

### `LSHOrchestrator` — `orchestrators/lsh.py:17`

```python
class LSHOrchestrator:
    def __init__(self, manifold_adapter, config=None): ...
    async def compute_and_store(self, symbol, content, metadata) -> ManifoldNode: ...
    async def compute_similarity(self, symbol_a, symbol_b) -> float: ...
    async def find_similar(self, symbol, threshold=0.7, limit=10) -> Tuple: ...
```

## CLI Entry Points

### `generate_minhash_for_all_symbols` — `lsh_engine.py:454`

```python
async def generate_minhash_for_all_symbols(db_url: str, batch_size: int = 100):
    """Generate MinHash signatures for all symbols in PostgreSQL database."""
```

### `main` — `lsh_engine.py:613`

```python
async def main():
    """CLI entry point: --db-url, --batch-size"""
```
