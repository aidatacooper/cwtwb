"""Workbook-oriented MCP tools — the primary entry points for AI agents.

STATEFUL SESSION MODEL
----------------------
The MCP server holds a single TWBEditor instance in mcp.state._editor.
Tools must be called in this order within each session:

  1. create_workbook(template_path)  OR  open_workbook(file_path)
       → Loads/creates a TWBEditor, stores it in state via set_editor().
  2. list_fields()
       → Inspect which datasource fields are available.
  3. add_worksheet(name)  [repeat as needed]
  4. configure_chart(name, ...) / configure_dual_axis(name, ...)
  5. configure_worksheet_style(name, ...)  [optional per sheet]
  6. add_dashboard(name, worksheet_names=[...])
  7. save_workbook(output_path)

Any tool that calls get_editor() will raise RuntimeError if step 1 was skipped.

TOOL INVENTORY
--------------
  create_workbook    — load a TWB/TWBX template into the active session
  open_workbook      — alias for create_workbook that also shows workbook state
  list_fields        — return datasource field list from the active editor
  list_worksheets    — return worksheet names in the active workbook
  list_dashboards    — return dashboard names and their zone worksheet lists
  add_worksheet      — append a blank worksheet to the workbook
  configure_chart    — set mark type, shelves, encodings, filters for a worksheet
  configure_dual_axis — set up a two-pane overlaid chart
  configure_chart_recipe — apply a named showcase recipe (e.g. "lollipop")
  configure_worksheet_style — apply background, axis, grid, cell formatting
  add_dashboard      — create a dashboard from a list of worksheet names
  add_dashboard_action — wire filter/highlight interactions between sheets
  set_excel_connection / set_csv_connection — replace the datasource connection with a local tabular file
  set_mysql_connection / set_tableauserver_connection / set_hyper_connection
                     — replace the datasource connection in the workbook
  save_workbook      — serialize and write the current editor to a .twb/.twbx file
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Optional

# Skill reference mapping: tool_name -> skill_name
_SKILL_REFERENCES = {
    "add_calculated_field": "calculation_builder",
    "configure_chart": "chart_builder",
    "configure_dual_axis": "chart_builder",
    "configure_chart_recipe": "chart_builder",
    "configure_worksheet_style": "formatting",
    "add_dashboard": "dashboard_designer",
}


def _skill_hint(tool_name: str) -> str:
    """Generate a skill reference hint for a tool."""
    skill = _SKILL_REFERENCES.get(tool_name)
    if not skill:
        return ""
    return f"\n\n📖 For best practices, read: read_resource('cwtwb://skills/{skill}')"

from ..capability_registry import format_capability_catalog, format_capability_detail
from ..charts.showcase_recipes import configure_chart_recipe as configure_chart_recipe_impl
from ..connections import (
    _column_values_from_rows,
    _excel_grid_origin,
    _infer_external_field_type,
    _infer_external_role,
    _infer_excel_datatype,
    _list_excel_sheet_names,
    _read_excel_sheet_rows,
    _sanitize_headers,
    infer_tableau_semantic_role,
)
from ..dashboards import write_dashboard_layout_file
from ..migration import (
    apply_twb_migration_json,
    inspect_target_schema as inspect_target_schema_impl,
    migrate_twb_guided_json,
    profile_twb_for_migration_json,
    propose_field_mapping_json,
    preview_twb_migration_json,
)
from ..twb_analyzer import analyze_workbook
from ..twb_editor import TWBEditor
from ..validator import TWBValidationError, load_workbook_root, validate_against_schema
from .app import get_editor, server, set_editor


def _format_worksheets(editor: TWBEditor) -> str:
    """Render worksheet names as a compact human-readable section."""
    worksheets = editor.list_worksheets()
    if not worksheets:
        return "=== Worksheets ===\n  (none)"
    lines = ["=== Worksheets ==="]
    lines.extend(f"  {name}" for name in worksheets)
    return "\n".join(lines)


def _format_dashboards(editor: TWBEditor) -> str:
    """Render dashboard names with worksheet-zone membership details."""
    dashboards = editor.list_dashboards()
    if not dashboards:
        return "=== Dashboards ===\n  (none)"

    lines = ["=== Dashboards ==="]
    for dashboard in dashboards:
        name = dashboard["name"]
        worksheet_names = dashboard["worksheets"]
        joined = ", ".join(worksheet_names) if worksheet_names else "(no worksheet zones)"
        lines.append(f"  {name}: {joined}")
    return "\n".join(lines)


@server.tool()
def create_workbook(template_path: str = "", workbook_name: str = "") -> str:
    """Create a new workbook from a TWB or TWBX template file."""

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
def open_workbook(file_path: str) -> str:
    """Open an existing workbook (.twb or .twbx) for in-place worksheet editing."""

    editor = TWBEditor.open_existing(file_path)
    set_editor(editor)

    lines = [f"Workbook opened: {file_path}", "", _format_worksheets(editor), "", _format_dashboards(editor)]
    return "\n".join(lines)


@server.tool()
def list_fields() -> str:
    """List all available fields in the current workbook datasource."""

    editor = get_editor()
    return editor.list_fields()


@server.tool()
def list_worksheets() -> str:
    """List worksheet names in the current workbook."""

    editor = get_editor()
    return _format_worksheets(editor)


@server.tool()
def list_dashboards() -> str:
    """List dashboards and their worksheet zones in the current workbook."""

    editor = get_editor()
    return _format_dashboards(editor)


@server.tool()
def add_calculated_field(
    field_name: str,
    formula: str,
    datatype: str = "real",
    role: str = "",
    field_type: str = "",
    default_format: str = "",
    internal_name: str = "",
) -> str:
    """Add a calculated field to the datasource.

    For formula syntax and best practices, read: read_resource('cwtwb://skills/calculation_builder')
    """

    editor = get_editor()
    result = editor.add_calculated_field(
        field_name,
        formula,
        datatype,
        role=role or None,
        field_type=field_type or None,
        default_format=default_format,
        internal_name=internal_name or None,
    )
    return result + _skill_hint("add_calculated_field")


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
    internal_name: str = "",
    alias: str = "",
    allowed_aliases: dict[str, str] | None = None,
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
        internal_name=internal_name or None,
        alias=alias or None,
        allowed_aliases=allowed_aliases,
    )


@server.tool()
def add_worksheet(worksheet_name: str) -> str:
    """Add a new blank worksheet to the workbook."""

    editor = get_editor()
    return editor.add_worksheet(worksheet_name)


@server.tool()
def clone_worksheet(source_worksheet: str, target_worksheet: str) -> str:
    """Clone an existing worksheet and its worksheet window."""

    editor = get_editor()
    return editor.clone_worksheet(source_worksheet, target_worksheet)


@server.tool()
def preview_worksheet_refactor(
    worksheet_name: str,
    replacements: dict[str, str],
) -> str:
    """Preview worksheet-scoped field rewrites without mutating the workbook."""

    import json

    editor = get_editor()
    return json.dumps(
        editor.preview_worksheet_refactor(worksheet_name, replacements),
        ensure_ascii=False,
        indent=2,
    )


@server.tool()
def apply_worksheet_refactor(
    worksheet_name: str,
    replacements: dict[str, str],
) -> str:
    """Rewrite one worksheet to use replacement fields without touching others."""

    import json

    editor = get_editor()
    return json.dumps(
        editor.apply_worksheet_refactor(worksheet_name, replacements),
        ensure_ascii=False,
        indent=2,
    )


@server.tool()
def set_worksheet_caption(worksheet_name: str, caption: str) -> str:
    """Set or clear a plain-text worksheet caption."""

    editor = get_editor()
    return editor.set_worksheet_caption(worksheet_name, caption)


@server.tool()
def set_worksheet_hidden(worksheet_name: str, hidden: bool = True) -> str:
    """Hide or unhide a worksheet tab by updating worksheet window metadata."""

    editor = get_editor()
    return editor.set_worksheet_hidden(worksheet_name, hidden=hidden)


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
    mark_sizing_off: bool = False,
    axis_fixed_range: dict | None = None,
    customized_label: str | None = None,
    color_map: dict[str, str] | None = None,
    text_format: dict[str, str] | None = None,
    map_layers: list[dict] | None = None,
    label_runs: list[dict] | None = None,
    label_param: str | None = None,
) -> str:
    """Configure chart type and field mappings for a worksheet.

    For chart type selection and encoding best practices, read: read_resource('cwtwb://skills/chart_builder')
    """

    editor = get_editor()
    result = editor.configure_chart(
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
        mark_sizing_off=mark_sizing_off,
        axis_fixed_range=axis_fixed_range,
        customized_label=customized_label,
        color_map=color_map,
        text_format=text_format,
        map_layers=map_layers,
        label_runs=label_runs,
        label_param=label_param,
    )
    return result + _skill_hint("configure_chart")


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
    mark_color_1: Optional[str] = None,
    reverse_axis_1: bool = False,
    color_map_1: Optional[dict[str, str]] = None,
) -> str:
    """Configure a dual-axis chart composition.

    For dual-axis chart patterns and best practices, read: read_resource('cwtwb://skills/chart_builder')
    """

    editor = get_editor()
    result = editor.configure_dual_axis(
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
        mark_color_1=mark_color_1,
        reverse_axis_1=reverse_axis_1,
        color_map_1=color_map_1,
    )
    return result + _skill_hint("configure_dual_axis")


@server.tool()
def configure_worksheet_style(
    worksheet_name: str,
    background_color: str | None = None,
    hide_axes: bool = False,
    hide_gridlines: bool = False,
    hide_zeroline: bool = False,
    hide_borders: bool = False,
    hide_band_color: bool = False,
    hide_col_field_labels: bool = False,
    hide_row_field_labels: bool = False,
    hide_droplines: bool = False,
    hide_reflines: bool = False,
    hide_table_dividers: bool = False,
    disable_tooltip: bool = False,
    pane_cell_style: dict | None = None,
    pane_datalabel_style: dict | None = None,
    pane_mark_style: dict | None = None,
    pane_trendline_hidden: bool = False,
    label_formats: list[dict] | None = None,
    cell_formats: list[dict] | None = None,
    header_formats: list[dict] | None = None,
    axis_style: dict | None = None,
) -> str:
    """Apply worksheet-level styling: background color, axis/grid/border visibility.

    For formatting best practices, read: read_resource('cwtwb://skills/formatting')
    """

    editor = get_editor()
    result = editor.configure_worksheet_style(
        worksheet_name=worksheet_name,
        background_color=background_color,
        hide_axes=hide_axes,
        hide_gridlines=hide_gridlines,
        hide_zeroline=hide_zeroline,
        hide_borders=hide_borders,
        hide_band_color=hide_band_color,
        hide_col_field_labels=hide_col_field_labels,
        hide_row_field_labels=hide_row_field_labels,
        hide_droplines=hide_droplines,
        hide_reflines=hide_reflines,
        hide_table_dividers=hide_table_dividers,
        disable_tooltip=disable_tooltip,
        pane_cell_style=pane_cell_style,
        pane_datalabel_style=pane_datalabel_style,
        pane_mark_style=pane_mark_style,
        pane_trendline_hidden=pane_trendline_hidden,
        label_formats=label_formats,
        cell_formats=cell_formats,
        header_formats=header_formats,
        axis_style=axis_style,
    )
    return result + _skill_hint("configure_worksheet_style")


@server.tool()
def configure_chart_recipe(
    worksheet_name: str,
    recipe_name: str,
    recipe_args: dict[str, str] | None = None,
    auto_ensure_prerequisites: bool = True,
) -> str:
    """Configure a showcase recipe chart through the shared recipe registry.

    For recipe chart patterns, read: read_resource('cwtwb://skills/chart_builder')
    """

    editor = get_editor()
    result = configure_chart_recipe_impl(
        editor,
        worksheet_name,
        recipe_name,
        recipe_args=recipe_args,
        auto_ensure_prerequisites=auto_ensure_prerequisites,
    )
    return result + _skill_hint("configure_chart_recipe")


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
    """Configure the workbook datasource to use a Tableau Server connection.

    This edits the workbook datasource connection only. It does not configure
    Tableau REST API/PAT credentials for validate_workbook_api, upload_workbook,
    or screenshot_workbook; pass env_path to those validation tools instead.
    """

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
def set_excel_connection(
    filepath: str,
    sheet_name: str = "",
    fields: list[dict] | None = None,
) -> str:
    """Configure the workbook datasource to use a local Excel connection."""

    editor = get_editor()
    return editor.set_excel_connection(
        filepath=filepath,
        sheet_name=sheet_name,
        fields=fields,
    )


@server.tool()
def set_csv_connection(
    filepath: str,
    delimiter: str = "",
    charset: str = "utf-8-sig",
    fields: list[dict] | None = None,
) -> str:
    """Configure the workbook datasource to use a local CSV connection."""

    editor = get_editor()
    return editor.set_csv_connection(
        filepath=filepath,
        delimiter=delimiter,
        charset=charset,
        fields=fields,
    )


@server.tool()
def set_hyper_connection(
    filepath: str,
    table_name: str = "Extract",
    tables: list[dict] | None = None,
) -> str:
    """Configure the workbook datasource to use a local Hyper extract connection."""

    editor = get_editor()
    return editor.set_hyper_connection(
        filepath=filepath,
        table_name=table_name,
        tables=tables,
    )


@server.tool()
def add_dashboard(
    dashboard_name: str,
    worksheet_names: list[str],
    width: int = 1200,
    height: int = 800,
    layout: str | dict = "auto",
) -> str:
    """Create a dashboard combining multiple worksheets.

    Recommended workflow for complex dashboards:
    1. Call list_worksheets to lock worksheet names
    2. Design layout with the user (KPI row, main chart, detail views, filters)
    3. Call generate_layout_json to save the layout as a JSON or YAML file
    4. Call add_dashboard with layout=<layout_file_path>

    Layout options:
    - str (file path): Path to JSON or YAML layout file (recommended for complex layouts)
    - dict: Custom declarative layout tree passed inline
    - "auto" (default): Simple vertical fallback — use layout dict or layout file for mixed layouts
    - "vertical": All worksheets stacked vertically
    - "horizontal": All worksheets side-by-side
    - "grid-2x2": 2x2 grid layout

    For dashboard design best practices, read: read_resource('cwtwb://skills/dashboard_designer')
    """

    editor = get_editor()
    result = editor.add_dashboard(
        dashboard_name=dashboard_name,
        width=width,
        height=height,
        layout=layout,
        worksheet_names=worksheet_names,
    )
    return result + _skill_hint("add_dashboard")


@server.tool()
def add_dashboard_action(
    dashboard_name: str,
    action_type: str,
    source_sheet: str,
    target_sheet: str = "",
    fields: list[str] | None = None,
    event_type: str = "on-select",
    caption: str = "",
    url: str = "",
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
        url=url,
    )


@server.tool()
def save_workbook(output_path: str) -> str:
    """Save the active workbook as a .twb or .twbx file. Use a .twbx extension to produce a
    packaged workbook (ZIP) that bundles the XML with any data extracts and
    images carried over from the source .twbx.

    This is the only default MCP tool that writes the active in-memory workbook
    to disk. After create_workbook/open_workbook plus worksheet/chart/dashboard
    edits, call save_workbook with the desired output_path to create the final
    .twb or .twbx file. validate_workbook and analyze_twb do not save files.
    """

    editor = get_editor()
    return editor.save(output_path)


# --- Layout tools ---


@server.tool()
def generate_layout_json(
    output_path: str,
    layout_tree: dict,
    ascii_preview: str,
) -> str:
    """Generate and save a dashboard layout file.

    Recommended workflow:
    1. Call list_worksheets to get available worksheet names
    2. Design the layout with the user (show ASCII preview for confirmation)
    3. Call this tool to save the layout as a JSON or YAML file
    4. Call add_dashboard with layout=<this_file_path>

    The layout_tree uses the declarative container DSL:
    - {"type": "container", "direction": "vertical"|"horizontal", "children": [...]}
    - {"type": "worksheet", "name": "<worksheet_name>"}
    - Use "fixed_size" (int, pixels) for KPI rows and filter sidebars
    - Use "weight" (int, relative) for main analytical areas
    """

    try:
        if not isinstance(layout_tree, dict):
            return "Failed to generate layout JSON: layout_tree must be an object."

        path = write_dashboard_layout_file(
            output_path=output_path,
            layout_tree=layout_tree,
            ascii_preview=ascii_preview,
        )

        return (
            f"Layout file successfully written to: {path.absolute()}\n"
            f"You can now call `add_dashboard` and set the `layout` parameter to exactly this file path."
        )
    except ValueError as e:
        return (
            "Failed to generate layout JSON: layout_tree is not a supported add_dashboard layout DSL. "
            f"{str(e)}"
        )
    except Exception as e:
        return f"Failed to generate layout JSON: {str(e)}"


@server.tool()
def generate_layout_yaml(
    output_path: str,
    layout_tree: dict,
    ascii_preview: str,
) -> str:
    """Generate and save a dashboard layout YAML file.

    Recommended workflow:
    1. Call list_worksheets to get available worksheet names
    2. Design the layout with the user (show ASCII preview for confirmation)
    3. Call this tool to save the layout as a YAML file
    4. Call add_dashboard with layout=<this_file_path>

    The layout_tree uses the same declarative container DSL as generate_layout_json.
    """

    path = Path(output_path)
    if path.suffix.lower() not in {".yaml", ".yml"}:
        path = path.with_suffix(".yaml")
    return generate_layout_json(
        output_path=str(path),
        layout_tree=layout_tree,
        ascii_preview=ascii_preview,
    )


# --- Migration tools ---


@server.tool()
def inspect_target_schema(target_source: str) -> str:
    """Inspect the first-sheet schema of a target Excel datasource."""

    path = Path(target_source)
    suffix = path.suffix.lower()
    if suffix not in (".xls", ".xlsx", ".xlsm", ".xlsb"):
        return f"Unsupported file type '{suffix}'. Only Excel files (.xls, .xlsx, .xlsm, .xlsb) are supported."

    try:
        return json.dumps(inspect_target_schema_impl(target_source), ensure_ascii=False, indent=2)
    except Exception as exc:
        return f"Unsupported or unreadable file: {exc}"


@server.tool()
def profile_twb_for_migration(
    file_path: str,
    scope: str = "workbook",
    target_source: str = "",
) -> str:
    """Profile workbook datasources and worksheet scope before migration."""

    return profile_twb_for_migration_json(
        file_path=file_path,
        scope=scope,
        target_source=target_source or None,
    )


@server.tool()
def propose_field_mapping(
    file_path: str,
    target_source: str,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
) -> str:
    """Scan source and target schema and propose a field mapping."""

    return propose_field_mapping_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
    )


@server.tool()
def preview_twb_migration(
    file_path: str,
    target_source: str,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
) -> str:
    """Preview a workbook migration onto a target datasource."""

    return preview_twb_migration_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
    )


@server.tool()
def apply_twb_migration(
    file_path: str,
    target_source: str,
    output_path: str,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
) -> str:
    """Apply a workbook migration and write a migrated TWB plus reports."""

    return apply_twb_migration_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        output_path=output_path,
    )


def migrate_twb_guided(
    file_path: str,
    target_source: str,
    output_path: str = "",
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    apply_if_no_blockers: bool = True,
) -> str:
    """Run the built-in migration workflow and pause for warning confirmation when needed."""

    return migrate_twb_guided_json(
        file_path=file_path,
        target_source=target_source,
        output_path=output_path or None,
        scope=scope,
        mapping_overrides=mapping_overrides,
        apply_if_no_blockers=apply_if_no_blockers,
    )


# --- Support tools ---


@server.tool()
def list_capabilities() -> str:
    """List cwtwb's declared capability boundary.

    This reports what workbook features/charts are supported by cwtwb. It does
    not enumerate callable MCP tools and should not be used to infer whether a
    tool like add_dashboard or save_workbook exists.
    """

    guardrails = [
        "Workflow guardrails:",
        "- This output is a capability catalog, not a list of callable MCP tools.",
        "- Recommended workbook flow: create_workbook/open_workbook -> list_fields -> add_worksheet/configure_chart -> add_dashboard -> save_workbook.",
        "- add_dashboard and save_workbook are default MCP tools. If they seem missing, refresh the MCP client session and uvx cache.",
        "- inspect_excel_connection is the read-only preview helper for multi-table Excel workbooks.",
    ]
    return "\n".join(guardrails) + "\n\n" + format_capability_catalog()


@server.tool()
def describe_capability(kind: str, name: str) -> str:
    """Describe one declared capability and its support tier."""

    return format_capability_detail(kind, name)


@server.tool()
def analyze_twb(file_path: str) -> str:
    """Analyze an existing TWB/TWBX file against cwtwb's declared capabilities.

    This tool requires a file_path that already exists on disk. It cannot
    analyze the active in-memory workbook directly and it does not save the
    current workbook. For a newly generated workbook, call save_workbook first,
    then pass that saved path to analyze_twb.
    """

    schema_note = (
        "Schema check: SKIPPED (analysis only). "
        "Important: analyze_twb reports capability fit, not loadability."
    )
    try:
        root = load_workbook_root(file_path)
        schema_result = validate_against_schema(root)
        if schema_result.valid:
            schema_note = "Schema check: PASS."
        else:
            schema_note = (
                f"Schema check: FAIL ({len(schema_result.errors)} error(s)). "
                "Important: capability analysis can still run on invalid workbooks."
            )
    except TWBValidationError as exc:
        schema_note = (
            "Schema check: FAIL (unable to parse workbook structure). "
            f"Details: {exc}"
        )

    report = analyze_workbook(file_path)
    return schema_note + "\n\n" + report.to_text() + "\n\n" + report.to_gap_text()


@server.tool()
def diff_template_gap(file_path: str) -> str:
    """Summarize the non-core capability gap of a TWB template."""

    report = analyze_workbook(file_path)
    return report.to_gap_text()


@server.tool()
def validate_workbook(file_path: Optional[str] = None) -> str:
    """Validate a workbook against the official Tableau TWB XSD schema.

    Checks whether the generated XML conforms to Tableau's published schema.
    This tool does not save or export the active workbook. If file_path is
    omitted, it validates the current in-memory workbook before save; if
    file_path is provided, it validates an existing .twb/.twbx file on disk.
    Call save_workbook when you need to write the workbook to a file.

    Args:
        file_path: Path to a .twb or .twbx file to validate. If omitted,
                   validates the currently open workbook (in memory, before save).

    Returns:
        PASS/FAIL summary with error details.
    """

    if file_path:
        p = Path(file_path)
        if not p.exists():
            return f"ERROR  File not found: {file_path}"

        try:
            root = load_workbook_root(p)
        except TWBValidationError as exc:
            return f"ERROR  {exc}"
        result = validate_against_schema(root)
    else:
        editor = get_editor()
        result = validate_against_schema(editor.root)

    result_text = result.to_text()
    if file_path:
        return result_text
    return (
        result_text
        + "\n\n"
        + "Note: validate_workbook only validates the in-memory workbook; it does not save files. "
        + "Use save_workbook(output_path=...) to write a .twb/.twbx file."
    )


@server.tool()
def inspect_excel_connection(file_path: str, sheet_name: str = "") -> str:
    """Preview how an Excel workbook will be interpreted before connection setup."""

    sheet_names = _list_excel_sheet_names(file_path)
    if not sheet_names:
        return json.dumps(
            {
                "file_path": file_path,
                "multi_table": False,
                "tables": [],
                "relationships": [],
                "note": "No readable sheets were found.",
            },
            ensure_ascii=False,
            indent=2,
        )

    ordered_sheet_names = sheet_names
    if sheet_name and sheet_name in sheet_names:
        ordered_sheet_names = [sheet_name] + [name for name in sheet_names if name != sheet_name]

    tables: list[dict] = []
    for index, candidate_sheet in enumerate(ordered_sheet_names):
        actual_sheet_name, rows = _read_excel_sheet_rows(file_path, sheet_name=candidate_sheet)
        if not rows:
            continue

        headers = _sanitize_headers(rows[0])
        value_rows = rows[1:]
        fields: list[dict] = []
        for ordinal, header in enumerate(headers):
            values = _column_values_from_rows(value_rows, ordinal)
            datatype = _infer_excel_datatype(header, values)
            role = _infer_external_role(header, datatype)
            fields.append(
                {
                    "name": header,
                    "ordinal": ordinal,
                    "datatype": datatype,
                    "role": role,
                    "field_type": _infer_external_field_type(role, datatype),
                    "semantic_role": infer_tableau_semantic_role(header),
                }
            )

        tables.append(
            {
                "name": actual_sheet_name,
                "grid_origin": _excel_grid_origin(rows),
                "outcome": "6" if len(rows) > 1 else "2",
                "row_count": max(len(rows) - 1, 0),
                "column_count": len(headers),
                "fields": fields,
            }
        )

    shared_name_counts = Counter(
        field["name"]
        for table in tables
        for field in table["fields"]
    )
    relationships: list[dict] = []
    if tables:
        primary = tables[0]
        primary_field_names = {field["name"] for field in primary["fields"]}
        for secondary in tables[1:]:
            shared_fields = [
                field["name"]
                for field in secondary["fields"]
                if field["name"] in primary_field_names and shared_name_counts[field["name"]] > 1
            ]
            if shared_fields:
                relationships.append(
                    {
                        "from_table": primary["name"],
                        "to_table": secondary["name"],
                        "shared_fields": shared_fields,
                    }
                )

    preview = {
        "file_path": file_path,
        "sheet_name_hint": sheet_name,
        "sheet_count": len(sheet_names),
        "multi_table": len(tables) > 1,
        "tables": tables,
        "relationships": relationships,
    }
    return json.dumps(preview, ensure_ascii=False, indent=2)

