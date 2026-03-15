"""Builder dispatch for chart configuration."""

from __future__ import annotations

from typing import Optional, Union

from .builder_basic import BasicChartBuilder
from .builder_dual_axis import DualAxisChartBuilder
from .builder_maps import MapChartBuilder
from .builder_pie import PieChartBuilder
from .builder_text import TextChartBuilder
from .routing_policy import ChartRouteProfile, profile_chart_request, profile_dual_axis_request


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
            label_runs=label_runs,
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
