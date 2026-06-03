"""Builder dispatch for chart configuration.

This module is the routing layer between the stable public API (ChartsMixin)
and the concrete builder implementations.  It answers two questions:

  1. Which builder class should handle this request?
     → profile_chart_request() maps mark_type + feature flags
       to a ChartRouteProfile (builder_name: "basic" | "text" | "pie" | "map").

  2. How should arguments be forwarded to that builder?
     → configure_chart() and configure_dual_axis() are thin adapter functions
       that instantiate the right builder and call build().

Call chain (for a standard chart):
  ChartsMixin.configure_chart()
    → dispatcher.configure_chart()
      → decide_chart_builder() → ChartRouteProfile
        → BasicChartBuilder / TextChartBuilder / PieChartBuilder / MapChartBuilder
          → builder.build() → mutates editor.root (lxml tree), returns worksheet_name

For dual-axis charts the chain ends at DualAxisChartBuilder instead.
No business logic lives here — all XML mutation is in the builder classes.
"""
from __future__ import annotations

__author__ = "Cooper Wenhua <imgwho@gmail.com>"


from dataclasses import dataclass
from typing import Optional, Union

from ..capability_registry import CapabilityLevel, get_capability
from .builder_base import BasicChartBuilder, MapChartBuilder, PieChartBuilder, TextChartBuilder
from .builder_dual_axis import DualAxisChartBuilder


# ---------------------------------------------------------------------------
# Chart pattern normalization (formerly pattern_mapping.py)
# ---------------------------------------------------------------------------

# Tableau 18.1 mark class enumeration (from workbook XSD).
# Any mark class not in this set is rejected by the runtime, so we never write
# an invalid value into <mark class="…"/>.
# ``Multipolygon`` is a map-layer-only class accepted by the same schema.
TABLEAU_MARK_CLASSES: frozenset[str] = frozenset({
    "Automatic",
    "Bar",
    "Line",
    "Area",
    "Circle",
    "Square",
    "Shape",
    "Pie",
    "Polygon",
    "GanttBar",
    "Text",
    "Map",
    "Multipolygon",
})

# Friendly aliases → underlying Tableau mark class.
# Keep the alias set conservative: every key must map to a real Tableau class.
MARK_ALIASES: dict[str, str] = {
    "Scatterplot": "Circle",
    "Scatter": "Circle",
    "Bubble Chart": "Circle",
    "Heatmap": "Square",
    "Tree Map": "Square",
}


@dataclass(frozen=True)
class PatternResolution:
    """Normalized mark configuration for basic-chart style builders."""

    requested_mark_type: str
    actual_mark_type: str
    columns: list[str]
    rows: list[str]


def normalize_chart_pattern(
    mark_type: str,
    columns: list[str] | None = None,
    rows: list[str] | None = None,
    color: str | None = None,
) -> PatternResolution:
    """Resolve advanced chart aliases onto their underlying Tableau marks.

    Known aliases (e.g. ``"Scatterplot"``, ``"Tree Map"``) and the canonical
    Tableau mark classes are mapped to a primitive mark string.  Unrecognised
    inputs are passed through unchanged so that recipe-level patterns such as
    ``"Donut"`` can still reach their specialised handling downstream.

    The canonical mark-class list is exported as :data:`TABLEAU_MARK_CLASSES`
    and the alias mapping as :data:`MARK_ALIASES` so that builders can perform
    their own validation at XML-write time without affecting routing policy.
    """

    resolved_columns = list(columns or [])
    resolved_rows = list(rows or [])

    if mark_type in MARK_ALIASES:
        actual_mark_type = MARK_ALIASES[mark_type]
    else:
        actual_mark_type = mark_type

    if mark_type in ("Tree Map", "Bubble Chart"):
        resolved_columns = []
        resolved_rows = []

    return PatternResolution(
        requested_mark_type=mark_type,
        actual_mark_type=actual_mark_type,
        columns=resolved_columns,
        rows=resolved_rows,
    )


# ---------------------------------------------------------------------------
# Routing policy (formerly routing_policy.py)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChartRouteProfile:
    """Resolved routing profile for a chart request."""

    requested_mark_type: str
    actual_mark_type: str
    support_level: CapabilityLevel | None
    route_family: str
    builder_name: str


def _resolve_support_level(mark_type: str) -> CapabilityLevel | None:
    """Resolve declared support tier for a requested chart/mark label."""
    spec = get_capability("chart", mark_type)
    return None if spec is None else spec.level


def profile_chart_request(mark_type: str, *, measure_values_mode: bool = False) -> ChartRouteProfile:
    """Classify a chart request without changing compatibility behavior."""

    if mark_type == "Text":
        return ChartRouteProfile(
            requested_mark_type=mark_type,
            actual_mark_type="Text",
            support_level=_resolve_support_level(mark_type),
            route_family="primitive",
            builder_name="text",
        )

    if mark_type == "Pie":
        return ChartRouteProfile(
            requested_mark_type=mark_type,
            actual_mark_type="Pie",
            support_level=_resolve_support_level(mark_type),
            route_family="primitive",
            builder_name="pie",
        )

    if mark_type == "Map":
        return ChartRouteProfile(
            requested_mark_type=mark_type,
            actual_mark_type="Map",
            support_level=_resolve_support_level(mark_type),
            route_family="primitive",
            builder_name="map",
        )

    normalized = normalize_chart_pattern(mark_type)
    support_level = _resolve_support_level(mark_type)

    if support_level == "advanced":
        route_family = "pattern"
    elif support_level == "recipe":
        route_family = "compatibility"
    else:
        route_family = "primitive"

    return ChartRouteProfile(
        requested_mark_type=mark_type,
        actual_mark_type=normalized.actual_mark_type,
        support_level=support_level,
        route_family=route_family,
        builder_name="basic",
    )


def profile_dual_axis_request() -> ChartRouteProfile:
    """Classify the dual-axis path as an advanced composition route."""

    return ChartRouteProfile(
        requested_mark_type="Dual Axis",
        actual_mark_type="Dual Axis",
        support_level=_resolve_support_level("Dual Axis"),
        route_family="composition",
        builder_name="dual_axis",
    )


# ---------------------------------------------------------------------------
# Dispatch (original dispatcher.py)
# ---------------------------------------------------------------------------

def decide_chart_builder(mark_type: str, *, measure_values: Optional[list[str]] = None) -> ChartRouteProfile:
    """Choose the stable builder layer for a chart request."""

    return profile_chart_request(mark_type, measure_values_mode=bool(measure_values))


def decide_dual_axis_builder() -> ChartRouteProfile:
    """Choose the stable builder layer for a dual-axis request."""

    return profile_dual_axis_request()


def configure_chart(
    editor,
    worksheet_name: str,
    mark_type: str = "Automatic",
    columns: Optional[list[str]] = None,
    rows: Optional[list[str]] = None,
    color: Optional[str] = None,
    size: Optional[str] = None,
    label: Optional[str] = None,
    detail: Optional[str] = None,
    wedge_size: Optional[str] = None,
    sort_descending: Optional[str] = None,
    tooltip: Optional[Union[str, list[str]]] = None,
    filters: Optional[list[dict]] = None,
    geographic_field: Optional[str] = None,
    measure_values: Optional[list[str]] = None,
    map_fields: Optional[list[str]] = None,
    mark_sizing_off: bool = False,
    axis_fixed_range: Optional[dict] = None,
    customized_label: Optional[str] = None,
    color_map: Optional[dict[str, str]] = None,
    text_format: Optional[dict[str, str]] = None,
    map_layers: Optional[list[dict]] = None,
    label_extra: Optional[list[str]] = None,
    label_runs: Optional[list[dict]] = None,
    label_param: Optional[str] = None,
) -> str:
    """Route chart configuration to the correct builder."""

    decision = decide_chart_builder(mark_type, measure_values=measure_values)

    if decision.builder_name == "pie" and (color or wedge_size):
        builder = PieChartBuilder(
            editor, worksheet_name, color, wedge_size, label, detail, tooltip, filters
        )
        return builder.build()

    if decision.builder_name == "map":
        builder = MapChartBuilder(
            editor,
            worksheet_name,
            geographic_field,
            color,
            size,
            label,
            detail,
            tooltip,
            map_fields,
            filters,
            map_layers=map_layers,
        )
        return builder.build()

    if decision.builder_name == "text":
        builder = TextChartBuilder(
            editor,
            worksheet_name,
            columns,
            rows,
            color,
            size,
            label,
            detail,
            sort_descending,
            tooltip,
            filters,
            measure_values,
            label_extra=label_extra,
            label_runs=label_runs,
            label_param=label_param,
        )
        return builder.build()

    builder = BasicChartBuilder(
        editor,
        worksheet_name,
        mark_type,
        columns,
        rows,
        color,
        size,
        label,
        detail,
        sort_descending,
        tooltip,
        filters,
        mark_sizing_off=mark_sizing_off,
        axis_fixed_range=axis_fixed_range,
        customized_label=customized_label,
        color_map=color_map,
        text_format=text_format,
        label_extra=label_extra,
        label_runs=label_runs,
    )
    return builder.build()


def configure_dual_axis(
    editor,
    worksheet_name: str,
    mark_type_1: str = "Bar",
    mark_type_2: str = "Line",
    columns: Optional[list[str]] = None,
    rows: Optional[list[str]] = None,
    dual_axis_shelf: str = "rows",
    color_1: Optional[str] = None,
    size_1: Optional[str] = None,
    label_1: Optional[str] = None,
    detail_1: Optional[str] = None,
    color_2: Optional[str] = None,
    size_2: Optional[str] = None,
    label_2: Optional[str] = None,
    detail_2: Optional[str] = None,
    synchronized: bool = True,
    sort_descending: Optional[str] = None,
    filters: Optional[list[dict]] = None,
    wedge_size_1: Optional[str] = None,
    wedge_size_2: Optional[str] = None,
    show_labels: bool = True,
    hide_axes: bool = False,
    hide_zeroline: bool = False,
    mark_sizing_off: bool = False,
    size_value_1: Optional[str] = None,
    size_value_2: Optional[str] = None,
    mark_color_2: Optional[str] = None,
    mark_color_1: Optional[str] = None,
    reverse_axis_1: bool = False,
    extra_axes: Optional[list[dict]] = None,
    color_map_1: Optional[dict[str, str]] = None,
) -> str:
    """Route dual-axis configuration to the dedicated builder."""

    _ = decide_dual_axis_builder()
    builder = DualAxisChartBuilder(
        editor,
        worksheet_name,
        mark_type_1,
        mark_type_2,
        columns,
        rows,
        dual_axis_shelf,
        color_1,
        size_1,
        label_1,
        detail_1,
        color_2,
        size_2,
        label_2,
        detail_2,
        synchronized,
        sort_descending,
        filters,
        wedge_size_1,
        wedge_size_2,
        show_labels,
        hide_axes,
        hide_zeroline,
        mark_sizing_off,
        size_value_1,
        size_value_2,
        mark_color_2,
        mark_color_1=mark_color_1,
        reverse_axis_1=reverse_axis_1,
        extra_axes=extra_axes,
        color_map_1=color_map_1,
    )
    return builder.build()
