"""
Tests for LSH engine (MinHash LSH for semantic similarity).
"""
import pytest
import numpy as np
from quro_cli.analysis.lsh_engine import (
    MinHashLSH,
    LSHConfig,
    LSHIndex
)


@pytest.fixture
def lsh_engine():
    """Create LSH engine with default config"""
    return MinHashLSH(LSHConfig())


@pytest.fixture
def lsh_index(lsh_engine):
    """Create LSH index"""
    return LSHIndex(lsh_engine)


def test_lsh_config_validation():
    """Test LSH config validation"""
    # Valid config
    config = LSHConfig(num_hashes=128, num_bands=16)
    engine = MinHashLSH(config)
    assert engine.config.rows_per_band == 8

    # Invalid config (not divisible)
    with pytest.raises(ValueError):
        MinHashLSH(LSHConfig(num_hashes=128, num_bands=15))


def test_compute_minhash(lsh_engine):
    """Test MinHash signature computation"""
    tokens = {"async", "await", "function", "class"}
    signature = lsh_engine.compute_minhash(tokens)

    assert signature.shape == (128,)
    assert signature.dtype == np.uint32
    assert np.all(signature > 0)


def test_compute_minhash_empty(lsh_engine):
    """Test MinHash with empty token set"""
    signature = lsh_engine.compute_minhash(set())

    assert signature.shape == (128,)
    assert np.all(signature == 0)


def test_compute_bands(lsh_engine):
    """Test band hash computation"""
    tokens = {"async", "await", "function"}
    signature = lsh_engine.compute_minhash(tokens)
    band_hashes = lsh_engine.compute_bands(signature)

    assert len(band_hashes) == 16
    assert all(isinstance(h, int) for h in band_hashes)


def test_jaccard_similarity_identical(lsh_engine):
    """Test Jaccard similarity for identical sets"""
    tokens = {"async", "await", "function"}
    sig1 = lsh_engine.compute_minhash(tokens)
    sig2 = lsh_engine.compute_minhash(tokens)

    similarity = lsh_engine.jaccard_similarity(sig1, sig2)
    assert similarity == 1.0


def test_jaccard_similarity_different(lsh_engine):
    """Test Jaccard similarity for different sets"""
    tokens1 = {"async", "await", "function"}
    tokens2 = {"class", "method", "variable"}

    sig1 = lsh_engine.compute_minhash(tokens1)
    sig2 = lsh_engine.compute_minhash(tokens2)

    similarity = lsh_engine.jaccard_similarity(sig1, sig2)
    assert 0.0 <= similarity < 0.3


def test_jaccard_similarity_overlap(lsh_engine):
    """Test Jaccard similarity for overlapping sets"""
    tokens1 = {"async", "await", "function", "class"}
    tokens2 = {"async", "await", "method", "variable"}

    sig1 = lsh_engine.compute_minhash(tokens1)
    sig2 = lsh_engine.compute_minhash(tokens2)

    similarity = lsh_engine.jaccard_similarity(sig1, sig2)
    # Should be around 0.33 (2 common out of 6 total)
    assert 0.2 <= similarity <= 0.5


def test_signature_serialization(lsh_engine):
    """Test signature to/from bytes conversion"""
    tokens = {"async", "await", "function"}
    signature = lsh_engine.compute_minhash(tokens)

    # Convert to bytes
    signature_bytes = lsh_engine.signature_to_bytes(signature)
    assert isinstance(signature_bytes, bytes)

    # Convert back
    restored = lsh_engine.signature_from_bytes(signature_bytes)
    assert np.array_equal(signature, restored)


def test_tokenize_code(lsh_engine):
    """Test code tokenization"""
    code = """
    async def process_data(x: int) -> str:
        return str(x)
    """

    tokens = lsh_engine.tokenize_code(code)
    assert "async" in tokens
    assert "def" in tokens
    assert "process_data" in tokens
    assert "int" in tokens
    assert "str" in tokens


def test_extract_behavioral_tags_python(lsh_engine):
    """Test behavioral tag extraction for Python"""
    code = """
    async def fetch_data():
        async with lock:
            try:
                await asyncio.sleep(1)
            except Exception:
                raise
    """

    tags = lsh_engine.extract_behavioral_tags(code, "python")
    assert "async" in tags
    assert "await" in tags
    assert "with" in tags
    assert "try" in tags
    assert "except" in tags
    assert "raise" in tags
    assert "asyncio" in tags


def test_extract_behavioral_tags_typescript(lsh_engine):
    """Test behavioral tag extraction for TypeScript"""
    code = """
    async function fetchData(): Promise<string> {
        try {
            await setTimeout(() => {}, 1000);
            return "data";
        } catch (error) {
            throw error;
        }
    }
    """

    tags = lsh_engine.extract_behavioral_tags(code, "typescript")
    assert "async" in tags
    assert "await" in tags
    assert "function" in tags
    assert "try" in tags
    assert "catch" in tags
    assert "return" in tags
    assert "promise" in tags


def test_lsh_index_insert(lsh_index, lsh_engine):
    """Test inserting items into LSH index"""
    tokens = {"async", "await", "function"}
    signature = lsh_engine.compute_minhash(tokens)

    lsh_index.insert("item1", signature)

    assert lsh_index.size() == 1
    assert "item1" in lsh_index.signatures


def test_lsh_index_query(lsh_index, lsh_engine):
    """Test querying LSH index"""
    # Insert similar items
    tokens1 = {"async", "await", "function", "class"}
    tokens2 = {"async", "await", "function", "method"}
    tokens3 = {"sync", "blocking", "thread"}

    sig1 = lsh_engine.compute_minhash(tokens1)
    sig2 = lsh_engine.compute_minhash(tokens2)
    sig3 = lsh_engine.compute_minhash(tokens3)

    lsh_index.insert("item1", sig1)
    lsh_index.insert("item2", sig2)
    lsh_index.insert("item3", sig3)

    # Query with similar signature
    query_tokens = {"async", "await", "function", "variable"}
    query_sig = lsh_engine.compute_minhash(query_tokens)

    results = lsh_index.query(query_sig, threshold=0.3)

    # Should find item1 and item2 (similar), but not item3
    assert len(results) >= 2
    item_ids = [item_id for item_id, _ in results]
    assert "item1" in item_ids
    assert "item2" in item_ids


def test_lsh_index_remove(lsh_index, lsh_engine):
    """Test removing items from LSH index"""
    tokens = {"async", "await", "function"}
    signature = lsh_engine.compute_minhash(tokens)

    lsh_index.insert("item1", signature)
    assert lsh_index.size() == 1

    lsh_index.remove("item1")
    assert lsh_index.size() == 0
    assert "item1" not in lsh_index.signatures


def test_lsh_index_query_threshold(lsh_index, lsh_engine):
    """Test LSH query with different thresholds"""
    tokens1 = {"async", "await", "function"}
    tokens2 = {"async", "await", "method"}

    sig1 = lsh_engine.compute_minhash(tokens1)
    sig2 = lsh_engine.compute_minhash(tokens2)

    lsh_index.insert("item1", sig1)
    lsh_index.insert("item2", sig2)

    # Query with high threshold
    results_high = lsh_index.query(sig1, threshold=0.9)
    assert len(results_high) == 1  # Only exact match

    # Query with low threshold
    results_low = lsh_index.query(sig1, threshold=0.3)
    assert len(results_low) >= 1  # May include similar items


def test_lsh_index_empty_query(lsh_index, lsh_engine):
    """Test querying empty LSH index"""
    tokens = {"async", "await", "function"}
    signature = lsh_engine.compute_minhash(tokens)

    results = lsh_index.query(signature)
    assert len(results) == 0
