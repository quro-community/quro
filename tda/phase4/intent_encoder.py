"""Intent Encoder using LLM Embeddings

@module quro.tda.phase4.intent_encoder
@intent Encode natural language intent to semantic vectors for trajectory planning.
"""

import logging
from typing import List, Optional
# Lazy import to avoid dependency issues
import ollama

logger = logging.getLogger(__name__)


class IntentEncoder:
    """Encode user intent to semantic vectors."""

    def __init__(self, embedding_dim: int = 128):
        """Initialize intent encoder.

        Args:
            embedding_dim: Dimension of intent vectors (default: 128)
        """
        self.embedding_dim = embedding_dim
        self._ollama_client = None

    def encode(self, intent: str) -> Optional[List[float]]:
        """Encode natural language intent to vector.

        Args:
            intent: Natural language intent (e.g., "understand async flow")

        Returns:
            Intent vector (128-dim) or None if encoding fails
        """
        if not intent or not intent.strip():
            return None

        try:
            # Try to use Ollama embedding model
            vector = self._encode_with_ollama(intent)
            if vector:
                return vector
        except Exception as e:
            logger.warning("Ollama encoding failed: %s", e)

        # Fallback: return None (no intent penalty)
        logger.info("Intent encoding unavailable, using no intent penalty")
        return None

    def _encode_with_ollama(self, text: str) -> Optional[List[float]]:
        """Encode text using Ollama embedding model.

        Args:
            text: Text to encode

        Returns:
            Embedding vector or None
        """
        try:

            if self._ollama_client is None:
                self._ollama_client = ollama.Client(host='http://127.0.0.1:11434')

            # Use qwen3-embedding model (8B parameters)
            response = self._ollama_client.embed(
                model="qwen3-embedding:8b",
                input=text
            )

            if response and "embeddings" in response:
                embedding = response["embeddings"][0]

                # Truncate or pad to target dimension
                if len(embedding) > self.embedding_dim:
                    return embedding[:self.embedding_dim]
                elif len(embedding) < self.embedding_dim:
                    # Pad with zeros
                    return embedding + [0.0] * (self.embedding_dim - len(embedding))
                else:
                    return embedding

        except ImportError:
            logger.warning("ollama package not installed")
        except Exception as e:
            logger.warning("Ollama embedding failed: %s", e)

        return None

    def batch_encode(self, intents: List[str]) -> List[Optional[List[float]]]:
        """Encode multiple intents in batch.

        Args:
            intents: List of natural language intents

        Returns:
            List of intent vectors (or None for failed encodings)
        """
        return [self.encode(intent) for intent in intents]
