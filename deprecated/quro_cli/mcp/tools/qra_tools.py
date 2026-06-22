"""
QRA Tools - Quantum Reasoning Archive operations

@module quro_cli.mcp.tools.qra_tools
@intent Provide reasoning chain management and knowledge archival
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg

logger = logging.getLogger(__name__)


class QRATools:
    """QRA Tools - Reasoning chain and knowledge management"""

    def __init__(
        self,
        workspace_root: Path,
        db_pool: Optional[asyncpg.Pool] = None
    ):
        self.workspace_root = workspace_root
        self.db_pool = db_pool
        self.qra_path = workspace_root / '.quro_context' / 'qra'
        self.qra_path.mkdir(parents=True, exist_ok=True)

    async def get_chain(self, symbol: str) -> Dict[str, Any]:
        """
        Get commit chain for a symbol

        Args:
            symbol: Symbol name

        Returns:
            {
                "status": "success",
                "symbol": str,
                "chain": [{"step": int, "reasoning": str, "timestamp": str}]
            }
        """
        chain_file = self.qra_path / f"{symbol}.chain.jsonl"

        if not chain_file.exists():
            return {
                "status": "success",
                "symbol": symbol,
                "chain": []
            }

        # Read chain from file
        chain = []
        with open(chain_file, 'r') as f:
            for line in f:
                entry = json.loads(line)
                chain.append(entry)

        return {
            "status": "success",
            "symbol": symbol,
            "chain": chain
        }

    async def commit_reasoning(
        self,
        symbol: str,
        reasoning: str,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Commit reasoning to QRA

        Args:
            symbol: Symbol name
            reasoning: Reasoning text
            tags: Optional tags for categorization

        Returns:
            {"status": "success", "symbol": str, "entry_id": str}
        """
        import time
        import uuid

        entry_id = str(uuid.uuid4())
        timestamp = time.time()

        # Create reasoning entry
        entry = {
            "entry_id": entry_id,
            "symbol": symbol,
            "reasoning": reasoning,
            "tags": tags or [],
            "timestamp": timestamp
        }

        # Append to reasoning log
        reasoning_file = self.qra_path / f"{symbol}.reasoning.jsonl"
        with open(reasoning_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        logger.info(f"Committed reasoning for {symbol}: {entry_id}")

        return {
            "status": "success",
            "symbol": symbol,
            "entry_id": entry_id
        }

    async def commit_chain(
        self,
        symbol: str,
        chain: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Commit full reasoning chain to QRA

        Args:
            symbol: Symbol name
            chain: List of reasoning steps

        Returns:
            {"status": "success", "symbol": str, "steps": int}
        """
        import time

        timestamp = time.time()

        # Validate chain structure
        for i, step in enumerate(chain):
            if "reasoning" not in step:
                return {
                    "status": "error",
                    "error": f"Step {i} missing 'reasoning' field"
                }

        # Write chain to file
        chain_file = self.qra_path / f"{symbol}.chain.jsonl"
        with open(chain_file, 'w') as f:
            for i, step in enumerate(chain):
                entry = {
                    "step": i,
                    "reasoning": step["reasoning"],
                    "metadata": step.get("metadata", {}),
                    "timestamp": timestamp
                }
                f.write(json.dumps(entry) + '\n')

        logger.info(f"Committed chain for {symbol}: {len(chain)} steps")

        return {
            "status": "success",
            "symbol": symbol,
            "steps": len(chain)
        }
