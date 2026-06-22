"""Scanner v3 - Core Types

@module quro.scanner.types
@intent Immutable data structures for scanner pipeline
@constraint No I/O, no side effects, frozen dataclasses
"""

from dataclasses import dataclass, field
from typing import Tuple, Optional, Dict, Any


@dataclass(frozen=True)
class ParsedSymbol:
    """Pure symbol data extracted from AST.

    Immutable representation of a code symbol (function, class, method, variable).
    No I/O, no mutations - pure data.
    """

    name: str
    """Symbol name (e.g., 'LockManager', 'acquire')"""

    kind: str
    """Symbol kind: 'function' | 'async_function' | 'class' | 'method' | 'async_method' | 'variable'"""

    file_path: str
    """Relative file path from workspace root"""

    line: int
    """Line number (1-indexed)"""

    char: int
    """Character offset (0-indexed)"""

    signature: Optional[str] = None
    """Function/method signature (e.g., 'def foo(x: int) -> str')"""

    calls: Tuple[str, ...] = ()
    """Symbol names called by this symbol"""

    imports: Tuple[str, ...] = ()
    """Import paths (e.g., 'asyncio', 'pathlib.Path')"""

    decorators: Tuple[str, ...] = ()
    """Decorator names (e.g., '@staticmethod', '@dataclass')"""

    docstring: Optional[str] = None
    """Docstring text (first line only for brevity)"""

    ast_kind: Optional[str] = None
    """Raw AST node kind (e.g., 'FunctionDef', 'AsyncFunctionDef')"""


@dataclass(frozen=True)
class SymbolFeatures:
    """Behavioral features extracted from symbol.

    Tags used for semantic categorization and CQE indexing.
    """

    behavioral_tags: Tuple[str, ...] = ()
    """Behavioral tags (e.g., 'async', 'lock', 'raii', 'network')"""

    structural_tags: Tuple[str, ...] = ()
    """Structural tags (e.g., 'entry_point', 'factory', 'singleton')"""

    risk_anchors: Tuple[str, ...] = ()
    """Risk patterns (e.g., 'orphan_lock', 'unguarded_await')"""

    lsh_signature: Optional[str] = None
    """MinHash LSH signature (128-band)"""


@dataclass(frozen=True)
class SymbolInfo:
    """Enriched symbol with features.

    Combines ParsedSymbol + SymbolFeatures for pipeline processing.
    """

    symbol: ParsedSymbol
    """Core symbol data"""

    features: SymbolFeatures
    """Extracted features"""

    fingerprint: str
    """Content-based fingerprint (SHA256)"""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Optional metadata (file size, language, etc.)"""


@dataclass(frozen=True)
class FileInfo:
    """File metadata for scanner output."""

    file_path: str
    """Relative file path from workspace root"""

    language: str
    """Language: 'python' | 'typescript' | 'javascript'"""

    fingerprint: str
    """File content fingerprint (SHA256)"""

    size_bytes: int
    """File size in bytes"""

    symbol_count: int
    """Number of symbols extracted"""

    scan_time_ms: float
    """Time taken to scan this file (milliseconds)"""


@dataclass(frozen=True)
class ScanResult:
    """Result of scanning a single file.

    Immutable result containing all extracted data.
    """

    file_info: FileInfo
    """File metadata"""

    symbols: Tuple[SymbolInfo, ...] = ()
    """Extracted symbols"""

    edges: Tuple[Tuple[str, str, str], ...] = ()
    """Call graph edges: (from_symbol, to_symbol, edge_kind)"""

    errors: Tuple[str, ...] = ()
    """Parse errors encountered"""
