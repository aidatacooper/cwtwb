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
    "Use set_excel_connection, set_hyper_connection, set_mysql_connection, or "
    "set_tableauserver_connection when the workbook datasource must be changed. "
    "Use validate_workbook after saving when the human asks for an explicit validation report. "
    "Prefer core primitives first, and use list_capabilities or describe_capability "
    "when you need to check whether a chart or feature is core, advanced, or recipe-only. "
    "For professional-quality output, optionally read the agent skills "
    "(cwtwb://skills/index) before starting each phase.",
)
