"""Canonical default MCP server entrypoint for cwtwb.

This module is the single source of truth for launching the stable default
cwtwb MCP server. It imports the workbook and validation tool modules so their
decorators register against the shared FastMCP server before the stdio
transport starts.

Supported launch styles:
    uvx cwtwb
    cwtwb
    cwtwb-mcp
    python -m cwtwb.mcp_server
"""

from .mcp.app import (
    get_mcp_status,
    main as _run_mcp_server,
    read_dataset_profile,
    read_profiles_index,
    read_skill,
    read_skills_index,
    read_tableau_functions,
    server,
)


def main(argv: list[str] | None = None) -> int:
    """Run the MCP server, but honor common help spellings for human terminals.

    This guard protects compatibility entrypoints such as ``cwtwb-mcp`` and
    older console scripts that may still point directly at ``cwtwb.mcp_server``.
    Without it, commands like ``cwtwb -help`` can appear to hang because they
    start the stdio MCP server and wait for JSON-RPC input.
    """

    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 1 and args[0].casefold() in {"-h", "--help", "-help", "help", "/?", "-?"}:
        from .cli import build_parser

        build_parser().print_help()
        return 0
    _run_mcp_server()
    return 0


from .mcp.tools_validate import (
    screenshot_workbook,
    upload_workbook,
    validate_workbook_api,
)
from .mcp.tools_workbook import (
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
    configure_worksheet_style,
    create_workbook,
    describe_capability,
    diff_template_gap,
    generate_layout_json,
    generate_layout_yaml,
    inspect_excel_connection,
    inspect_target_schema,
    list_capabilities,
    list_dashboards,
    list_fields,
    list_worksheets,
    migrate_twb_guided,
    open_workbook,
    preview_twb_migration,
    preview_worksheet_refactor,
    profile_twb_for_migration,
    propose_field_mapping,
    remove_calculated_field,
    save_workbook,
    set_csv_connection,
    set_excel_connection,
    set_hyper_connection,
    set_mysql_connection,
    set_tableauserver_connection,
    set_worksheet_caption,
    set_worksheet_hidden,
    validate_workbook,
)

__all__ = [
    "main",
    "server",
    "get_mcp_status",
    "read_tableau_functions",
    "read_skills_index",
    "read_skill",
    "read_profiles_index",
    "read_dataset_profile",
    "create_workbook",
    "open_workbook",
    "save_workbook",
    "list_fields",
    "add_worksheet",
    "migrate_twb_guided",
    "configure_chart",
    "configure_dual_axis",
    "configure_worksheet_style",
    "configure_chart_recipe",
    "add_dashboard",
    "add_dashboard_action",
    "list_worksheets",
    "list_dashboards",
    "set_excel_connection",
    "set_csv_connection",
    "set_hyper_connection",
    "set_mysql_connection",
    "set_tableauserver_connection",
    "inspect_excel_connection",
    "add_calculated_field",
    "remove_calculated_field",
    "add_parameter",
    "clone_worksheet",
    "set_worksheet_caption",
    "set_worksheet_hidden",
    "generate_layout_json",
    "generate_layout_yaml",
    "validate_workbook",
    "validate_workbook_api",
    "upload_workbook",
    "screenshot_workbook",
    "analyze_twb",
    "describe_capability",
    "list_capabilities",
    "inspect_target_schema",
    "diff_template_gap",
    "profile_twb_for_migration",
    "propose_field_mapping",
    "preview_twb_migration",
    "apply_twb_migration",
    "preview_worksheet_refactor",
    "apply_worksheet_refactor",
]


if __name__ == "__main__":
    main()
