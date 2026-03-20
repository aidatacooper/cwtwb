"""Compatibility entrypoint for cwtwb's MCP server."""

from .mcp.app import server
from .mcp.prompts import (
    authoring_execution_plan,
    dashboard_brief_to_contract,
    guided_dashboard_authoring,
    light_elicitation,
)
from .mcp.resources import (
    read_dataset_profile,
    read_dashboard_authoring_contract,
    read_profiles_index,
    read_skill,
    read_skills_index,
    read_tableau_functions,
)
from .mcp.tools_layout import generate_layout_json
from .mcp.tools_authoring import (
    build_analysis_brief,
    build_execution_plan,
    build_wireframe,
    confirm_authoring_stage,
    draft_authoring_contract,
    finalize_analysis_brief,
    finalize_authoring_contract,
    finalize_wireframe,
    generate_workbook_from_run,
    get_run_status,
    intake_datasource_schema,
    list_authoring_runs,
    reopen_authoring_stage,
    resume_authoring_run,
    review_authoring_contract_for_run,
    start_authoring_run,
)
from .mcp.tools_migration import (
    apply_twb_migration,
    inspect_target_schema,
    migrate_twb_guided,
    profile_twb_for_migration,
    propose_field_mapping,
    preview_twb_migration,
)
from .mcp.tools_support import (
    analyze_twb,
    describe_capability,
    diff_template_gap,
    list_capabilities,
    review_authoring_contract,
    validate_workbook,
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
    list_dashboards,
    list_fields,
    list_worksheets,
    open_workbook,
    remove_calculated_field,
    save_workbook,
    set_excel_connection,
    set_worksheet_caption,
    set_hyper_connection,
    set_mysql_connection,
    set_tableauserver_connection,
)


def main():
    """Run the MCP server via stdio transport."""

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
