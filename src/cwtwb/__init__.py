"""cwtwb - Tableau Workbook (.twb) Generation MCP Server"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cwtwb")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"

from .capability_registry import (  # noqa: E402
    CAPABILITY_SPECS,
    CapabilitySpec,
    format_capability_catalog,
    get_capability,
    list_capabilities,
)
from .field_registry import FieldRegistry  # noqa: E402
from .twb_analyzer import AnalysisReport, TWBAnalyzer, analyze_workbook  # noqa: E402
from .twb_editor import TWBEditor  # noqa: E402
from .validator import TWBValidationError  # noqa: E402

__all__ = [
    "AnalysisReport",
    "CAPABILITY_SPECS",
    "CapabilitySpec",
    "FieldRegistry",
    "TWBAnalyzer",
    "TWBEditor",
    "TWBValidationError",
    "__version__",
    "analyze_workbook",
    "format_capability_catalog",
    "get_capability",
    "list_capabilities",
]


