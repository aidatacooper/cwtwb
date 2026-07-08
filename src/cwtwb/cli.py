from __future__ import annotations

import argparse
import os
import sys
from typing import Sequence

from . import __version__
from .commands.common import add_json_flag
from .commands.info import doctor, status
from .commands.readonly import analyze, capabilities, dashboards, fields, inspect_workbook, validate, worksheets
from .commands.run_spec import run as run_spec
from .commands.write import (
    chart_add,
    connection_set_csv,
    connection_set_excel,
    connection_set_hyper,
    create,
    dashboard_add,
    layout_generate,
    migrate_apply,
    migrate_preview,
)


DESCRIPTION = "Tableau workbook engineering toolkit and MCP server."
HELP_ARGS = {"-h", "--help", "-help", "help", "/?", "-?"}


def _run_mcp() -> int:
    from .mcp_server import main as mcp_main

    mcp_main()
    return 0


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", required=True, help="Output workbook path.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    parser.add_argument("--no-save-validation", action="store_true", help="Skip TWBEditor save-time validation.")
    add_json_flag(parser)


def _add_modify_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out", help="Output workbook path.")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the input workbook.")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    parser.add_argument("--no-save-validation", action="store_true", help="Skip TWBEditor save-time validation.")
    add_json_flag(parser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cwtwb",
        description=DESCRIPTION,
        epilog=(
            "Smart entry: `cwtwb` with no arguments prints help in an interactive "
            "terminal and starts the MCP stdio server when stdin is not a TTY. "
            "Use `cwtwb mcp` to start MCP explicitly."
        ),
    )
    parser.add_argument("--version", action="version", version=f"cwtwb {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("mcp", help="Start the MCP stdio server.").set_defaults(func=lambda _args: _run_mcp())

    doctor_parser = subparsers.add_parser("doctor", help="Check installation and MCP/CLI setup.")
    add_json_flag(doctor_parser)
    doctor_parser.set_defaults(func=doctor)

    status_parser = subparsers.add_parser("status", help="Show version, package paths, and runtime status.")
    add_json_flag(status_parser)
    status_parser.set_defaults(func=status)

    for name, help_text, func in (
        ("inspect", "Inspect workbook structure.", inspect_workbook),
        ("fields", "List datasource fields.", fields),
        ("worksheets", "List worksheets.", worksheets),
        ("dashboards", "List dashboards.", dashboards),
        ("validate", "Validate workbook against the bundled Tableau TWB schema.", validate),
        ("analyze", "Analyze workbook capabilities and support fit.", analyze),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("workbook")
        add_json_flag(command)
        command.set_defaults(func=func)

    cap_parser = subparsers.add_parser("capabilities", help="List declared cwtwb capabilities.")
    cap_parser.add_argument("--kind", choices=["chart", "encoding", "dashboard_zone", "action", "connection", "feature"])
    cap_parser.add_argument("--level", choices=["core", "advanced", "recipe", "unsupported"])
    add_json_flag(cap_parser)
    cap_parser.set_defaults(func=capabilities)

    run_parser = subparsers.add_parser("run", help="Run a YAML/JSON workbook automation spec.")
    run_parser.add_argument("spec")
    run_parser.add_argument("--out", help="Override spec output path.")
    run_parser.add_argument("--dry-run", action="store_true", help="Validate top-level spec loading without writing files.")
    run_parser.add_argument("--validate", action="store_true", help="Run local schema validation after writing.")
    run_parser.add_argument("--force", action="store_true", help="Overwrite an existing output file.")
    run_parser.add_argument("--no-save-validation", action="store_true", help="Skip TWBEditor save-time validation.")
    add_json_flag(run_parser)
    run_parser.set_defaults(func=run_spec)

    create_parser = subparsers.add_parser("create", help="Create a workbook from the built-in or supplied template.")
    create_parser.add_argument("--template", default="", help="Template .twb/.twbx path. Omit for the built-in Superstore template.")
    create_parser.add_argument("--clear-worksheets", action="store_true", help="Remove template worksheets before saving.")
    _add_output_options(create_parser)
    create_parser.set_defaults(func=create)

    connection = subparsers.add_parser("connection", help="Modify workbook datasource connections.")
    connection_sub = connection.add_subparsers(dest="connection_command", required=True)
    excel = connection_sub.add_parser("set-excel", help="Set a local Excel datasource connection.")
    excel.add_argument("workbook")
    excel.add_argument("--data", required=True, help="Excel file path.")
    excel.add_argument("--sheet", default="", help="Sheet name.")
    excel.add_argument("--fields", help="JSON/YAML field metadata file.")
    _add_modify_output_options(excel)
    excel.set_defaults(func=connection_set_excel)

    csv = connection_sub.add_parser("set-csv", help="Set a local CSV datasource connection.")
    csv.add_argument("workbook")
    csv.add_argument("--data", required=True, help="CSV file path.")
    csv.add_argument("--delimiter", default="", help="CSV delimiter override.")
    csv.add_argument("--charset", default="utf-8-sig", help="CSV charset.")
    csv.add_argument("--fields", help="JSON/YAML field metadata file.")
    _add_modify_output_options(csv)
    csv.set_defaults(func=connection_set_csv)

    hyper = connection_sub.add_parser("set-hyper", help="Set a local Hyper extract connection.")
    hyper.add_argument("workbook")
    hyper.add_argument("--data", required=True, help="Hyper file path.")
    hyper.add_argument("--table", default="Extract", help="Hyper table name.")
    hyper.add_argument("--tables", help="JSON/YAML Hyper tables metadata file.")
    _add_modify_output_options(hyper)
    hyper.set_defaults(func=connection_set_hyper)

    chart = subparsers.add_parser("chart", help="Modify worksheets and charts.")
    chart_sub = chart.add_subparsers(dest="chart_command", required=True)
    chart_add_parser = chart_sub.add_parser("add", help="Add or configure a worksheet chart.")
    chart_add_parser.add_argument("workbook")
    chart_add_parser.add_argument("--worksheet", required=True)
    chart_add_parser.add_argument("--mark", default="Automatic")
    chart_add_parser.add_argument("--columns", nargs="*")
    chart_add_parser.add_argument("--rows", nargs="*")
    chart_add_parser.add_argument("--color")
    chart_add_parser.add_argument("--size")
    chart_add_parser.add_argument("--label")
    chart_add_parser.add_argument("--detail")
    chart_add_parser.add_argument("--wedge-size")
    chart_add_parser.add_argument("--sort-descending")
    chart_add_parser.add_argument("--tooltip", nargs="*")
    chart_add_parser.add_argument("--filters", help="JSON/YAML filter list file.")
    chart_add_parser.add_argument("--geographic-field")
    chart_add_parser.add_argument("--measure-values", nargs="*")
    chart_add_parser.add_argument("--map-fields", nargs="*")
    chart_add_parser.add_argument("--mark-sizing-off", action="store_true")
    chart_add_parser.add_argument("--axis-fixed-range", help="JSON object.")
    chart_add_parser.add_argument("--customized-label")
    chart_add_parser.add_argument("--color-map", help="JSON object.")
    chart_add_parser.add_argument("--text-format", help="JSON object.")
    chart_add_parser.add_argument("--map-layers", help="JSON array.")
    chart_add_parser.add_argument("--label-runs", help="JSON array.")
    chart_add_parser.add_argument("--label-param")
    _add_modify_output_options(chart_add_parser)
    chart_add_parser.set_defaults(func=chart_add)

    dashboard = subparsers.add_parser("dashboard", help="Modify dashboards.")
    dashboard_sub = dashboard.add_subparsers(dest="dashboard_command", required=True)
    dashboard_add_parser = dashboard_sub.add_parser("add", help="Add a dashboard from worksheets.")
    dashboard_add_parser.add_argument("workbook")
    dashboard_add_parser.add_argument("--name", required=True)
    dashboard_add_parser.add_argument("--worksheets", nargs="+", required=True)
    dashboard_add_parser.add_argument("--width", type=int, default=1200)
    dashboard_add_parser.add_argument("--height", type=int, default=800)
    dashboard_add_parser.add_argument("--layout", default="auto")
    _add_modify_output_options(dashboard_add_parser)
    dashboard_add_parser.set_defaults(func=dashboard_add)

    layout = subparsers.add_parser("layout", help="Generate dashboard layout files.")
    layout_sub = layout.add_subparsers(dest="layout_command", required=True)
    layout_generate_parser = layout_sub.add_parser("generate", help="Normalize and write a JSON/YAML dashboard layout file.")
    layout_generate_parser.add_argument("layout", help="Input JSON/YAML layout tree.")
    layout_generate_parser.add_argument("--out", required=True)
    layout_generate_parser.add_argument("--ascii-preview", default="")
    add_json_flag(layout_generate_parser)
    layout_generate_parser.set_defaults(func=layout_generate)

    migrate = subparsers.add_parser("migrate", help="Preview or apply workbook datasource migration.")
    migrate_sub = migrate.add_subparsers(dest="migrate_command", required=True)
    migrate_preview_parser = migrate_sub.add_parser("preview", help="Preview migration to a target Excel datasource.")
    migrate_preview_parser.add_argument("workbook")
    migrate_preview_parser.add_argument("--target-source", required=True)
    migrate_preview_parser.add_argument("--scope", default="workbook")
    migrate_preview_parser.add_argument("--map", action="append", help="Mapping override as SOURCE=TARGET. Repeatable.")
    add_json_flag(migrate_preview_parser)
    migrate_preview_parser.set_defaults(func=migrate_preview)

    migrate_apply_parser = migrate_sub.add_parser("apply", help="Apply migration to a target Excel datasource.")
    migrate_apply_parser.add_argument("workbook")
    migrate_apply_parser.add_argument("--target-source", required=True)
    migrate_apply_parser.add_argument("--scope", default="workbook")
    migrate_apply_parser.add_argument("--map", action="append", help="Mapping override as SOURCE=TARGET. Repeatable.")
    migrate_apply_parser.add_argument("--out", required=True)
    migrate_apply_parser.add_argument("--force", action="store_true")
    add_json_flag(migrate_apply_parser)
    migrate_apply_parser.set_defaults(func=migrate_apply)

    ui_parser = subparsers.add_parser("ui", help="Reserved for a future local web UI.")
    ui_parser.set_defaults(func=lambda _args: (_ for _ in ()).throw(SystemExit("cwtwb ui is not implemented yet.")))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = os.getenv("CWTWB_MODE", "").strip().lower()

    if not argv:
        if mode == "mcp":
            return _run_mcp()
        parser = build_parser()
        if mode == "cli" or sys.stdin.isatty():
            parser.print_help()
            return 0
        return _run_mcp()

    parser = build_parser()
    if len(argv) == 1 and argv[0].casefold() in HELP_ARGS:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    try:
        return int(args.func(args) or 0)
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
