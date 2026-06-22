"""
Phase-1: Pure Graph Observation Layer

This module records atomic graph traversal events without interpretation.
It is an offline batch processor that traverses ALL symbols in the codebase.

Usage:
    python -m quro.tda.phase1 [OPTIONS]
"""

__all__ = [
    "GraphEventLogger",
    "Phase1BatchProcessor",
]

from tda.phase1.event_logger import GraphEventLogger
from tda.phase1.batch_processor import Phase1BatchProcessor
