"""Canonical capability catalog for cwtwb.

This module defines the project's explicit capability boundary so the SDK,
MCP tools, docs, and tests can reference the same source of truth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


CapabilityLevel = Literal["core", "advanced", "recipe", "unsupported"]
CapabilityKind = Literal[
    "chart",
    "encoding",
    "dashboard_zone",
    "action",
    "connection",
    "feature",
]


@dataclass(frozen=True)
class CapabilitySpec:
    """A single declared capability in cwtwb."""

    key: str
    kind: CapabilityKind
    level: CapabilityLevel
    canonical: str
    aliases: tuple[str, ...] = ()
    rationale: str = ""
    notes: str = ""


CAPABILITY_SPECS: tuple[CapabilitySpec, ...] = (
    CapabilitySpec(
        key="bar",
        kind="chart",
        level="core",
        canonical="Bar",
        aliases=("bar chart",),
        rationale="High-frequency categorical comparison with stable field mapping.",
    ),
    CapabilitySpec(
        key="line",
        kind="chart",
        level="core",
        canonical="Line",
        aliases=("line chart",),
        rationale="High-frequency time-series primitive with stable semantics.",
    ),
    CapabilitySpec(
        key="area",
        kind="chart",
        level="core",
        canonical="Area",
        aliases=("area chart",),
        rationale="Common trend + composition primitive built directly from native marks.",
    ),
    CapabilitySpec(
        key="pie",
        kind="chart",
        level="core",
        canonical="Pie",
        aliases=("pie chart",),
        rationale="Simple part-to-whole chart with explicit wedge-size encoding.",
    ),
    CapabilitySpec(
        key="map",
        kind="chart",
        level="core",
        canonical="Map",
        aliases=("map chart", "multipolygon"),
        rationale="Stable geographic primitive with dedicated builder support.",
    ),
    CapabilitySpec(
        key="text",
        kind="chart",
        level="core",
        canonical="Text",
        aliases=("text table", "kpi", "kpi card"),
        rationale="Required for KPI and text-table workflows in practical dashboards.",
    ),
    CapabilitySpec(
        key="scatterplot",
        kind="chart",
        level="advanced",
        canonical="Scatterplot",
        aliases=("scatter plot", "circle pattern"),
        rationale="Useful analytical pattern, but implemented as a mapped Circle mode.",
    ),
    CapabilitySpec(
        key="heatmap",
        kind="chart",
        level="advanced",
        canonical="Heatmap",
        aliases=("heat map", "square pattern"),
        rationale="Useful pattern, but implemented as a Square mode plus encoding conventions.",
    ),
    CapabilitySpec(
        key="tree-map",
        kind="chart",
        level="advanced",
        canonical="Tree Map",
        aliases=("treemap", "square pattern"),
        rationale="Valuable chart family, but currently a higher-level Square pattern.",
    ),
    CapabilitySpec(
        key="bubble-chart",
        kind="chart",
        level="advanced",
        canonical="Bubble Chart",
        aliases=("bubble", "circle pattern"),
        rationale="Valuable chart family, but currently a higher-level Circle pattern.",
    ),
    CapabilitySpec(
        key="circle-mark",
        kind="chart",
        level="advanced",
        canonical="Circle Mark",
        aliases=("circle",),
        rationale="Native mark primitive used by advanced circle-based patterns.",
        notes="Tracked for analysis so circle-backed templates are not reported as unknown.",
    ),
    CapabilitySpec(
        key="square-mark",
        kind="chart",
        level="advanced",
        canonical="Square Mark",
        aliases=("square",),
        rationale="Native mark primitive used by advanced square-based patterns.",
        notes="Tracked for analysis so square-backed templates are not reported as unknown.",
    ),
    CapabilitySpec(
        key="dual-axis",
        kind="chart",
        level="advanced",
        canonical="Dual Axis",
        aliases=("combo chart",),
        rationale="Important higher-order composition primitive with dedicated builder support.",
    ),
    CapabilitySpec(
        key="donut",
        kind="chart",
        level="recipe",
        canonical="Donut",
        aliases=("donut chart",),
        rationale="Recipe-level pattern built on dual-axis and layout tricks.",
    ),
    CapabilitySpec(
        key="lollipop",
        kind="chart",
        level="recipe",
        canonical="Lollipop",
        aliases=("lollipop chart",),
        rationale="Recipe-level dual-axis styling pattern rather than a first-class primitive.",
    ),
    CapabilitySpec(
        key="bullet",
        kind="chart",
        level="recipe",
        canonical="Bullet",
        aliases=("bullet chart",),
        rationale="Useful showcase pattern, but not a stable first-class primitive yet.",
    ),
    CapabilitySpec(
        key="bump",
        kind="chart",
        level="recipe",
        canonical="Bump",
        aliases=("bump chart",),
        rationale="Recipe-level ranking pattern with higher semantic and validation complexity.",
    ),
    CapabilitySpec(
        key="butterfly",
        kind="chart",
        level="recipe",
        canonical="Butterfly",
        aliases=("butterfly chart",),
        rationale="Recipe-level mirrored-bar pattern rather than a base primitive.",
    ),
    CapabilitySpec(
        key="calendar",
        kind="chart",
        level="recipe",
        canonical="Calendar",
        aliases=("calendar chart",),
        rationale="Recipe-level pattern with date-grid semantics beyond base marks.",
    ),
    CapabilitySpec(
        key="color",
        kind="encoding",
        level="core",
        canonical="Color",
        aliases=("color encoding",),
        rationale="Standard visual encoding across base charts.",
    ),
    CapabilitySpec(
        key="size",
        kind="encoding",
        level="core",
        canonical="Size",
        aliases=("size encoding",),
        rationale="Standard visual encoding across base charts.",
    ),
    CapabilitySpec(
        key="text-encoding",
        kind="encoding",
        level="core",
        canonical="Text",
        aliases=("label", "text encoding"),
        rationale="Needed for KPI cards and text tables.",
    ),
    CapabilitySpec(
        key="tooltip",
        kind="encoding",
        level="core",
        canonical="Tooltip",
        aliases=("tooltip encoding",),
        rationale="Common and stable supplemental encoding.",
    ),
    CapabilitySpec(
        key="geometry",
        kind="encoding",
        level="core",
        canonical="Geometry",
        aliases=("geometry encoding",),
        rationale="Required for geographic map rendering.",
    ),
    CapabilitySpec(
        key="lod",
        kind="encoding",
        level="advanced",
        canonical="LOD",
        aliases=("level of detail",),
        rationale="Advanced encoding/pane behavior used in map and advanced patterns.",
    ),
    CapabilitySpec(
        key="wedge-size",
        kind="encoding",
        level="advanced",
        canonical="Wedge Size",
        aliases=("wedge size", "wedge size encoding"),
        rationale="Specialized encoding mainly for pie-like patterns.",
    ),
    CapabilitySpec(
        key="worksheet-zone",
        kind="dashboard_zone",
        level="core",
        canonical="Worksheet",
        aliases=("worksheet zone",),
        rationale="Base dashboard composition primitive.",
    ),
    CapabilitySpec(
        key="layout-container",
        kind="dashboard_zone",
        level="core",
        canonical="Layout Container",
        aliases=("layout-flow", "layout container"),
        rationale="Base dashboard layout primitive used to arrange worksheet zones.",
    ),
    CapabilitySpec(
        key="filter-zone",
        kind="dashboard_zone",
        level="advanced",
        canonical="Filter",
        aliases=("filter zone",),
        rationale="Interactive dashboard control above base sheet placement.",
    ),
    CapabilitySpec(
        key="paramctrl-zone",
        kind="dashboard_zone",
        level="advanced",
        canonical="ParamCtrl",
        aliases=("parameter control", "paramctrl zone"),
        rationale="Interactive dashboard control above base sheet placement.",
    ),
    CapabilitySpec(
        key="color-zone",
        kind="dashboard_zone",
        level="advanced",
        canonical="Color Legend",
        aliases=("color zone", "legend"),
        rationale="Dashboard legend placement is above the base worksheet primitive.",
    ),
    CapabilitySpec(
        key="filter-action",
        kind="action",
        level="advanced",
        canonical="Filter Action",
        aliases=("tsc:tsl-filter",),
        rationale="Important interaction primitive beyond base chart creation.",
    ),
    CapabilitySpec(
        key="highlight-action",
        kind="action",
        level="advanced",
        canonical="Highlight Action",
        aliases=("tsc:brush",),
        rationale="Important interaction primitive beyond base chart creation.",
    ),
    CapabilitySpec(
        key="excel-direct",
        kind="connection",
        level="core",
        canonical="excel-direct",
        aliases=("excel",),
        rationale="Supported connection type in the zero-config default flow.",
    ),
    CapabilitySpec(
        key="hyper",
        kind="connection",
        level="core",
        canonical="hyper",
        rationale="Supported extract connection type.",
    ),
    CapabilitySpec(
        key="federated",
        kind="connection",
        level="core",
        canonical="federated",
        rationale="Common Tableau logical-wrapper connection that contains supported physical connections.",
        notes="Tracked as core infrastructure so generated workbooks are not penalized for Tableau's wrapper node.",
    ),
    CapabilitySpec(
        key="mysql",
        kind="connection",
        level="core",
        canonical="mysql",
        rationale="Supported local relational connection type.",
    ),
    CapabilitySpec(
        key="sqlproxy",
        kind="connection",
        level="core",
        canonical="sqlproxy",
        aliases=("tableau server",),
        rationale="Supported Tableau Server-style connection type.",
    ),
    CapabilitySpec(
        key="reference-line",
        kind="feature",
        level="unsupported",
        canonical="Reference Line",
        aliases=("reference line",),
        rationale="Known Tableau feature outside cwtwb's current supported surface.",
    ),
    CapabilitySpec(
        key="trend-line",
        kind="feature",
        level="unsupported",
        canonical="Trend Line",
        aliases=("trend line",),
        rationale="Known Tableau feature outside cwtwb's current supported surface.",
    ),
    CapabilitySpec(
        key="table-calculation",
        kind="feature",
        level="unsupported",
        canonical="Table Calculation",
        aliases=("table calc",),
        rationale="Known Tableau feature outside cwtwb's current supported surface.",
    ),
    CapabilitySpec(
        key="bin",
        kind="feature",
        level="unsupported",
        canonical="Bin",
        aliases=("bins",),
        rationale="Known Tableau feature outside cwtwb's current supported surface.",
    ),
    CapabilitySpec(
        key="set",
        kind="feature",
        level="unsupported",
        canonical="Set",
        aliases=("sets",),
        rationale="Known Tableau feature outside cwtwb's current supported surface.",
    ),
)


def _normalize_name(value: str) -> str:
    return " ".join(value.strip().casefold().replace("_", " ").replace("-", " ").split())


_LOOKUP: dict[tuple[CapabilityKind, str], CapabilitySpec] = {}
for _spec in CAPABILITY_SPECS:
    for _name in (_spec.key, _spec.canonical, *_spec.aliases):
        _LOOKUP[(_spec.kind, _normalize_name(_name))] = _spec


def get_capability(kind: CapabilityKind, name: str) -> CapabilitySpec | None:
    """Resolve a capability spec by kind and raw name."""

    return _LOOKUP.get((kind, _normalize_name(name)))


def list_capabilities(
    *,
    kind: CapabilityKind | None = None,
    level: CapabilityLevel | None = None,
) -> list[CapabilitySpec]:
    """Return declared capabilities, optionally filtered by kind and/or level."""

    items = [
        spec
        for spec in CAPABILITY_SPECS
        if (kind is None or spec.kind == kind)
        and (level is None or spec.level == level)
    ]
    return sorted(items, key=lambda spec: (spec.kind, spec.level, spec.canonical))


def get_level_summary() -> dict[CapabilityLevel, int]:
    """Return counts of declared capabilities by level."""

    summary: dict[CapabilityLevel, int] = {
        "core": 0,
        "advanced": 0,
        "recipe": 0,
        "unsupported": 0,
    }
    for spec in CAPABILITY_SPECS:
        summary[spec.level] += 1
    return summary


def format_capability_detail(kind: CapabilityKind, name: str) -> str:
    """Render one capability with tier guidance and rationale."""

    spec = get_capability(kind, name)
    if spec is None:
        return (
            f"No declared capability matched kind='{kind}' name='{name}'. "
            "Use list_capabilities() to inspect the current support boundary."
        )

    lines = [f"{spec.kind}: {spec.canonical}", f"Level: {spec.level}"]
    if spec.aliases:
        lines.append(f"Aliases: {', '.join(spec.aliases)}")
    if spec.rationale:
        lines.append(f"Rationale: {spec.rationale}")
    if spec.notes:
        lines.append(f"Notes: {spec.notes}")

    recommendation = {
        "core": "Recommendation: Safe default for SDK docs, examples, and the MCP happy path.",
        "advanced": "Recommendation: Supported, but keep behind explicit APIs and document it as an advanced pattern.",
        "recipe": "Recommendation: Treat as a recipe or showcase pattern, not a first-class SDK promise.",
        "unsupported": "Recommendation: Do not expose this as supported generation surface yet.",
    }[spec.level]
    lines.append(recommendation)
    return "\n".join(lines)


def format_capability_catalog() -> str:
    """Render the registry as a concise human-readable summary."""

    lines = ["cwtwb capability catalog", ""]
    summary = get_level_summary()
    lines.append(
        "Levels: "
        f"core={summary['core']}, "
        f"advanced={summary['advanced']}, "
        f"recipe={summary['recipe']}, "
        f"unsupported={summary['unsupported']}"
    )
    for level in ("core", "advanced", "recipe", "unsupported"):
        lines.append("")
        lines.append(f"[{level}]")
        level_items = list_capabilities(level=level)
        for spec in level_items:
            lines.append(f"- {spec.kind}: {spec.canonical}")
    return "\n".join(lines)


