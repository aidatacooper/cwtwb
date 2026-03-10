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
    format_capability_detail,
    get_capability,
    list_capabilities,
)
from .field_registry import FieldRegistry  # noqa: E402
from .migration import (  # noqa: E402
    apply_twb_migration,
    inspect_target_schema,
    migrate_twb_guided,
    profile_twb_for_migration,
    propose_field_mapping,
    preview_twb_migration,
)
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
    "apply_twb_migration",
    "analyze_workbook",
    "format_capability_catalog",
    "format_capability_detail",
    "get_capability",
    "inspect_target_schema",
    "list_capabilities",
    "migrate_twb_guided",
    "profile_twb_for_migration",
    "propose_field_mapping",
    "preview_twb_migration",
]


