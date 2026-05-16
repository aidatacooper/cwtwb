"""FastMCP server singleton for the cwtwb MCP server.

This module creates the single FastMCP `server` instance that all tool and
resource modules register against via @server.tool() and @server.resource().

Import order matters: app.py must be imported before tools_*.py and resources.py
so that `server` exists when the decorators run.  The entry point (typically
run via `mcp run` or `python -m cwtwb.mcp`) imports all tool modules, which
self-register, and then starts the server transport.

The `instructions` string is what AI agents read when they first connect —
it summarises the required call order and points agents to skill resources.
"""

from mcp.server.fastmcp import FastMCP


server = FastMCP(
    "cwtwb",
    instructions="Tableau Workbook (.twb) generation MCP Server. "
    "Use manual workbook editing: create_workbook or open_workbook first, "
    "then list_fields, add_worksheet, configure_chart or configure_dual_axis, "
    "optionally add_dashboard and add_dashboard_action, and finally save_workbook. "
    "add_dashboard exists in the default MCP tool surface and should be used when "
    "a dashboard is requested. "
    "save_workbook is the only default MCP tool that writes the active in-memory "
    "workbook to a .twb/.twbx file on disk; do not use validate_workbook, "
    "analyze_twb, or migration tools as substitutes for saving. "
    "validate_workbook only validates the active workbook or an existing file and "
    "does not write output. analyze_twb requires an existing .twb/.twbx file path, "
    "so call save_workbook before analyze_twb when analyzing a newly generated workbook. "
    "Do not infer tool availability from list_capabilities; list_capabilities is a "
    "feature support catalog, not a tool inventory. "
    "Use set_excel_connection, set_csv_connection, set_hyper_connection, set_mysql_connection, or "
    "set_tableauserver_connection when the workbook datasource must be changed. "
    "Use inspect_excel_connection when you need a read-only preview of Excel sheet parsing, inferred datatypes, "
    "or likely multi-table relationships before mutating the workbook. "
    "When authoring a dashboard layout, first call list_worksheets and lock the exact worksheet names; "
    "reuse those exact names in layout nodes to avoid name drift. "
    "For layout JSON, use the canonical DSL: container nodes use type='container' with direction and children; "
    "do not use zones or absolute-position dashboard schemas. "
    "Generate layout files with generate_layout_json first for DSL validation, then pass the resulting file path to add_dashboard(layout=...). "
    "Prefer a small fixed layout template and fill worksheet names and sizes instead of free-form layout generation. "
    "Use validate_workbook after saving when the human asks for an explicit validation report. "
    "Prefer core primitives first, and use list_capabilities or describe_capability "
    "when you need to check whether a chart or feature is core, advanced, or recipe-only. "
    "For professional-quality output, optionally read the agent skills "
    "(cwtwb://skills/index) before starting each phase.",
)
