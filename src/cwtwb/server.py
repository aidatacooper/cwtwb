"""Compatibility entrypoint for cwtwb's MCP server."""

from .mcp.app import server
from .mcp.resources import read_skill, read_skills_index, read_tableau_functions
from .mcp.tools_layout import generate_layout_json
from .mcp.tools_support import (
    analyze_twb,
    describe_capability,
    diff_template_gap,
    list_capabilities,
)
from .mcp.tools_workbook import (
    add_calculated_field,
    add_dashboard,
    add_dashboard_action,
    add_parameter,
    add_worksheet,
    configure_chart,
    configure_chart_recipe,
    configure_dual_axis,
    create_workbook,
    list_fields,
    remove_calculated_field,
    save_workbook,
    set_hyper_connection,
    set_mysql_connection,
    set_tableauserver_connection,
)


def main():
    """Run the MCP server via stdio transport."""

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
