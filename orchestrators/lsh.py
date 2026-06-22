"""LSH Orchestrator - Bridges Manifold Adapter and LSH Kernel.

@module quro.orchestrators.lsh
@intent Coordinate LSH fingerprint computation and persistence.
"""

from typing import Tuple, Optional
from pathlib import Path
from core.lsh import LSHConfig, LSHSignature, MinHashLSH
from adapters.manifold import (
    ManifoldAdapter,
    ManifoldNode,
    NodeInsertRequest,
)


class LSHOrchestrator:
    """Orchestrates LSH fingerprint computation and persistence.

    Coordinates:
    - LSH Kernel (pure computation)
    - Manifold Adapter (I/O persistence)

    Invariant: Orchestration only, no business logic.
    """

    def __init__(
        self,
        manifold_adapter: ManifoldAdapter,
        config: Optional[LSHConfig] = None,
    ):
        """Initialize LSH orchestrator.

        Args:
            manifold_adapter: Manifold persistence adapter
            config: LSH configuration (defaults to standard config)
        """
        self.manifold = manifold_adapter
        self.config = config or LSHConfig()
        self.kernel = MinHashLSH(self.config)

    async def compute_and_store(
        self,
        symbol: str,
        content: str,
        metadata: dict,
    ) -> ManifoldNode:
        """Compute LSH signature and store in manifold.

        Args:
            symbol: Symbol name
            content: Source code content
            metadata: Additional metadata

        Returns:
            ManifoldNode with stored signature

        Pipeline:
            1. Tokenize content and compute LSH signature (kernel)
            2. Store in manifold (adapter)
        """
        # Step 1: Tokenize and compute signature (pure computation)
        tokens = self._tokenize(content)
        signature = self.kernel.compute_signature(tokens)

        # Step 2: Store in manifold (I/O)
        request = NodeInsertRequest(
            symbol_uid=symbol,
            lsh_bands=tuple(signature.bands),
            behavioral_tags=(),
        )
        node = await self.manifold.insert_node(request)

        return node

    async def compute_similarity(
        self,
        symbol_a: str,
        symbol_b: str,
    ) -> float:
        """Compute Jaccard similarity between two symbols.

        Args:
            symbol_a: First symbol name
            symbol_b: Second symbol name

        Returns:
            Jaccard similarity [0, 1]

        Pipeline:
            1. Load fingerprints from manifold (adapter)
            2. Compute similarity (kernel)
        """
        # Step 1: Load fingerprints (I/O)
        node_a = await self.manifold.get_node(symbol_a)
        node_b = await self.manifold.get_node(symbol_b)

        if node_a is None or node_b is None:
            return 0.0

        # Step 2: Compute similarity (pure computation)
        sig_a = LSHSignature(
            hash_values=node_a.lsh_bands,
            bands=list(node_a.lsh_bands),
            config=self.config,
        )
        sig_b = LSHSignature(
            hash_values=node_b.lsh_bands,
            bands=list(node_b.lsh_bands),
            config=self.config,
        )

        similarity = self.kernel.compute_similarity(sig_a, sig_b)

        return similarity

    async def find_similar(
        self,
        symbol: str,
        threshold: float = 0.7,
        limit: int = 10,
    ) -> Tuple[Tuple[str, float], ...]:
        """Find symbols similar to given symbol.

        Args:
            symbol: Symbol name to find similar symbols for
            threshold: Minimum similarity threshold [0, 1]
            limit: Maximum number of results

        Returns:
            Tuple of (symbol, similarity) pairs

        Pipeline:
            1. Load target fingerprint (adapter)
            2. Load all fingerprints (adapter)
            3. Compute similarities (kernel)
            4. Filter and sort
        """
        # Step 1: Load target fingerprint (I/O)
        target_node = await self.manifold.get_node(symbol)
        if target_node is None:
            return ()

        target_fp = LSHSignature(
            hash_values=target_node.lsh_bands,
            bands=list(target_node.lsh_bands),
            config=self.config,
        )

        # Step 2: Load all nodes (I/O)
        all_nodes = await self.manifold.list_nodes()

        # Step 3: Compute similarities (pure computation)
        similarities = []
        for node in all_nodes:
            if node.symbol_uid == symbol:
                continue  # Skip self

            node_fp = LSHSignature(
                hash_values=node.lsh_bands,
                bands=list(node.lsh_bands),
                config=self.config,
            )
            similarity = self.kernel.compute_similarity(target_fp, node_fp)

            if similarity >= threshold:
                similarities.append((node.symbol_uid, similarity))

        # Step 4: Sort and limit
        similarities.sort(key=lambda x: x[1], reverse=True)
        return tuple(similarities[:limit])

    def _tokenize(self, content: str) -> set:
        """Tokenize content into set of tokens.

        Args:
            content: Source code content

        Returns:
            Set of tokens (words)

        Note: Simple whitespace tokenization for now.
        Production would use language-specific tokenizers.
        """
        return set(content.lower().split())
