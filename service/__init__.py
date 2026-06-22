"""Service Layer for Quro v3

@module quro.service
@intent Unified service layer for CLI, API, and MCP access.

This module provides a register-based service architecture where all business
logic lives. CLI, MCP, and programmatic API all use these services.
"""

from service.base import BaseService
from service.registry import ServiceRegistry
from service.cqe_service import CQEService
from service.tda_service import TDAService
from service.scanner_service import ScannerService
from service.visualization_service import VisualizationService

__all__ = [
    "BaseService",
    "ServiceRegistry",
    "CQEService",
    "TDAService",
    "ScannerService",
    "VisualizationService",
]
