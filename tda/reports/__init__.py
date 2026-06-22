"""
TDA Reports Module

@module quro.tda.reports
@intent Quality reporting and statistics for TDA components
"""

from tda.reports.quality_report import (
    TDAQualityReportGenerator,
    TDAQualityReport,
    Phase1Stats,
    Phase2Stats,
    Phase3Stats,
    CQEIntegrationStats,
    DualLayerComparison,
)

__all__ = [
    "TDAQualityReportGenerator",
    "TDAQualityReport",
    "Phase1Stats",
    "Phase2Stats",
    "Phase3Stats",
    "CQEIntegrationStats",
    "DualLayerComparison",
]
