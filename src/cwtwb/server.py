"""Compatibility entrypoint for cwtwb's MCP server.

This module re-exports MCP tool functions for backward compatibility with
existing test files and external callers. The canonical definitions live
in the mcp.tools_workbook module (or mcp.app for main()).
"""
__author__ = "Cooper Wenhua <imgwho@gmail.com>"

from .mcp.app import (
    main,
    read_dataset_profile,
    read_profiles_index,
    read_skill,
    read_skills_index,
    read_tableau_functions,
    server,
)
from .mcp.tools_workbook import (
    add_calculated_field,
    add_dashboard,
    add_dashboard_action,
    add_parameter,
    add_worksheet,
    apply_worksheet_refactor,
    analyze_twb,
    apply_twb_migration,
    clone_worksheet,
    configure_chart,
    configure_chart_recipe,
    configure_dual_axis,
    create_workbook,
    describe_capability,
    diff_template_gap,
    generate_layout_json,
    inspect_excel_connection,
    inspect_target_schema,
    list_capabilities,
    list_dashboards,
    list_fields,
    list_worksheets,
    open_workbook,
    preview_twb_migration,
    preview_worksheet_refactor,
    profile_twb_for_migration,
    propose_field_mapping,
    remove_calculated_field,
    save_workbook,
    set_csv_connection,
    set_excel_connection,
    set_worksheet_caption,
    set_worksheet_hidden,
    set_hyper_connection,
    set_mysql_connection,
    set_tableauserver_connection,
    validate_workbook,
)


if __name__ == "__main__":
    main()
