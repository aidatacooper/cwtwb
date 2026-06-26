"""Backward-compatible MCP entrypoint for cwtwb.

The canonical server entrypoint is now ``cwtwb.mcp_server``. This module stays
as a compatibility shim for existing callers and test imports.
"""
__author__ = "Cooper Wenhua <imgwho@gmail.com>"

from .mcp_server import (
    add_calculated_field,
    add_dashboard,
    add_dashboard_action,
    add_parameter,
    add_worksheet,
    apply_twb_migration,
    apply_worksheet_refactor,
    analyze_twb,
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
    main,
    migrate_twb_guided,
    open_workbook,
    preview_twb_migration,
    preview_worksheet_refactor,
    profile_twb_for_migration,
    propose_field_mapping,
    read_dataset_profile,
    read_profiles_index,
    read_skill,
    read_skills_index,
    read_tableau_functions,
    remove_calculated_field,
    save_workbook,
    server,
    set_csv_connection,
    set_excel_connection,
    set_hyper_connection,
    set_mysql_connection,
    set_tableauserver_connection,
    set_worksheet_caption,
    set_worksheet_hidden,
    screenshot_workbook,
    upload_workbook,
    validate_workbook,
    validate_workbook_api,
)

if __name__ == "__main__":
    main()
