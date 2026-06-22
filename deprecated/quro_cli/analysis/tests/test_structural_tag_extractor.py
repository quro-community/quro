"""
Tests for StructuralTagExtractor — Design 55: deterministic atom foundation.

Covers all 17 category tokens, role inference, merge logic, and edge cases.
"""

import pytest

from quro_cli.analysis.structural_tag_extractor import (
    ROLE_CONFIGURATION,
    ROLE_CONTAINER,
    ROLE_COORDINATOR,
    ROLE_CORE_INFRASTRUCTURE,
    ROLE_IO_HANDLER,
    ROLE_RESOURCE_MANAGER,
    ROLE_TRANSFORMER,
    ROLE_UNKNOWN,
    StructuralTags,
    extract_tags,
    merge_with_llm_tags,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def empty_source() -> str:
    return "pass"


@pytest.fixture
def async_source() -> str:
    return """
async def fetch_data():
    result = await client.get('/api/data')
    return result.json()
"""


# ── Category token detection tests ────────────────────────────────────────────


class TestAsyncDetection:
    """async tag from kind and from await keyword."""

    def test_from_kind_async_function(self, empty_source: str) -> None:
        result = extract_tags(kind="async_function", source_code=empty_source)
        assert "async" in result.tags

    def test_from_await_keyword(self) -> None:
        result = extract_tags(
            kind="function",
            source_code="data = await fetch()",
        )
        assert "async" in result.tags

    def test_absent_when_no_signal(self, empty_source: str) -> None:
        result = extract_tags(kind="function", source_code=empty_source)
        assert "async" not in result.tags


class TestLockDetection:
    """lock tag from threading/asyncio lock primitives."""

    def test_asyncio_lock(self) -> None:
        result = extract_tags(source_code="self._lock = asyncio.Lock()")
        assert "lock" in result.tags

    def test_threading_lock(self) -> None:
        result = extract_tags(source_code="lock = threading.Lock()")
        assert "lock" in result.tags

    def test_rlock(self) -> None:
        result = extract_tags(source_code="mutex = RLock()")
        assert "lock" in result.tags

    def test_semaphore(self) -> None:
        result = extract_tags(source_code="sem = Semaphore(10)")
        assert "lock" in result.tags


class TestRAIIDetection:
    """raii tag from context manager protocol."""

    def test_enter_exit(self) -> None:
        result = extract_tags(
            kind="class",
            source_code="class Foo:\n    def __enter__(self): pass\n    def __exit__(self, *a): pass",
        )
        assert "raii" in result.tags

    def test_with_self(self) -> None:
        result = extract_tags(
            kind="class",
            source_code="class Foo:\n    def bar(self):\n        with self:",
        )
        assert "raii" in result.tags


class TestErrorDetection:
    """error tag from exception handling."""

    @pytest.mark.parametrize("snippet", [
        "try:\n    pass\nexcept ValueError:",
        "raise RuntimeError('oops')",
        "try:",
        "except Exception as e:",
        "import traceback",
    ])
    def test_error_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "error" in result.tags


class TestDatabaseDetection:
    """database tag from DB library usage."""

    @pytest.mark.parametrize("snippet", [
        "import asyncpg",
        "import psycopg",
        "from sqlalchemy import Column",
        "cursor.execute('SELECT * FROM users')",
        "cursor.execute('INSERT INTO')",
        "with transaction():",
    ])
    def test_database_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "database" in result.tags


class TestNetworkDetection:
    """network tag from HTTP/socket libraries."""

    @pytest.mark.parametrize("snippet", [
        "requests.get(url)",
        "httpx.AsyncClient()",
        "aiohttp.ClientSession()",
        "socket.socket()",
        "import urllib.request",
        "sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
    ])
    def test_network_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "network" in result.tags


class TestFilesystemDetection:
    """filesystem tag from path/file operations."""

    @pytest.mark.parametrize("snippet", [
        "Path('/tmp/data')",
        "content = file.read_text()",
        "file.write_text(data)",
        "os.path.exists(path)",
        "shutil.copytree(src, dst)",
    ])
    def test_filesystem_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "filesystem" in result.tags


class TestHashDetection:
    """hash tag from hashlib/checksum operations."""

    @pytest.mark.parametrize("snippet", [
        "hashlib.sha256(data).hexdigest()",
        "h = hashlib.md5()",
        "compute_checksum(data)",
        "digest = h.digest()",
    ])
    def test_hash_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "hash" in result.tags


class TestParseDetection:
    """parse tag from parsing/tokenization libraries."""

    @pytest.mark.parametrize("snippet", [
        "ast.parse(source)",
        "re.compile(pattern)",
        "tokenize.generate_tokens()",
        "json.loads(raw)",
        "yaml.safe_load(stream)",
    ])
    def test_parse_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "parse" in result.tags


class TestSecurityDetection:
    """security tag from auth/crypto patterns."""

    @pytest.mark.parametrize("snippet", [
        "verify_auth(token)",
        "encrypt(data, key)",
        "decrypt(ciphertext, key)",
        "hashlib.sha256(password)",
        "validate_password(pwd)",
        "bearer_token = request.headers.get('token')",
    ])
    def test_security_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "security" in result.tags


class TestSignalDetection:
    """signal tag from OS signal handling."""

    @pytest.mark.parametrize("snippet", [
        "signal.signal(signal.SIGINT, handler)",
        "signal.signal(signal.SIGTERM, cleanup)",
        "atexit.register(cleanup)",
    ])
    def test_signal_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "signal" in result.tags


class TestIOBoundDetection:
    """io_bound tag from IO-heavy patterns."""

    @pytest.mark.parametrize("snippet", [
        "import aiofiles",
        "data = file.read_text()",
        "file.write_text(content)",
        "stream = response.stream()",
        "buf = memoryview.buffer",
    ])
    def test_io_bound_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "io_bound" in result.tags


class TestVRAMControlDetection:
    """vram_control tag from Ollama/GPU patterns."""

    @pytest.mark.parametrize("snippet", [
        "vram_usage = check_vram()",
        "loadModel('qwen3.5')",
        "unloadModel('qwen3.5')",
        "GPU compute",
        "ollama.list()",
    ])
    def test_vram_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "vram_control" in result.tags


class TestAtomicDetection:
    """atomic tag from concurrency primitives."""

    @pytest.mark.parametrize("snippet", [
        "Lock()",
        "RLock()",
        "Event()",
        "Condition()",
        "atomic_operation()",
    ])
    def test_atomic_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "atomic" in result.tags


class TestGeneratorDetection:
    """generator tag from yield keyword."""

    def test_yield(self) -> None:
        result = extract_tags(source_code="def gen():\n    yield 1\n    yield 2")
        assert "generator" in result.tags

    def test_no_yield(self, empty_source: str) -> None:
        result = extract_tags(source_code=empty_source)
        assert "generator" not in result.tags


class TestDecoratorDetection:
    """decorator tag from AST decorator field."""

    def test_has_decorator(self) -> None:
        result = extract_tags(decorators=["staticmethod"])
        assert "decorator" in result.tags

    def test_no_decorator(self) -> None:
        result = extract_tags(decorators=[])
        assert "decorator" not in result.tags

    def test_none_decorator(self) -> None:
        result = extract_tags(decorators=None)
        assert "decorator" not in result.tags

    def test_empty_string_decorator_filtered(self) -> None:
        result = extract_tags(decorators=["", "  "])
        assert "decorator" not in result.tags


class TestMemoryDetection:
    """memory tag from memory management patterns."""

    @pytest.mark.parametrize("snippet", [
        "ptr = malloc(1024)",
        "free(ptr)",
        "gc.collect()",
        "weakref.ref(obj)",
        "mmap.mmap(fd, size)",
    ])
    def test_memory_signals(self, snippet: str) -> None:
        result = extract_tags(source_code=snippet)
        assert "memory" in result.tags


class TestEntryPointDetection:
    """entry_point tag from name and decorator patterns."""

    @pytest.mark.parametrize("name", ["main", "cli", "run", "start", "serve"])
    def test_entry_point_names(self, name: str) -> None:
        result = extract_tags(symbol_name=name)
        assert "entry_point" in result.tags

    def test_entry_point_decorators(self) -> None:
        result = extract_tags(
            symbol_name="handler",
            decorators=["click.command"],
        )
        assert "entry_point" in result.tags

    def test_not_entry_point(self) -> None:
        result = extract_tags(symbol_name="process_data")
        assert "entry_point" not in result.tags


# ── Multi-tag combination tests ──────────────────────────────────────────────


class TestMultiTagExtraction:
    """Multiple tags detected from single source."""

    def test_async_error_network(self) -> None:
        result = extract_tags(
            kind="async_function",
            source_code="""
try:
    data = await httpx.get(url)
except Exception as e:
    raise
""",
        )
        assert "async" in result.tags
        assert "error" in result.tags
        assert "network" in result.tags

    def test_lock_raii_class(self) -> None:
        result = extract_tags(
            kind="class",
            source_code="""
class Guard:
    def __init__(self):
        self._lock = Lock()
    def __enter__(self):
        self._lock.acquire()
    def __exit__(self, *a):
        self._lock.release()
""",
        )
        assert "lock" in result.tags
        assert "raii" in result.tags
        assert "atomic" in result.tags


# ── Role inference tests ─────────────────────────────────────────────────────


class TestRoleInference:
    """Role derived from structural signals, priority-ordered."""

    def test_resource_manager_from_raii(self) -> None:
        result = extract_tags(
            kind="class",
            source_code="def __enter__(self): pass\ndef __exit__(self, *a): pass",
        )
        assert result.role == ROLE_RESOURCE_MANAGER

    def test_resource_manager_from_lock(self) -> None:
        result = extract_tags(
            kind="class",
            source_code="self._lock = Lock()",
        )
        assert result.role == ROLE_RESOURCE_MANAGER

    def test_io_handler_from_filesystem(self) -> None:
        result = extract_tags(source_code="Path('/tmp/data').read_text()")
        assert result.role == ROLE_IO_HANDLER

    def test_io_handler_from_database(self) -> None:
        result = extract_tags(source_code="import asyncpg")
        assert result.role == ROLE_IO_HANDLER

    def test_io_handler_from_network(self) -> None:
        result = extract_tags(source_code="requests.get(url)")
        assert result.role == ROLE_IO_HANDLER

    def test_coordinator_from_call_count(self) -> None:
        result = extract_tags(call_count=7)
        assert result.role == ROLE_COORDINATOR

    def test_coordinator_from_name(self) -> None:
        result = extract_tags(symbol_name="TaskOrchestrator")
        assert result.role == ROLE_COORDINATOR

    def test_coordinator_from_handler_name(self) -> None:
        result = extract_tags(symbol_name="ScanHandler")
        assert result.role == ROLE_COORDINATOR

    def test_transformer_from_parse_tag(self) -> None:
        result = extract_tags(source_code="ast.parse(source)")
        assert result.role == ROLE_TRANSFORMER

    def test_transformer_from_name(self) -> None:
        result = extract_tags(symbol_name="DataEncoder")
        assert result.role == ROLE_TRANSFORMER

    def test_configuration_from_file_path(self) -> None:
        result = extract_tags(file_path="quro_cli/config.py")
        assert result.role == ROLE_CONFIGURATION

    def test_configuration_from_name(self) -> None:
        result = extract_tags(symbol_name="DefaultConfig")
        assert result.role == ROLE_CONFIGURATION

    def test_container_from_empty_class(self) -> None:
        result = extract_tags(kind="class", source_code="pass")
        assert result.role == ROLE_CONTAINER

    def test_container_not_for_function(self, empty_source: str) -> None:
        result = extract_tags(kind="function", source_code=empty_source)
        assert result.role != ROLE_CONTAINER

    def test_core_infrastructure_from_name(self) -> None:
        result = extract_tags(symbol_name="CQEEngine")
        assert result.role == ROLE_CORE_INFRASTRUCTURE

    def test_unknown_when_no_signal(self, empty_source: str) -> None:
        result = extract_tags(
            kind="function",
            source_code=empty_source,
            symbol_name="helper",
        )
        assert result.role == ROLE_UNKNOWN

    def test_priority_resource_manager_over_io_handler(self) -> None:
        """RAII class with filesystem should be resource_manager, not io_handler."""
        result = extract_tags(
            kind="class",
            source_code="def __enter__(self): pass\nPath('/tmp')",
        )
        assert result.role == ROLE_RESOURCE_MANAGER


# ── StructuralTags immutability ──────────────────────────────────────────────


class TestStructuralTags:
    """StructuralTags is frozen and converts to dict correctly."""

    def test_frozen(self) -> None:
        tags = StructuralTags(tags=("async", "error"), role="io_handler")
        with pytest.raises(AttributeError):
            tags.tags = ("lock",)  # type: ignore[misc]

    def test_to_dict(self) -> None:
        tags = StructuralTags(tags=("async", "error"), role="io_handler")
        d = tags.to_dict()
        assert d == {
            "tags": ["async", "error"],
            "role": "io_handler",
            "source": "structural",
        }

    def test_to_dict_creates_new_list(self) -> None:
        tags = StructuralTags(tags=("async",))
        d1 = tags.to_dict()
        d2 = tags.to_dict()
        assert d1 is not d2
        assert d1["tags"] is not d2["tags"]

    def test_default_values(self) -> None:
        tags = StructuralTags()
        assert tags.tags == ()
        assert tags.role == ROLE_UNKNOWN
        assert tags.source == "structural"


# ── Tag ordering determinism ─────────────────────────────────────────────────


class TestDeterminism:
    """Same inputs always produce same output (sorted tags)."""

    def test_sorted_output(self) -> None:
        r1 = extract_tags(
            kind="async_function",
            source_code="try:\n    await httpx.get(url)\nexcept Exception:\n    pass",
        )
        r2 = extract_tags(
            kind="async_function",
            source_code="try:\n    await httpx.get(url)\nexcept Exception:\n    pass",
        )
        assert r1.tags == r2.tags
        assert r1.tags == tuple(sorted(r1.tags))

    def test_different_calls_different_objects(self) -> None:
        r1 = extract_tags(source_code="pass")
        r2 = extract_tags(source_code="pass")
        assert r1.tags == r2.tags


# ── Merge with LLM tags ─────────────────────────────────────────────────────


class TestMergeWithLLMTags:
    """LLM tags are additive; structural tags are never overridden."""

    def test_no_llm_tags_returns_same(self) -> None:
        structural = StructuralTags(tags=("async", "error"), role="io_handler")
        result = merge_with_llm_tags(structural, None)
        assert result is structural

    def test_empty_list_returns_same(self) -> None:
        structural = StructuralTags(tags=("async",), role="unknown")
        result = merge_with_llm_tags(structural, [])
        assert result is structural

    def test_new_tags_appended(self) -> None:
        structural = StructuralTags(tags=("async", "error"), role="io_handler")
        result = merge_with_llm_tags(structural, ["idempotent", "retryable"])
        assert "async" in result.tags
        assert "error" in result.tags
        assert "idempotent" in result.tags
        assert "retryable" in result.tags
        assert result.role == "io_handler"
        assert result.source == "merged"

    def test_duplicate_tags_not_doubled(self) -> None:
        structural = StructuralTags(tags=("async", "error"), role="io_handler")
        result = merge_with_llm_tags(structural, ["async", "error"])
        assert result.tags.count("async") == 1
        assert result.tags.count("error") == 1
        assert result.source == "structural"  # No new tags → same object

    def test_role_never_from_llm(self) -> None:
        structural = StructuralTags(tags=("async",), role="unknown")
        result = merge_with_llm_tags(structural, ["some_tag"])
        assert result.role == "unknown"

    def test_garbage_tags_filtered(self) -> None:
        structural = StructuralTags(tags=("async",), role="unknown")
        result = merge_with_llm_tags(structural, ["xy", "", " ", "ab"])
        assert "xy" in result.tags
        assert "ab" in result.tags
        # Empty and whitespace tags filtered (len < 2)
        assert "" not in result.tags

    def test_non_string_tags_filtered(self) -> None:
        structural = StructuralTags(tags=("async",), role="unknown")
        result = merge_with_llm_tags(structural, [123, None, "valid"])  # type: ignore[list-item]
        assert "valid" in result.tags
        assert len(result.tags) == 2  # "async" + "valid"

    def test_merged_tags_sorted(self) -> None:
        structural = StructuralTags(tags=("error", "async"), role="unknown")
        result = merge_with_llm_tags(structural, ["zzz_tag"])
        assert result.tags == ("async", "error", "zzz_tag")
