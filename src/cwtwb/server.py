"""cwtwb MCP Server - Tableau Workbook (.twb) generation tools.

Provides the following MCP tools:
- create_workbook: Create a new workbook from template
- list_fields: List datasource fields
- add_calculated_field: Add a calculated field
- remove_calculated_field: Remove a calculated field
- add_worksheet: Add a worksheet
- configure_chart: Configure chart type and encodings
- add_dashboard: Create a dashboard
- save_workbook: Save the TWB file
"""

import json
import logging
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from .twb_editor import TWBEditor

logger = logging.getLogger(__name__)

# Resource paths
from .config import REFERENCES_DIR, TABLEAU_FUNCTIONS_JSON, SKILLS_DIR
from .capability_registry import format_capability_catalog
from .twb_analyzer import analyze_workbook

# ---------- MCP Server ----------

server = FastMCP(
    "cwtwb",
    instructions="Tableau Workbook (.twb) generation MCP Server. "
    "Create visualizations by calling create_workbook first, "
    "then add_worksheet + configure_chart, and finally save_workbook. "
    "For professional-quality output, read the agent skills "
    "(cwtwb://skills/index) before starting each phase.",
)

# Global state: current active TWBEditor instance
_editor: Optional[TWBEditor] = None


def _get_editor() -> TWBEditor:
    """Get the current editor instance, raising if none exists."""
    if _editor is None:
        raise RuntimeError(
            "No active workbook. Call create_workbook first."
        )
    return _editor


# ---------- Resources ----------

@server.resource("file://docs/tableau_all_functions.json")
def read_tableau_functions() -> str:
    """Read the complete list of Tableau calculation functions.
    
    Returns a JSON array of function objects, containing the syntax,
    definition, examples, and output data types for all documented
    Tableau functions.
    """
    if not TABLEAU_FUNCTIONS_JSON.exists():
        raise FileNotFoundError(f"Tableau functions JSON not found at: {TABLEAU_FUNCTIONS_JSON}")
    
    with TABLEAU_FUNCTIONS_JSON.open("r", encoding="utf-8") as f:
        return f.read()


# Available skill names (without .md extension)
_SKILL_NAMES = [
    "calculation_builder",
    "chart_builder",
    "dashboard_designer",
    "formatting",
]


@server.resource("cwtwb://skills/index")
def read_skills_index() -> str:
    """List all available cwtwb agent skills.

    Skills are expert-level guidance files that help AI agents produce
    professional-quality Tableau workbooks. Each skill focuses on one
    phase of the dashboard creation process.

    Workflow: calculation_builder -> chart_builder -> dashboard_designer -> formatting

    Returns:
        Index of available skills with descriptions.
    """
    lines = [
        "# cwtwb Agent Skills",
        "",
        "Load a skill before each phase for expert-level guidance.",
        "Read a skill with: read_resource('cwtwb://skills/<skill_name>')",
        "",
        "## Available Skills (in recommended order)",
        "",
    ]
    for name in _SKILL_NAMES:
        skill_path = SKILLS_DIR / f"{name}.md"
        if skill_path.exists():
            # Extract description from YAML frontmatter
            content = skill_path.read_text(encoding="utf-8")
            desc = ""
            for line in content.split("\n"):
                if line.startswith("description:"):
                    desc = line.split(":", 1)[1].strip()
                    break
            lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines)


@server.resource("cwtwb://skills/{skill_name}")
def read_skill(skill_name: str) -> str:
    """Read a specific cwtwb agent skill.

    Skills provide expert-level guidance for each phase of dashboard creation:
    - calculation_builder: Parameters, calculated fields, LOD expressions
    - chart_builder: Chart type selection, encodings, filters
    - dashboard_designer: Layout design, filter panels, interaction actions
    - formatting: Number formats, colors, sorting, tooltips

    Args:
        skill_name: Name of the skill (e.g. "chart_builder").

    Returns:
        Full skill content with best practices, examples, and checklists.
    """
    skill_path = SKILLS_DIR / f"{skill_name}.md"
    if not skill_path.exists():
        available = ", ".join(_SKILL_NAMES)
        raise FileNotFoundError(
            f"Skill '{skill_name}' not found. Available skills: {available}"
        )
    return skill_path.read_text(encoding="utf-8")


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
    global _editor
    _editor = TWBEditor(template_path)

    lines = []
    if workbook_name:
        lines.append(f"Workbook created: {workbook_name}")
    else:
        lines.append("Workbook created from template")
    lines.append("")
    lines.append(_editor.list_fields())
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
        mark_type: Chart mark type. One of:
            Bar, Line, Pie, Area, Circle, Square, Text, Map, Automatic.
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
    """Configure a dual-axis chart (e.g. Lollipop, Donut, Combo chart).
    
    IMPORTANT: The `dual_axis_shelf` (either "rows" or "columns") MUST contain the duplicate measure expressions at the end of the list.
    For example, for a horizontal Lollipop chart by Category and Sales:
    rows=["Category"], columns=["SUM(Sales)", "SUM(Sales)"], dual_axis_shelf="columns".

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
def generate_layout_json(
    output_path: str,
    layout_tree: dict,
    ascii_preview: str,
) -> str:
    """Generate and save a Dashboard layout JSON file.

    IMPORTANT: For complex custom layouts, you should always use this tool FIRST,
    and then pass the generated file path to `add_dashboard`. This avoids memory issues.

    Args:
        output_path: Absolute file path where the JSON should be saved (e.g. /output/layout.json).
        layout_tree: The nested dictionary representing the layout.
            Supported component 'type' values:
            - "container": A layout container. Requires 'direction' ("vertical" or "horizontal") and 'children' (list).
                           Optional: 'layout_strategy' (e.g., "distribute-evenly", "fixed-width"), 
                           'width' or 'height' (int) if sized fixedly.
            - "worksheet": A worksheet dashboard zone. Requires 'name' (string, matching the worksheet name).
                           Optional: 'weight' (int) to control proportional sizing within containers.
            - "filter": A quick filter control. Requires 'worksheet' (the target sheet name) and 'field' (the target field name).
                        Optional: 'mode' (e.g., "dropdown", "checkdropdown", or empty "" for default behavior).
            - "paramctrl": An interactive parameter control. Requires 'param' (name of the parameter).
            - "color": A color legend. Requires 'worksheet' (target sheet) and 'field' (the assigned color field).
        ascii_preview: REQUIRED. An ASCII string previewing the layout for human readers. 
            Use dashes, pipes, and brackets to represent containers and worksheets.

    Returns:
        Confirmation message with the exact absolute file path to pass to `add_dashboard`.
    """
    try:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        output_data = {}
        if ascii_preview:
            # Split ASCII by lines to make it clean in JSON
            output_data["_ascii_layout_preview"] = ascii_preview.strip().split("\n")
            
        output_data["layout_schema"] = layout_tree
        
        with open(path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
            
        return (
            f"Layout JSON successfully written to: {path.absolute()}\n"
            f"You can now call `add_dashboard` and set the `layout` parameter to exactly this file path."
        )
    except Exception as e:
        return f"Failed to generate layout JSON: {str(e)}"



@server.tool()
def list_capabilities() -> str:
    """List cwtwb's declared capability boundary.

    Returns:
        Human-readable catalog grouped by support level.
    """
    return format_capability_catalog()


@server.tool()
def analyze_twb(file_path: str) -> str:
    """Analyze a TWB file against cwtwb's declared capabilities.

    Args:
        file_path: Absolute or workspace-relative path to a .twb file.

    Returns:
        Summary of detected supported, recipe, and unsupported capabilities.
    """
    report = analyze_workbook(file_path)
    return report.to_text()


@server.tool()
def diff_template_gap(file_path: str) -> str:
    """Summarize the non-core capability gap of a TWB template.

    Args:
        file_path: Absolute or workspace-relative path to a .twb file.

    Returns:
        Decision-oriented summary of advanced, recipe-only, unsupported,
        and unknown capabilities.
    """
    report = analyze_workbook(file_path)
    return report.to_gap_text()

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
