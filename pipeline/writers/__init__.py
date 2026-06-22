"""Pipeline Writers

@module quro.pipeline.writers
@intent Data output writers for TDA pipeline phases
"""

from pipeline.writers.duckdb_event_writer import DuckDBEventWriter

__all__ = [
    "DuckDBEventWriter",
]
