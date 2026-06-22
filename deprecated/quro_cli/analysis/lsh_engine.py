"""
MinHash LSH (Locality Sensitive Hashing) Engine for semantic similarity search.

Implements MinHash algorithm with banding technique for efficient approximate
nearest neighbor search in high-dimensional spaces.
"""

import hashlib
import struct
from typing import List, Set, Tuple, Dict, Any, Optional
import numpy as np
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class LSHConfig:
    """LSH configuration parameters"""

    num_hashes: int = 128  # Number of hash functions
    num_bands: int = 16  # Number of bands
    rows_per_band: int = 8  # Rows per band (num_hashes / num_bands)
    threshold: float = 0.3  # Similarity threshold


class MinHashLSH:
    """
    MinHash LSH for semantic similarity search

    Uses MinHash signatures with banding technique to find similar items efficiently.
    Time complexity: O(1) for query (vs O(n) for brute force)
    """

    def __init__(self, config: Optional[LSHConfig] = None):
        """
        Initialize MinHash LSH engine

        Args:
            config: LSH configuration (default: LSHConfig())
        """
        self.config = config or LSHConfig()

        # Validate configuration
        if self.config.num_hashes % self.config.num_bands != 0:
            raise ValueError(
                f"num_hashes ({self.config.num_hashes}) must be divisible by "
                f"num_bands ({self.config.num_bands})"
            )

        self.config.rows_per_band = self.config.num_hashes // self.config.num_bands

        # Generate hash functions (using different seeds)
        self.hash_functions = self._generate_hash_functions()

        logger.info(
            f"MinHash LSH initialized: {self.config.num_hashes} hashes, "
            f"{self.config.num_bands} bands, {self.config.rows_per_band} rows/band"
        )

    def _generate_hash_functions(self) -> List[Tuple[int, int]]:
        """
        Generate hash function parameters (a, b) for MinHash

        Each hash function is: h(x) = (a*x + b) mod prime

        Returns:
            List of (a, b) tuples for each hash function
        """
        # Large prime number for modulo operation
        prime = 2**31 - 1

        # Generate random (a, b) pairs using deterministic seed
        np.random.seed(42)
        hash_functions = []

        for i in range(self.config.num_hashes):
            a = np.random.randint(1, prime)
            b = np.random.randint(0, prime)
            hash_functions.append((a, b))

        return hash_functions

    def compute_minhash(self, tokens: Set[str]) -> np.ndarray:
        """
        Compute MinHash signature for a set of tokens

        Args:
            tokens: Set of tokens (e.g., words, n-grams, behavioral tags)

        Returns:
            MinHash signature as numpy array of shape (num_hashes,)
        """
        if not tokens:
            return np.zeros(self.config.num_hashes, dtype=np.uint32)

        # Convert tokens to integer hashes
        token_hashes = [self._hash_token(token) for token in tokens]

        # Compute MinHash signature
        signature = np.full(
            self.config.num_hashes, np.iinfo(np.uint32).max, dtype=np.uint32
        )

        prime = 2**31 - 1

        for token_hash in token_hashes:
            for i, (a, b) in enumerate(self.hash_functions):
                # h(x) = (a*x + b) mod prime
                hash_value = (a * token_hash + b) % prime
                signature[i] = min(signature[i], hash_value)

        return signature

    def _hash_token(self, token: str) -> int:
        """
        Hash a token to an integer

        Args:
            token: Token string

        Returns:
            Integer hash value
        """
        # Use SHA256 and take first 4 bytes as uint32
        hash_bytes = hashlib.sha256(token.encode("utf-8")).digest()[:4]
        return struct.unpack("I", hash_bytes)[0]

    def compute_bands(self, signature: np.ndarray) -> List[int]:
        """
        Compute band hashes from MinHash signature

        Args:
            signature: MinHash signature

        Returns:
            List of band hashes (one per band)
        """
        band_hashes = []

        for band_idx in range(self.config.num_bands):
            start = band_idx * self.config.rows_per_band
            end = start + self.config.rows_per_band

            # Extract band rows
            band_rows = signature[start:end]

            # Hash the band
            band_hash = self._hash_band(band_rows)
            band_hashes.append(band_hash)

        return band_hashes

    def _hash_band(self, band_rows: np.ndarray) -> int:
        """
        Hash a band (multiple rows) to a single integer

        Args:
            band_rows: Array of hash values in the band

        Returns:
            Band hash as integer
        """
        # Convert to bytes and hash
        band_bytes = band_rows.tobytes()
        hash_bytes = hashlib.sha256(band_bytes).digest()[:8]
        return struct.unpack("Q", hash_bytes)[0]

    def jaccard_similarity(self, sig1: np.ndarray, sig2: np.ndarray) -> float:
        """
        Estimate Jaccard similarity from MinHash signatures

        Args:
            sig1: First MinHash signature
            sig2: Second MinHash signature

        Returns:
            Estimated Jaccard similarity [0.0, 1.0]
        """
        if len(sig1) != len(sig2):
            raise ValueError("Signatures must have same length")

        # Count matching hash values
        matches = np.sum(sig1 == sig2)

        # Jaccard similarity ≈ fraction of matching hashes
        return matches / len(sig1)

    def signature_to_bytes(self, signature: np.ndarray) -> bytes:
        """
        Convert MinHash signature to bytes for storage

        Args:
            signature: MinHash signature

        Returns:
            Signature as bytes
        """
        return signature.tobytes()

    def signature_from_bytes(self, signature_bytes: bytes) -> np.ndarray:
        """
        Convert bytes back to MinHash signature

        Args:
            signature_bytes: Signature as bytes

        Returns:
            MinHash signature as numpy array
        """
        return np.frombuffer(signature_bytes, dtype=np.uint32)

    def compute_signature(self, text: str) -> bytes:
        """
        Compute MinHash signature from text and return as bytes

        Args:
            text: Input text (code, features, etc.)

        Returns:
            MinHash signature as bytes
        """
        # Tokenize text
        tokens = self.tokenize_code(text)

        # Compute MinHash signature
        signature = self.compute_minhash(tokens)

        # Convert to bytes
        return self.signature_to_bytes(signature)

    def get_band_hashes(self, signature_bytes: bytes) -> List[int]:
        """
        Get band hashes from signature bytes

        Args:
            signature_bytes: MinHash signature as bytes

        Returns:
            List of band hashes
        """
        # Convert bytes to signature
        signature = self.signature_from_bytes(signature_bytes)

        # Compute band hashes
        return self.compute_bands(signature)

    def tokenize_code(self, code: str) -> Set[str]:
        """
        Tokenize code into set of tokens for MinHash

        Uses simple whitespace + punctuation splitting.
        For production, consider using AST-based tokenization.

        Args:
            code: Source code string

        Returns:
            Set of tokens
        """
        # Simple tokenization: split on whitespace and common punctuation
        import re

        tokens = re.findall(r"\w+", code.lower())
        return set(tokens)

    def extract_behavioral_tags(self, code: str, language: str = "python") -> Set[str]:
        """
        Extract behavioral tags from code for semantic similarity

        Behavioral tags capture code patterns like:
        - async/await usage
        - lock/synchronization primitives
        - error handling patterns
        - I/O operations

        Args:
            code: Source code string
            language: Programming language

        Returns:
            Set of behavioral tags
        """
        tags = set()

        # Common patterns across languages
        patterns = {
            "async": r"\basync\b",
            "await": r"\bawait\b",
            "lock": r"\block\b",
            "mutex": r"\bmutex\b",
            "semaphore": r"\bsemaphore\b",
            "try": r"\btry\b",
            "catch": r"\bcatch\b",
            "except": r"\bexcept\b",
            "finally": r"\bfinally\b",
            "with": r"\bwith\b",
            "context_manager": r"__enter__|__exit__",
            "generator": r"\byield\b",
            "decorator": r"@\w+",
            "class": r"\bclass\b",
            "function": r"\bdef\b|\bfunction\b",
            "import": r"\bimport\b|\bfrom\b",
            "loop": r"\bfor\b|\bwhile\b",
            "conditional": r"\bif\b|\belse\b",
            "return": r"\breturn\b",
            "raise": r"\braise\b|\bthrow\b",
        }

        import re

        for tag, pattern in patterns.items():
            if re.search(pattern, code, re.IGNORECASE):
                tags.add(tag)

        # Language-specific tags
        if language == "python":
            if "asyncio" in code:
                tags.add("asyncio")
            if "threading" in code:
                tags.add("threading")
            if "multiprocessing" in code:
                tags.add("multiprocessing")
        elif language == "typescript" or language == "javascript":
            if "Promise" in code:
                tags.add("promise")
            if "setTimeout" in code or "setInterval" in code:
                tags.add("timer")

        return tags


class LSHIndex:
    """
    LSH Index for storing and querying MinHash signatures

    Maintains band buckets for efficient similarity search.
    """

    def __init__(self, lsh_engine: MinHashLSH):
        """
        Initialize LSH index

        Args:
            lsh_engine: MinHash LSH engine
        """
        self.lsh_engine = lsh_engine

        # Band buckets: band_idx -> band_hash -> set of item_ids
        self.buckets: Dict[int, Dict[int, Set[str]]] = {
            i: {} for i in range(lsh_engine.config.num_bands)
        }

        # Store signatures: item_id -> signature
        self.signatures: Dict[str, np.ndarray] = {}

    def insert(self, item_id: str, signature: np.ndarray) -> None:
        """
        Insert item into LSH index

        Args:
            item_id: Unique item identifier
            signature: MinHash signature
        """
        # Store signature
        self.signatures[item_id] = signature

        # Compute band hashes
        band_hashes = self.lsh_engine.compute_bands(signature)

        # Insert into buckets
        for band_idx, band_hash in enumerate(band_hashes):
            if band_hash not in self.buckets[band_idx]:
                self.buckets[band_idx][band_hash] = set()
            self.buckets[band_idx][band_hash].add(item_id)

    def query(
        self, signature: np.ndarray, threshold: Optional[float] = None
    ) -> List[Tuple[str, float]]:
        """
        Query LSH index for similar items

        Args:
            signature: Query MinHash signature
            threshold: Similarity threshold (default: from config)

        Returns:
            List of (item_id, similarity) tuples, sorted by similarity descending
        """
        threshold = threshold or self.lsh_engine.config.threshold

        # Compute band hashes for query
        band_hashes = self.lsh_engine.compute_bands(signature)

        # Find candidate items (items in same buckets)
        candidates = set()
        for band_idx, band_hash in enumerate(band_hashes):
            if band_hash in self.buckets[band_idx]:
                candidates.update(self.buckets[band_idx][band_hash])

        # Compute exact similarities for candidates
        results = []
        for item_id in candidates:
            item_signature = self.signatures[item_id]
            similarity = self.lsh_engine.jaccard_similarity(signature, item_signature)

            if similarity >= threshold:
                results.append((item_id, similarity))

        # Sort by similarity descending
        results.sort(key=lambda x: x[1], reverse=True)

        return results

    def remove(self, item_id: str) -> None:
        """
        Remove item from LSH index

        Args:
            item_id: Item identifier to remove
        """
        if item_id not in self.signatures:
            return

        # Get signature
        signature = self.signatures[item_id]

        # Compute band hashes
        band_hashes = self.lsh_engine.compute_bands(signature)

        # Remove from buckets
        for band_idx, band_hash in enumerate(band_hashes):
            if band_hash in self.buckets[band_idx]:
                self.buckets[band_idx][band_hash].discard(item_id)

                # Clean up empty buckets
                if not self.buckets[band_idx][band_hash]:
                    del self.buckets[band_idx][band_hash]

        # Remove signature
        del self.signatures[item_id]

    def size(self) -> int:
        """
        Get number of items in index

        Returns:
            Number of indexed items
        """
        return len(self.signatures)


async def generate_minhash_for_all_symbols(db_url: str, batch_size: int = 100):
    """
    Generate MinHash signatures for all symbols in database

    Args:
        db_url: PostgreSQL database URL
        batch_size: Number of symbols to process per batch
    """
    import asyncpg
    import time

    print("\n" + "=" * 100)
    print("MinHash Generation - LSH Engine")
    print("=" * 100)

    # Initialize LSH engine
    lsh_engine = MinHashLSH()
    print(
        f"✓ LSH Engine initialized (num_hashes={lsh_engine.config.num_hashes}, bands={lsh_engine.config.num_bands})"
    )

    # Connect to database
    pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)

    try:
        async with pool.acquire() as conn:
            # Get total count
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM symbols WHERE scan_completed = TRUE"
            )
            print(f"✓ Database connected: {total:,} symbols to process\n")

            # Process in batches
            processed = 0
            updated = 0
            start_time = time.time()

            while processed < total:
                # Fetch batch
                rows = await conn.fetch(
                    """
                    SELECT s.id, s.canonical_uid, s.symbol_name, s.role, s.intent, s.tags, f.file_path
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.scan_completed = TRUE
                    ORDER BY s.id
                    LIMIT $1 OFFSET $2
                """,
                    batch_size,
                    processed,
                )

                if not rows:
                    break

                print(
                    f"\n📦 Batch {processed // batch_size + 1} (symbols {processed + 1}-{processed + len(rows)}):"
                )
                print("-" * 100)
                # Fetch batch
                rows = await conn.fetch(
                    """
                    SELECT s.id, s.canonical_uid, s.symbol_name, s.role, s.intent, s.tags, f.file_path
                    FROM symbols s
                    JOIN files f ON s.file_id = f.id
                    WHERE s.scan_completed = TRUE
                    ORDER BY s.id
                    LIMIT $1 OFFSET $2
                """,
                    batch_size,
                    processed,
                )

                if not rows:
                    break

                # Generate MinHash for each symbol
                import json
                import time

                batch_start = time.time()

                for idx, row in enumerate(rows):
                    # Build feature text from semantic data
                    features = []

                    if row["role"]:
                        features.append(f"role:{row['role']}")
                    if row["intent"]:
                        features.append(f"intent:{row['intent']}")
                    if row["tags"]:
                        tags = (
                            json.loads(row["tags"])
                            if isinstance(row["tags"], str)
                            else row["tags"]
                        )
                        for tag in tags:
                            features.append(f"tag:{tag}")

                    # Add symbol name
                    features.append(f"name:{row['symbol_name']}")

                    # Combine features
                    feature_text = " ".join(features)

                    # Generate MinHash signature
                    signature_bytes = lsh_engine.compute_signature(feature_text)

                    # Update database
                    await conn.execute(
                        """
                        UPDATE symbols
                        SET minhash_signature = $1
                        WHERE id = $2
                    """,
                        signature_bytes,
                        row["id"],
                    )

                    updated += 1

                    # Show progress for each symbol in batch
                    if (idx + 1) % 10 == 0 or (idx + 1) == len(rows):
                        elapsed = time.time() - batch_start
                        rate = (idx + 1) / elapsed if elapsed > 0 else 0
                        print(
                            f"  [{processed + idx + 1}/{total}] {row['symbol_name'][:40]:40s} | {row['file_path'][:50]:50s} | {rate:.1f} sym/s",
                            flush=True,
                        )

                processed += len(rows)
                batch_elapsed = time.time() - batch_start
                overall_elapsed = time.time() - start_time
                overall_rate = processed / overall_elapsed if overall_elapsed > 0 else 0
                eta_seconds = (
                    (total - processed) / overall_rate if overall_rate > 0 else 0
                )
                eta_minutes = eta_seconds / 60

                print("-" * 100)
                print(
                    f"✓ Batch complete: {len(rows)} symbols in {batch_elapsed:.2f}s ({len(rows) / batch_elapsed:.1f} sym/s)"
                )
                print(
                    f"📊 Overall: {processed}/{total} ({processed / total * 100:.1f}%) | {overall_rate:.1f} sym/s | ETA: {eta_minutes:.1f} min\n"
                )

            total_elapsed = time.time() - start_time
            print("=" * 100)
            print(f"✅ MinHash generation complete!")
            print(f"   Symbols updated: {updated:,}")
            print(f"   Total time: {total_elapsed:.2f}s ({total_elapsed / 60:.1f} min)")
            print(f"   Average rate: {updated / total_elapsed:.1f} sym/s")
            print("=" * 100 + "\n")

    finally:
        await pool.close()


async def main():
    """CLI entry point for LSH engine"""
    import argparse
    import sys

    from quro_cli.config import QURO_DB_URL

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Generate MinHash signatures for symbols"
    )
    parser.add_argument(
        "--db-url",
        default=QURO_DB_URL,
        help="PostgreSQL database URL (default: QURO_DB_URL env)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Batch size for processing"
    )

    args = parser.parse_args()

    try:
        await generate_minhash_for_all_symbols(args.db_url, args.batch_size)
        logger.info("✅ MinHash generation completed successfully")
    except Exception as e:
        logger.error(f"❌ MinHash generation failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
