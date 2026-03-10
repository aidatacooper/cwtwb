"""Workbook-oriented MCP tools."""

from __future__ import annotations

from typing import Optional

from ..charts.showcase_recipes import configure_chart_recipe as configure_chart_recipe_impl
from ..twb_editor import TWBEditor
from .app import server
from .state import get_editor, set_editor


@server.tool()
def create_workbook(template_path: str = "", workbook_name: str = "") -> str:
    """Create a new workbook from a TWB template file."""

    editor = TWBEditor(template_path)
    set_editor(editor)

    lines = []
    if workbook_name:
        lines.append(f"Workbook created: {workbook_name}")
    else:
        lines.append("Workbook created from template")
    lines.append("")
    lines.append(editor.list_fields())
    return "\n".join(lines)


@server.tool()
def list_fields() -> str:
    """List all available fields in the current workbook datasource."""

    editor = get_editor()
    return editor.list_fields()


@server.tool()
def add_calculated_field(
    field_name: str,
    formula: str,
    datatype: str = "real",
    role: str = "",
    field_type: str = "",
) -> str:
    """Add a calculated field to the datasource."""

    editor = get_editor()
    return editor.add_calculated_field(
        field_name,
        formula,
        datatype,
        role=role or None,
        field_type=field_type or None,
    )


@server.tool()
def remove_calculated_field(field_name: str) -> str:
    """Remove a previously added calculated field."""

    editor = get_editor()
    return editor.remove_calculated_field(field_name)


@server.tool()
def add_parameter(
    name: str,
    datatype: str = "real",
    default_value: str = "0",
    domain_type: str = "range",
    min_value: str = "",
    max_value: str = "",
    granularity: str = "",
    allowed_values: list[str] | None = None,
    default_format: str = "",
) -> str:
    """Add a parameter to the workbook."""

    editor = get_editor()
    return editor.add_parameter(
        name=name,
        datatype=datatype,
        default_value=default_value,
        domain_type=domain_type,
        min_value=min_value,
        max_value=max_value,
        granularity=granularity,
        allowed_values=allowed_values,
        default_format=default_format,
    )


@server.tool()
def add_worksheet(worksheet_name: str) -> str:
    """Add a new blank worksheet to the workbook."""

    editor = get_editor()
    return editor.add_worksheet(worksheet_name)


@server.tool()
def configure_chart(
    worksheet_name: str,
    mark_type: str = "Automatic",
    columns: list[str] | None = None,
    rows: list[str] | None = None,
    color: str | None = None,
    size: str | None = None,
    label: str | None = None,
    detail: str | None = None,
    wedge_size: str | None = None,
    sort_descending: str | None = None,
    tooltip: str | list[str] | None = None,
    filters: list[dict] | None = None,
    geographic_field: str | None = None,
    measure_values: list[str] | None = None,
    map_fields: list[str] | None = None,
) -> str:
    """Configure chart type and field mappings for a worksheet."""

    editor = get_editor()
    return editor.configure_chart(
        worksheet_name=worksheet_name,
        mark_type=mark_type,
        columns=columns,
        rows=rows,
        color=color,
        size=size,
        label=label,
        detail=detail,
        wedge_size=wedge_size,
        sort_descending=sort_descending,
        tooltip=tooltip,
        filters=filters,
        geographic_field=geographic_field,
        measure_values=measure_values,
        map_fields=map_fields,
    )


@server.tool()
def configure_dual_axis(
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
    reverse_axis_1: bool = False,
) -> str:
    """Configure a dual-axis chart composition."""

    editor = get_editor()
    return editor.configure_dual_axis(
        worksheet_name=worksheet_name,
        mark_type_1=mark_type_1,
        mark_type_2=mark_type_2,
        columns=columns,
        rows=rows,
        dual_axis_shelf=dual_axis_shelf,
        color_1=color_1,
        size_1=size_1,
        label_1=label_1,
        detail_1=detail_1,
        color_2=color_2,
        size_2=size_2,
        label_2=label_2,
        detail_2=detail_2,
        synchronized=synchronized,
        sort_descending=sort_descending,
        filters=filters,
        wedge_size_1=wedge_size_1,
        wedge_size_2=wedge_size_2,
        show_labels=show_labels,
        hide_axes=hide_axes,
        hide_zeroline=hide_zeroline,
        mark_sizing_off=mark_sizing_off,
        size_value_1=size_value_1,
        size_value_2=size_value_2,
        mark_color_2=mark_color_2,
        reverse_axis_1=reverse_axis_1,
    )


@server.tool()
def configure_chart_recipe(
    worksheet_name: str,
    recipe_name: str,
    recipe_args: dict[str, str] | None = None,
    auto_ensure_prerequisites: bool = True,
) -> str:
    """Configure a showcase recipe chart through the shared recipe registry."""

    editor = get_editor()
    return configure_chart_recipe_impl(
        editor,
        worksheet_name,
        recipe_name,
        recipe_args=recipe_args,
        auto_ensure_prerequisites=auto_ensure_prerequisites,
    )


@server.tool()
def set_mysql_connection(
    server: str,
    dbname: str,
    username: str,
    table_name: str,
    port: str = "3306",
) -> str:
    """Configure the workbook datasource to use a local MySQL connection."""

    editor = get_editor()
    return editor.set_mysql_connection(
        server=server,
        dbname=dbname,
        username=username,
        table_name=table_name,
        port=port,
    )


@server.tool()
def set_tableauserver_connection(
    server: str,
    dbname: str,
    username: str,
    table_name: str,
    directory: str = "/dataserver",
    port: str = "82",
) -> str:
    """Configure the workbook datasource to use a Tableau Server connection."""

    editor = get_editor()
    return editor.set_tableauserver_connection(
        server=server,
        dbname=dbname,
        username=username,
        table_name=table_name,
        directory=directory,
        port=port,
    )


@server.tool()
def set_hyper_connection(
    filepath: str,
    table_name: str = "Extract",
) -> str:
    """Configure the workbook datasource to use a local Hyper extract connection."""

    editor = get_editor()
    return editor.set_hyper_connection(
        filepath=filepath,
        table_name=table_name,
    )


@server.tool()
def add_dashboard(
    dashboard_name: str,
    worksheet_names: list[str],
    width: int = 1200,
    height: int = 800,
    layout: str | dict = "vertical",
) -> str:
    """Create a dashboard combining multiple worksheets."""

    editor = get_editor()
    return editor.add_dashboard(
        dashboard_name=dashboard_name,
        width=width,
        height=height,
        layout=layout,
        worksheet_names=worksheet_names,
    )


@server.tool()
def add_dashboard_action(
    dashboard_name: str,
    action_type: str,
    source_sheet: str,
    target_sheet: str,
    fields: list[str],
    event_type: str = "on-select",
    caption: str = "",
) -> str:
    """Add an interaction action to a dashboard."""

    editor = get_editor()
    return editor.add_dashboard_action(
        dashboard_name=dashboard_name,
        action_type=action_type,
        source_sheet=source_sheet,
        target_sheet=target_sheet,
        fields=fields,
        event_type=event_type,
        caption=caption,
    )


@server.tool()
def save_workbook(output_path: str) -> str:
    """Save the workbook as a TWB file."""

    editor = get_editor()
    return editor.save(output_path)
