"""
Quro v3 I/O Layer - Boundary adapters

@module quro.io
@intent Adapt external data sources to pure protocols
@constraint All side effects happen here

Components:
- adapters/ - Protocol implementations (SQLite, PostgreSQL, etc.)
- telemetry.py - Event logging (JSONL)
- extensions.py - Plugin registry
"""
