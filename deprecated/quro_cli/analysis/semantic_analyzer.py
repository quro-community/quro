"""
Semantic analyzer using commons LLM factory for symbol role/intent/tags extraction.

Integrates with scanner to provide LLM-based semantic analysis.
Includes rate limiting, retry logic, and cost tracking.
"""
import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Use commons LLM factory
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from commons.python.llm import LLMFactory
from commons.python.llm.config import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class SemanticAnalysisResult:
    """Result of semantic analysis"""
    role: str
    intent: str
    tags: List[str]
    confidence: float
    model_version: str


class SemanticAnalyzer:
    """
    Semantic analyzer using commons LLM factory for symbol analysis.

    Features:
    - Task-specific model configuration via SEMANTIC_SCAN_PROVIDER/SEMANTIC_SCAN_MODEL
    - Auto-detects provider from environment (OPENAI_API_KEY, DASHSCOPE_API_KEY, etc.)
    - Rate limiting (500ms between requests)
    - Exponential backoff on errors
    - Cost tracking
    - Multi-provider failover support

    Environment Variables:
    - SEMANTIC_SCAN_PROVIDER: LLM provider (openai, qwen, deepseek, etc.)
    - SEMANTIC_SCAN_MODEL: Model name (e.g., qwen-turbo, gpt-4o-mini)
    - If not set, auto-detects from API keys (OPENAI_API_KEY, DASHSCOPE_API_KEY, etc.)
    """

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize semantic analyzer.

        Args:
            provider: LLM provider (openai, qwen, deepseek, etc.).
                     Uses SEMANTIC_SCAN_PROVIDER env var if None, then auto-detects.
            model: Model name override.
                  Uses SEMANTIC_SCAN_MODEL env var if None, then provider default.
        """
        # Priority: explicit args > env vars > auto-detect
        if provider is None:
            provider = os.getenv("SEMANTIC_SCAN_PROVIDER")

        if provider is None:
            provider = self._detect_provider()

        if model is None:
            model = os.getenv("SEMANTIC_SCAN_MODEL")

        self.provider = provider
        self.model = model

        # Initialize LLM adapter via commons factory
        try:
            self.adapter = LLMFactory.get_adapter(provider=provider, model=model)
            self.model = self.adapter.model  # Get actual model name
            logger.info(f"SemanticAnalyzer initialized with provider={provider}, model={self.model}")
        except Exception as e:
            logger.error(f"Failed to initialize LLM adapter: {e}")
            raise ValueError(f"Failed to initialize semantic analyzer: {e}")

        # Rate limiting
        self.min_request_interval = 0.5  # 500ms between requests
        self.last_request_time = 0.0

        # Cost tracking
        self.total_requests = 0
        self.total_tokens = 0
        self.failed_requests = 0

    def _detect_provider(self) -> str:
        """Auto-detect LLM provider from environment variables"""
        # Priority order: OpenAI > Qwen > DeepSeek > Ollama
        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        elif os.getenv("DASHSCOPE_API_KEY"):
            return "qwen"
        elif os.getenv("DEEPSEEK_API_KEY"):
            return "deepseek"
        elif os.getenv("OLLAMA_BASE_URL") or os.path.exists("/usr/local/bin/ollama"):
            return "ollama"
        else:
            raise ValueError(
                "No LLM provider detected. Please set one of: "
                "OPENAI_API_KEY, DASHSCOPE_API_KEY, DEEPSEEK_API_KEY, or install Ollama"
            )

    async def _enforce_rate_limit(self):
        """Enforce minimum interval between requests"""
        now = time.time()
        elapsed = now - self.last_request_time

        if elapsed < self.min_request_interval:
            delay = self.min_request_interval - elapsed
            await asyncio.sleep(delay)

        self.last_request_time = time.time()

    async def analyze_symbol(
        self,
        symbol_name: str,
        symbol_type: str,
        file_path: str,
        source_code: Optional[str] = None,
        docstring: Optional[str] = None,
        max_retries: int = 3
    ) -> Optional[SemanticAnalysisResult]:
        """
        Analyze a symbol using LLM via commons factory.

        Args:
            symbol_name: Name of the symbol
            symbol_type: Type (function, class, variable, etc.)
            file_path: File path for context
            source_code: Optional source code snippet
            docstring: Optional docstring
            max_retries: Maximum retry attempts

        Returns:
            SemanticAnalysisResult or None if analysis fails
        """
        # Enforce rate limit
        await self._enforce_rate_limit()

        # Build prompt
        prompt = self._build_prompt(symbol_name, symbol_type, file_path, source_code, docstring)

        # Retry with exponential backoff
        for attempt in range(max_retries):
            try:
                # Call LLM via commons adapter
                response = await self.adapter.chat_completions(
                    messages=[
                        {"role": "system", "content": "You are a code analysis expert. Analyze symbols and provide structured metadata."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format="json"
                )

                # Track usage
                self.total_requests += 1
                usage = response.get("usage", {})
                self.total_tokens += usage.get("total_tokens", 0)

                # Parse response
                content = response.get("content", "")
                if not content:
                    raise ValueError("Empty response from LLM")

                result = json.loads(content)

                # Sanitize intent — strip "Implements ..." prefix that LLMs keep generating
                raw_intent = result.get("intent", "")
                if raw_intent.startswith("Implements "):
                    raw_intent = raw_intent[len("Implements "):].strip()
                    logger.debug("Stripped 'Implements ' prefix from intent for %s", symbol_name)

                # Validate and sanitize tags — reject garbage from LLM
                raw_tags = result.get("tags", [])
                sanitized_tags = [
                    t for t in raw_tags
                    if isinstance(t, str) and len(t) >= 2 and t.isprintable() and not t.isspace()
                ]
                if len(sanitized_tags) != len(raw_tags):
                    rejected = [t for t in raw_tags if t not in sanitized_tags]
                    logger.warning(
                        "Rejected %d garbage tags from %s: %s",
                        len(rejected), symbol_name, rejected[:5],
                    )

                return SemanticAnalysisResult(
                    role=result.get("role", "unknown"),
                    intent=raw_intent,
                    tags=sanitized_tags,
                    confidence=result.get("confidence", 0.6),
                    model_version=self.model
                )

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error for {symbol_name}: {e}")
                self.failed_requests += 1

                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5
                    await asyncio.sleep(wait_time)
                else:
                    return None

            except Exception as e:
                logger.error(f"Error analyzing {symbol_name}: {e}")
                self.failed_requests += 1

                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) * 0.5
                    await asyncio.sleep(wait_time)
                else:
                    return None

        return None

    def _build_prompt(
        self,
        symbol_name: str,
        symbol_type: str,
        file_path: str,
        source_code: Optional[str],
        docstring: Optional[str]
    ) -> str:
        """Build analysis prompt"""
        prompt = f"""Analyze this {symbol_type} symbol and provide structured metadata.

Symbol: {symbol_name}
File: {file_path}
Type: {symbol_type}
"""

        if docstring:
            prompt += f"\nDocstring:\n{docstring}\n"

        if source_code:
            # Truncate source code to avoid token limits
            truncated = source_code[:1000] if len(source_code) > 1000 else source_code
            prompt += f"\nSource code:\n{truncated}\n"

        prompt += """
You are a static code behavior analyzer.

You MUST output valid JSON only. No explanation, no markdown.

Task:
Analyze the given Python symbol and extract its behavior graph.

Rules:
1. Do NOT summarize in natural language.
2. Do NOT use tags like "async", "io", "core".
3. Only use atomic behavior primitives:
   - IO: file_read, file_write, network_send, network_receive
   - Concurrency: lock_acquire, lock_release, async_spawn, await_suspend
   - State: mutation, read_only, cache_write
   - Control: branch, orchestration, delegation
4.Every behavior atom MUST be directly traceable to one of:
- AST node (Assign / Call / With / Await)
- explicit control flow (If / For / While)
- explicit API call detected in code

If not directly observable → DO NOT INCLUDE

Output schema:

{
  "symbol": "<name>",
  "behavior_atoms": [
    {
      "type": "IO|Concurrency|State|Control",
      "subtype": "<one of allowed primitives>",
      "strength": 0.0-1.0
    }
  ],
  "edges": [
    {
      "to": "<called symbol>",
      "type": "calls"
    }
  ],
  "structural_certainty": 0.0-1.0
}

Hard constraint:
- Output MUST be valid JSON
- No extra keys
- No natural language
"""

        return prompt

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self._estimate_cost()
        }

    def _estimate_cost(self) -> float:
        """Estimate cost based on token usage"""
        # Rough estimate based on common pricing
        # gpt-4o-mini: $0.15/1M input, $0.60/1M output
        # qwen-turbo: ~$0.10/1M tokens
        # Average: ~$0.20/1M tokens
        cost_per_token = 0.20 / 1_000_000
        return self.total_tokens * cost_per_token
