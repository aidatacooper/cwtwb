"""Tests for the MCP tool-layer wrappers (server.py exports).

Verifies that tools correctly relay calls to the editor and return
properly-formatted string payloads. Covers:
  - remove_calculated_field
  - set_mysql_connection / set_tableauserver_connection / set_csv_connection / set_hyper_connection (MCP layer)
  - inspect_target_schema (non-hyper path returns informative message)
  - list_capabilities
  - analyze_twb
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.mcp.app import server
from cwtwb.server import (
    add_calculated_field,
    add_worksheet,
    apply_worksheet_refactor,
    clone_worksheet,
    create_workbook,
    list_capabilities,
    list_fields,
    open_workbook,
    preview_worksheet_refactor,
    remove_calculated_field,
    save_workbook,
    set_csv_connection,
    set_hyper_connection,
    set_mysql_connection,
    set_worksheet_hidden,
    set_tableauserver_connection,
    analyze_twb,
    inspect_target_schema,
    inspect_excel_connection,
    validate_workbook,
)

TEMPLATE = Path("templates/twb/superstore.twb")
EXAMPLE_WORKBOOK = Path("examples/worksheet_refactor_kpi_profit/5 KPI Design Ideas (2).twb")


@pytest.fixture(autouse=True)
def fresh_workbook():
    """Ensure each test starts with a clean workbook state."""
    create_workbook(str(TEMPLATE), "MCP Tool Tests")


class TestToolDescriptions:
    def test_save_validate_and_analyze_descriptions_prevent_save_confusion(self):
        save_desc = server._tool_manager._tools["save_workbook"].description
        validate_desc = server._tool_manager._tools["validate_workbook"].description
        analyze_desc = server._tool_manager._tools["analyze_twb"].description
        capability_desc = server._tool_manager._tools["list_capabilities"].description
        server_instructions = server.instructions

        assert "only default MCP tool that writes" in save_desc
        assert "validate_workbook and analyze_twb do not save files" in save_desc
        assert "does not save or export" in validate_desc
        assert "requires a file_path that already exists on disk" in analyze_desc
        assert "call save_workbook first" in analyze_desc
        assert "not enumerate callable MCP tools" in capability_desc
        assert "feature support catalog, not a tool inventory" in server_instructions
        assert "add_dashboard exists in the default MCP tool surface" in server_instructions


# ── remove_calculated_field ───────────────────────────────────────────────────

class TestRemoveCalculatedField:
    def test_remove_existing_field(self):
        add_calculated_field("Profit Ratio", "SUM([Profit])/SUM([Sales])", "real")
        assert "Profit Ratio" in list_fields()

        result = remove_calculated_field("Profit Ratio")
        assert "Profit Ratio" in result  # message confirms the name
        assert "Profit Ratio" not in list_fields()

    def test_remove_field_updates_xml(self, tmp_path):
        add_calculated_field("Temp Calc", "1+1", "real")
        remove_calculated_field("Temp Calc")
        output = tmp_path / "after_remove.twb"
        save_workbook(str(output))
        root = ET.parse(output).getroot()
        assert root.find(".//datasource/column[@caption='Temp Calc']") is None

    def test_add_remove_add_cycle(self):
        add_calculated_field("Cycle Field", "42", "real")
        remove_calculated_field("Cycle Field")
        # Can re-add the same name without error
        add_calculated_field("Cycle Field", "0", "real")
        assert "Cycle Field" in list_fields()

    def test_remove_nonexistent_field_returns_message(self):
        """Removing an unknown field should not raise; returns an informative message."""
        result = remove_calculated_field("Does Not Exist")
        assert isinstance(result, str)


# ── connection MCP wrappers ───────────────────────────────────────────────────

class TestConnectionMcpTools:
    def test_set_csv_connection_returns_confirmation(self):
        base_dir = Path(__file__).parent.parent / "tmp" / "test_csv_mcp"
        base_dir.mkdir(parents=True, exist_ok=True)
        csv_path = base_dir / "tool_sales.csv"
        csv_path.write_text(
            "Order ID;State/Province;Sales\n"
            "1;California;100\n"
            "2;Nevada;200\n",
            encoding="utf-8",
        )

        result = set_csv_connection(filepath=str(csv_path))
        assert "CSV" in result or "Configured" in result

    def test_set_csv_connection_writes_correct_xml(self):
        base_dir = Path(__file__).parent.parent / "tmp" / "test_csv_mcp"
        base_dir.mkdir(parents=True, exist_ok=True)
        csv_path = base_dir / "tool_sales.csv"
        csv_path.write_text(
            "Order ID;State/Province;Sales\n"
            "1;California;100\n"
            "2;Nevada;200\n",
            encoding="utf-8",
        )

        set_csv_connection(filepath=str(csv_path))
        output = base_dir / "csv_mcp.twb"
        save_workbook(str(output))
        root = ET.parse(output).getroot()
        conn = root.find(".//connection[@class='textscan']")
        assert conn is not None
        assert conn.get("filename") == csv_path.name
        assert conn.get("directory") == str(csv_path.parent).replace("\\", "/")
        assert conn.get("separator") is None
        relation_columns = root.find(".//connection[@class='federated']/relation/columns")
        assert relation_columns is not None
        assert relation_columns.get("separator") == ";"

    def test_set_mysql_connection_returns_confirmation(self):
        result = set_mysql_connection(
            server="localhost",
            dbname="mydb",
            username="admin",
            table_name="orders",
        )
        assert "MySQL" in result or "mysql" in result.lower() or "Configured" in result

    def test_set_mysql_connection_writes_correct_xml(self, tmp_path):
        set_mysql_connection("db.host", "warehouse", "reader", "sales", port="3307")
        output = tmp_path / "mysql_mcp.twb"
        save_workbook(str(output))
        root = ET.parse(output).getroot()
        conn = root.find(".//connection[@class='mysql']")
        assert conn is not None
        assert conn.get("server") == "db.host"
        assert conn.get("dbname") == "warehouse"
        assert conn.get("port") == "3307"

    def test_set_tableauserver_connection_returns_confirmation(self):
        result = set_tableauserver_connection(
            server="tableau.example.com",
            dbname="corp_data",
            username="svc",
            table_name="proxy_table",
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_set_tableauserver_connection_writes_correct_xml(self, tmp_path):
        set_tableauserver_connection(
            server="ts.example.com",
            dbname="ds_001",
            username="",
            table_name="sqlproxy",
            port="82",
        )
        output = tmp_path / "tbs_mcp.twb"
        save_workbook(str(output))
        root = ET.parse(output).getroot()
        conn = root.find(".//connection[@class='sqlproxy']")
        assert conn is not None
        assert conn.get("server") == "ts.example.com"

    def test_set_hyper_connection_returns_confirmation(self):
        result = set_hyper_connection(filepath="data.hyper")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_set_hyper_connection_writes_correct_xml(self, tmp_path):
        set_hyper_connection(filepath="analysis.hyper", table_name="Extract")
        output = tmp_path / "hyper_mcp.twb"
        save_workbook(str(output))
        root = ET.parse(output).getroot()
        conn = root.find(".//connection[@class='hyper']")
        assert conn is not None
        assert "analysis.hyper" in (conn.get("dbname") or "")


# ── inspect_target_schema ─────────────────────────────────────────────────────

class TestInspectTargetSchema:
    def test_unsupported_file_type_returns_message(self):
        result = inspect_target_schema("not_a_hyper.csv")
        assert "Unsupported" in result

    def test_non_hyper_path_does_not_raise(self):
        result = inspect_target_schema("some_file.xlsx")
        assert isinstance(result, str)


class TestInspectExcelConnection:
    def test_preview_detects_multi_table_relationships(self, tmp_path):
        from openpyxl import Workbook

        xlsx_path = tmp_path / "preview_multi.xlsx"
        wb = Workbook()
        ws_orders = wb.active
        ws_orders.title = "Orders"
        ws_orders.append(["Order ID", "Region", "Sales"])
        ws_orders.append(["CA-1", "West", 100])
        ws_orders.append(["CA-2", "East", 200])

        ws_people = wb.create_sheet("People")
        ws_people.append(["Region", "Owner"])
        ws_people.append(["West", "Alice"])
        ws_people.append(["East", "Bob"])
        wb.save(xlsx_path)

        payload = json.loads(inspect_excel_connection(str(xlsx_path), sheet_name="Orders"))

        assert payload["multi_table"] is True
        assert payload["sheet_count"] == 2
        assert [table["name"] for table in payload["tables"]] == ["Orders", "People"]
        assert payload["relationships"] == [
            {
                "from_table": "Orders",
                "to_table": "People",
                "shared_fields": ["Region"],
            }
        ]
        assert payload["tables"][0]["fields"][0]["datatype"] == "string"
        assert payload["tables"][0]["fields"][2]["datatype"] == "integer"


# ── worksheet clone / refactor MCP wrappers ──────────────────────────────────

class TestWorksheetCloneRefactorTools:
    def test_clone_and_refactor_existing_kpi_sheet(self):
        open_workbook(str(EXAMPLE_WORKBOOK))

        clone_result = clone_worksheet("1. KPI", "1. KPI Profit MCP Tool")
        assert "1. KPI Profit MCP Tool" in clone_result

        preview_result = preview_worksheet_refactor(
            "1. KPI Profit MCP Tool",
            {"Sales": "Profit"},
        )
        preview_payload = json.loads(preview_result)
        assert preview_payload["worksheet_name"] == "1. KPI Profit MCP Tool"
        assert preview_payload["formulas_updated"]

        apply_result = apply_worksheet_refactor(
            "1. KPI Profit MCP Tool",
            {"Sales": "Profit"},
        )
        apply_payload = json.loads(apply_result)
        assert apply_payload["worksheet_name"] == "1. KPI Profit MCP Tool"
        assert apply_payload["reference_rewrites"]
        assert apply_payload["post_process"]["renamed"]
        assert any(
            renamed["source_name"].startswith("[Calculation_")
            for renamed in apply_payload["post_process"]["renamed"]
        )
        assert any(
            source.startswith("[Calculation_")
            for source in apply_payload["post_process"]["rewrite_map"]
        )

    def test_set_worksheet_hidden_can_unhide_clone(self):
        open_workbook(str(EXAMPLE_WORKBOOK))
        clone_worksheet("1. KPI", "1. KPI Visible MCP Tool")

        result = set_worksheet_hidden("1. KPI Visible MCP Tool", hidden=False)
        assert "unhidden" in result

        output = Path(".tmp_test_outputs")
        output.mkdir(exist_ok=True)
        workbook_path = output / "mcp_visible_kpi_clone.twb"
        save_workbook(str(workbook_path))

        root = ET.parse(workbook_path).getroot()
        window = root.find(".//windows/window[@class='worksheet'][@name='1. KPI Visible MCP Tool']")
        assert window is not None
        assert window.get("hidden") is None


# ── list_capabilities ─────────────────────────────────────────────────────────

class TestListCapabilities:
    def test_returns_catalog_text(self):
        result = list_capabilities()
        assert "Workflow guardrails:" in result
        assert "not a list of callable MCP tools" in result
        assert "add_dashboard and save_workbook are default MCP tools" in result
        assert "cwtwb capability catalog" in result
        assert "chart: Bar" in result
        assert "[core]" in result

    def test_includes_recipe_section(self):
        result = list_capabilities()
        assert "[recipe]" in result
        assert "Donut" in result or "donut" in result.lower()

    def test_level_filter_core_only(self):
        from cwtwb.server import list_capabilities as lc
        # list_capabilities MCP tool returns the full catalog; internal function
        # accepts a level filter — verify via the registry directly
        from cwtwb.capability_registry import format_capability_catalog
        core_catalog = format_capability_catalog(level_filter="core")
        assert "[core]" in core_catalog
        assert "[recipe]" not in core_catalog


# ── analyze_twb ───────────────────────────────────────────────────────────────

class TestAnalyzeTwb:
    def test_analyze_existing_template(self):
        path = Path("templates/viz/Tableau Advent Calendar.twb")
        if not path.exists():
            pytest.skip("Advent Calendar template not available")
        result = analyze_twb(str(path))
        assert "Template fit:" in result
        assert "Capability gap:" in result

    def test_analyze_generated_workbook(self, tmp_path):
        add_worksheet("Sales Bar")
        from cwtwb.server import configure_chart
        configure_chart("Sales Bar", mark_type="Bar", rows=["Category"], columns=["SUM(Sales)"])
        output = tmp_path / "analyze_test.twb"
        save_workbook(str(output))
        result = analyze_twb(str(output))
        assert isinstance(result, str)
        assert "fit" in result.lower() or "cap" in result.lower()


class TestValidateWorkbookHints:
    def test_in_memory_validation_includes_save_hint(self):
        result = validate_workbook()
        assert "does not save files" in result
        assert "Use save_workbook(output_path=...)" in result
