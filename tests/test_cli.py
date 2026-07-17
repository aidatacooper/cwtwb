from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from cwtwb import __version__
from cwtwb.cli import main


def test_empty_interactive_invocation_prints_help(monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

    assert main([]) == 0

    captured = capsys.readouterr()
    assert "Tableau workbook engineering toolkit" in captured.out
    assert "starts the MCP stdio server when stdin is not a TTY" in captured.out


def test_empty_non_tty_invocation_starts_mcp(monkeypatch):
    called = {"mcp": False}

    def fake_run_mcp():
        called["mcp"] = True
        return 0

    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr("cwtwb.cli._run_mcp", fake_run_mcp)

    assert main([]) == 0
    assert called["mcp"] is True


def test_single_dash_help_alias_prints_help(capsys):
    assert main(["-help"]) == 0

    captured = capsys.readouterr()
    assert "Tableau workbook engineering toolkit" in captured.out
    assert "cwtwb mcp" in captured.out


def test_word_help_alias_prints_help(capsys):
    assert main(["help"]) == 0

    captured = capsys.readouterr()
    assert "Tableau workbook engineering toolkit" in captured.out


def test_status_json_reports_local_version(capsys):
    assert main(["status", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == __version__
    assert payload["schema_dir"]


def test_inspect_json_lists_workbook_content(capsys):
    assert main(["inspect", "tests/test_empty.twb", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["worksheets"] == ["Sheet 1"]
    assert payload["field_counts"]["total"] > 0


def test_create_chart_and_dashboard_commands_write_workbook(tmp_path: Path):
    base = tmp_path / "base.twb"
    chart = tmp_path / "chart.twb"
    dashboard = tmp_path / "dashboard.twb"

    assert main(["create", "--out", str(base), "--force", "--no-save-validation"]) == 0
    assert base.exists()

    assert main([
        "chart",
        "add",
        str(base),
        "--worksheet",
        "Sales by Category",
        "--mark",
        "Bar",
        "--rows",
        "Category",
        "--columns",
        "SUM(Sales)",
        "--out",
        str(chart),
        "--force",
        "--no-save-validation",
    ]) == 0
    assert chart.exists()

    assert main([
        "dashboard",
        "add",
        str(chart),
        "--name",
        "Overview",
        "--worksheets",
        "Sales by Category",
        "--layout",
        "horizontal",
        "--out",
        str(dashboard),
        "--force",
        "--no-save-validation",
    ]) == 0
    assert dashboard.exists()


def test_connection_set_excel_command_writes_workbook(tmp_path: Path):
    base = tmp_path / "base.twb"
    connected = tmp_path / "connected.twb"

    assert main(["create", "--out", str(base), "--force", "--no-save-validation"]) == 0
    assert main([
        "connection",
        "set-excel",
        str(base),
        "--data",
        "tests/fixtures/Sample - Superstore.xls",
        "--sheet",
        "Orders",
        "--out",
        str(connected),
        "--force",
        "--no-save-validation",
    ]) == 0
    assert connected.exists()


def test_run_spec_writes_workbook(tmp_path: Path):
    output = tmp_path / "spec_output.twb"
    spec = tmp_path / "spec.yaml"
    spec.write_text(
        yaml.safe_dump(
            {
                "output": str(output),
                "clear_worksheets": True,
                "worksheets": [
                    {
                        "name": "Sales by Category",
                        "mark": "Bar",
                        "rows": ["Category"],
                        "columns": ["SUM(Sales)"],
                    }
                ],
                "dashboard": {
                    "name": "Overview",
                    "worksheets": ["Sales by Category"],
                    "layout": "horizontal",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    assert main(["run", str(spec), "--force", "--no-save-validation"]) == 0
    assert output.exists()
