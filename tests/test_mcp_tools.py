"""Tests for the MCP tool-layer wrappers (server.py exports).

Verifies that tools correctly relay calls to the editor and return
properly-formatted string payloads. Covers:
  - remove_calculated_field
  - set_mysql_connection / set_tableauserver_connection / set_hyper_connection (MCP layer)
  - inspect_target_schema (non-hyper path returns informative message)
  - list_capabilities
  - analyze_twb
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.server import (
    add_calculated_field,
    add_worksheet,
    create_workbook,
    list_capabilities,
    list_fields,
    remove_calculated_field,
    save_workbook,
    set_hyper_connection,
    set_mysql_connection,
    set_tableauserver_connection,
    analyze_twb,
    inspect_target_schema,
)

TEMPLATE = Path("templates/twb/superstore.twb")


@pytest.fixture(autouse=True)
def fresh_workbook():
    """Ensure each test starts with a clean workbook state."""
    create_workbook(str(TEMPLATE), "MCP Tool Tests")


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


# ── list_capabilities ─────────────────────────────────────────────────────────

class TestListCapabilities:
    def test_returns_catalog_text(self):
        result = list_capabilities()
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
