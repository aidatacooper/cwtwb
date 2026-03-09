"""cwtwb MCP Server - Tableau Workbook (.twb) generation tools."""

import logging
from typing import Optional

from .twb_editor import TWBEditor

logger = logging.getLogger(__name__)

from .mcp.app import server
from .mcp.resources import read_skill, read_skills_index, read_tableau_functions
from .mcp.state import get_editor as _get_editor
from .mcp.state import set_editor as _set_editor
from .mcp.tools_layout import generate_layout_json
from .mcp.tools_support import (
    analyze_twb,
    describe_capability,
    diff_template_gap,
    list_capabilities,
)

# ---------- Tools ----------


@server.tool()
def create_workbook(template_path: str = "", workbook_name: str = "") -> str:
    """Create a new workbook from a TWB template file.

    This must be called first before using any other tools.
    It loads the template, parses all datasource fields,
    and clears existing worksheets.

    Args:
        template_path: Optional absolute path to a TWB template file to use. If omitted, an empty default template with a simple Superstore dataset is used.
        workbook_name: Optional display name for the workbook.

    Returns:
        Summary of loaded datasource and available fields.
    """
    editor = TWBEditor(template_path)
    _set_editor(editor)

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
    """List all available fields in the current workbook datasource.

    Shows dimensions and measures with their data types.
    Calculated fields are marked with [calculated].

    Returns:
        Formatted list of all fields.
    """
    editor = _get_editor()
    return editor.list_fields()


@server.tool()
def add_calculated_field(
    field_name: str,
    formula: str,
    datatype: str = "real",
) -> str:
    """Add a calculated field to the datasource.

    The formula should use Tableau calculation syntax.
    Field names in the formula should use the display names
    shown by list_fields (e.g. Sales, Profit).

    Args:
        field_name: Display name for the calculated field (e.g. "Profit Ratio").
        formula: Tableau calculation formula.
            Use field names wrapped in brackets, e.g.:
            - SUM([Profit])/SUM([Sales])
            - IF [Category] = "Technology" THEN 1 ELSE 0 END
        datatype: Result data type: real, string, integer, date, boolean.
            Default: real.

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
    return editor.add_calculated_field(field_name, formula, datatype)


@server.tool()
def remove_calculated_field(field_name: str) -> str:
    """Remove a previously added calculated field.

    Args:
        field_name: Display name of the calculated field to remove.

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    """Add a parameter to the workbook.

    Parameters are interactive controls that let users change values
    dynamically. They can be referenced in calculated fields using
    [Parameters].[ParameterName] syntax.

    Args:
        name: Display name for the parameter (e.g. "Target Profit").
        datatype: Data type: real, integer, string, date, boolean.
        default_value: Default/current value.
        domain_type: "range" (slider with min/max) or "list" (dropdown).
        min_value: Minimum value (range mode only).
        max_value: Maximum value (range mode only).
        granularity: Step size (range mode only).
        allowed_values: List of allowed values (list mode only).
        default_format: Optional Tableau number format string (e.g. "p0.00%").

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    """Add a new blank worksheet to the workbook.

    After adding, use configure_chart to set the chart type and fields.

    Args:
        worksheet_name: Name for the new worksheet.

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    """Configure chart type and field mappings for a worksheet.

    Field expressions use the format: AGGREGATION(FieldName) or just FieldName.

    Supported aggregations: SUM, AVG, COUNT, COUNTD, MIN, MAX, MEDIAN, ATTR.
    Supported date parts: YEAR, QUARTER, MONTH, DAY.

    Capability tiers:
    - Core primitives: Bar, Line, Area, Pie, Map, Text
    - Advanced patterns: Scatterplot, Heatmap, Tree Map, Bubble Chart
    - Recipe patterns such as Donut or Lollipop should usually be built from
      explicit dual-axis or helper workflows instead of being treated as
      first-class chart primitives.

    For Pie charts, use 'color' for the slice dimension
    and 'wedge_size' for the measure (leave columns/rows empty).

    For Bar/Line charts, put dimensions in rows and measures in columns
    (or vice versa).

    For Map charts (mark_type="Map"), set 'geographic_field' to the
    geographic dimension (e.g. "State/Province"). The map automatically
    uses generated Latitude/Longitude fields. You can also set 'color'
    and 'size' encodings on the map.

    Args:
        worksheet_name: Target worksheet name.
        mark_type: Chart mark type or higher-level chart pattern. Common choices:
            Bar, Line, Pie, Area, Text, Map, Scatterplot, Heatmap,
            Tree Map, Bubble Chart, Circle, Square, Automatic.
        columns: Column shelf field expressions (e.g. ["SUM(Sales)"]).
        rows: Row shelf field expressions (e.g. ["Category"]).
        color: Color encoding field expression.
        size: Size encoding field expression.
        label: Label encoding field expression.
        detail: Detail encoding field expression.
        wedge_size: Pie chart wedge size field expression (e.g. "SUM(Sales)").
        sort_descending: Sort dimension descending by this measure (e.g. "SUM(Sales)").
        tooltip: Tooltip encoding field expression(s). Can be a single string or list of strings.
        filters: List of filters. Supports both categorical (e.g. [{"column": "Region"}]) and quantitative range filters (e.g. [{"column": "Order Date", "type": "quantitative"}]).
        geographic_field: Geographic dimension for Map charts (e.g. "State/Province").
        measure_values: List of measure expressions for Measure Names/Values mode.
            Creates a KPI card showing multiple measures as a text table.
            E.g. ["SUM(Sales)", "SUM(Profit)", "Profit Ratio", "AVG(Discount)"].
        map_fields: Additional geographic fields to add as LOD (level of detail) on Map charts.
            E.g. ["Country/Region", "City"]. Use this to specify which geographic hierarchy
            fields the map should include beyond the primary geographic_field.

    Returns:
        Confirmation message.

    Examples:
        # Bar chart: Category vs Sales
        configure_chart("Sheet1", mark_type="Bar",
                        rows=["Category"], columns=["SUM(Sales)"])

        # Pie chart: Segment by Sales
        configure_chart("Sheet1", mark_type="Pie",
                        color="Segment", wedge_size="SUM(Sales)")

        # Line chart: Monthly sales trend
        configure_chart("Sheet1", mark_type="Line",
                        columns=["MONTH(Order Date)"],
                        rows=["SUM(Sales)"])

        # Map chart: Sales by State
        configure_chart("Sheet1", mark_type="Map",
                        geographic_field="State/Province",
                        color="SUM(Sales)", size="SUM(Profit)",
                        map_fields=["Country/Region"])

        # KPI card: Multiple measures
        configure_chart("Sheet1", mark_type="Text",
                        measure_values=["SUM(Sales)", "SUM(Profit)",
                                        "Profit Ratio", "AVG(Discount)"])
    """
    editor = _get_editor()
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
) -> str:
    """Configure a dual-axis chart composition.
    
    IMPORTANT: The `dual_axis_shelf` (either "rows" or "columns") MUST contain the duplicate measure expressions at the end of the list.
    For example, for a horizontal Lollipop chart by Category and Sales:
    rows=["Category"], columns=["SUM(Sales)", "SUM(Sales)"], dual_axis_shelf="columns".

    This is an advanced building block and is often the basis for recipe-level
    patterns such as Lollipop or Donut charts.

    Args:
        worksheet_name: Target worksheet name.
        mark_type_1: Mark type for the primary axis (e.g., "Bar").
        mark_type_2: Mark type for the secondary axis (e.g., "Circle").
        columns: Column shelf field expressions.
        rows: Row shelf field expressions.
        dual_axis_shelf: Which shelf contains the dual measures ("rows" or "columns").
        color_1: Color encoding for primary axis.
        size_1: Size encoding for primary axis.
        label_1: Label encoding for primary axis.
        detail_1: Detail encoding for primary axis.
        color_2: Color encoding for secondary axis.
        size_2: Size encoding for secondary axis.
        label_2: Label encoding for secondary axis.
        detail_2: Detail encoding for secondary axis.
        synchronized: Whether to synchronize the secondary axis with the primary.
        sort_descending: Sort dimension descending by this measure.
        filters: List of filters.

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    )



@server.tool()
def set_mysql_connection(
    server: str,
    dbname: str,
    username: str,
    table_name: str,
    port: str = "3306",
) -> str:
    """Configure the workbook datasource to use a Local MySQL connection.

    Args:
        server: MySQL server address (e.g. "127.0.0.1")
        dbname: Database name
        username: Database username
        table_name: Table name to query
        port: MySQL port (default: 3306)

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    """Configure the workbook datasource to use a Tableau Server connection.

    Args:
        server: Tableau Server address (e.g. "xxx.com")
        dbname: Database name on Tableau Server
        username: Username (can be empty)
        table_name: Target table name
        directory: Directory path on server (default: "/dataserver")
        port: Port number (default: 82. Common options: 80, 443, 82)

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    """Configure the workbook datasource to use a local Hyper extract connection.

    Args:
        filepath: Absolute path to the .hyper file.
        table_name: Target table name inside the hyper file (default is usually "Extract" but may vary).

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    """Create a dashboard combining multiple worksheets.

    Args:
        dashboard_name: Name for the dashboard.
        worksheet_names: List of worksheet names to include.
        width: Canvas width in pixels. Default: 1200.
        height: Canvas height in pixels. Default: 800.
        layout: Layout type. One of:
            - "vertical": Stack worksheets vertically.
            - "horizontal": Place worksheets side by side.
            - "grid-2x2": 2x2 grid layout (max 4 worksheets).
            - A nested `dict` defining a complex declarative JSON layout.
            - An absolute file path to a .json file containing the layout dictionary.
        
        CRITICAL: If you want to use a nested dict for a complex layout, DO NOT pass it directly here
        to avoid payload size errors. You MUST FIRST call `generate_layout_json` to save it to a file,
        and then pass the absolute file path generated by that tool to this `layout` parameter.

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    """Add an interaction action to a dashboard.

    Supports 'filter' or 'highlight' actions between two worksheets on the dashboard.

    Args:
        dashboard_name: The name of the dashboard containing the source worksheet.
        action_type: Type of action ('filter' or 'highlight').
        source_sheet: The worksheet triggering the action.
        target_sheet: The worksheet being affected by the action.
        fields: List of fields to match on (e.g., ["Region", "State"]).
        event_type: Trigger event ('on-select', 'on-hover', 'on-menu'). Default is 'on-select'.
        caption: Optional caption for the action.

    Returns:
        Confirmation message.
    """
    editor = _get_editor()
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
    """Save the workbook as a TWB file.

    The file can be opened directly with Tableau Desktop.

    Args:
        output_path: Absolute path for the output .twb file.

    Returns:
        Confirmation message with the output path.
    """
    editor = _get_editor()
    return editor.save(output_path)


# ---------- Entry point ----------


def main():
    """Run the MCP server via stdio transport."""
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
