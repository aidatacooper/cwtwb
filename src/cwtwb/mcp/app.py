"""FastMCP application instance for cwtwb."""

from mcp.server.fastmcp import FastMCP


server = FastMCP(
    "cwtwb",
    instructions="Tableau Workbook (.twb) generation MCP Server. "
    "Create visualizations by calling create_workbook first, "
    "then add_worksheet + configure_chart, and finally save_workbook. "
    "Prefer core primitives first, and use list_capabilities or describe_capability "
    "when you need to check whether a chart or feature is core, advanced, or recipe-only. "
    "For professional-quality output, read the agent skills "
    "(cwtwb://skills/index) before starting each phase.",
)
