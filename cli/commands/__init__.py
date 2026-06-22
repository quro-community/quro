"""CLI Commands

@module quro.cli.commands
@intent Command implementations for CLI.

Command groups:
  - scanner : scan
  - cqe     : query / symbol / list / stats
  - tda     : plan / explore / centers / pipeline / populate-fields
              + next / upstream / escape / role / field / attractors
  - centers : list / show / reach   (semantic-center orientation)
  - docs    : path / build-index / check-coverage
  - visualize
"""

from cli.commands.scanner import ScanCommand
from cli.commands.cqe import (
    CQEQueryCommand,
    CQESymbolCommand,
    CQEListCommand,
    CQEStatsCommand,
)
from cli.commands.tda import (
    TDAPlanCommand,
    TDAExploreCommand,
    TDACentersCommand,
    TDANextCommand,
    TDAUpstreamCommand,
    TDAEscapeCommand,
    TDARoleCommand,
    TDAFieldCommand,
    TDAAttractorsCommand,
)
from cli.commands.tda_pipeline import (
    TDAPipelineCommand,
    TDAPopulateFieldsCommand,
)
from cli.commands.centers import (
    CentersListCommand,
    CentersShowCommand,
    CentersReachCommand,
)
from cli.commands.docs import (
    DocsPathCommand,
    DocsBuildIndexCommand,
    DocsCheckCoverageCommand,
)
from cli.commands.visualize import VisualizeCommand

__all__ = [
    # scanner
    "ScanCommand",
    # cqe
    "CQEQueryCommand",
    "CQESymbolCommand",
    "CQEListCommand",
    "CQEStatsCommand",
    # tda
    "TDAPlanCommand",
    "TDAExploreCommand",
    "TDACentersCommand",
    "TDAPipelineCommand",
    "TDAPopulateFieldsCommand",
    "TDANextCommand",
    "TDAUpstreamCommand",
    "TDAEscapeCommand",
    "TDARoleCommand",
    "TDAFieldCommand",
    "TDAAttractorsCommand",
    # centers
    "CentersListCommand",
    "CentersShowCommand",
    "CentersReachCommand",
    # docs
    "DocsPathCommand",
    "DocsBuildIndexCommand",
    "DocsCheckCoverageCommand",
    # visualize
    "VisualizeCommand",
]
