"""End-to-end tests: full MCP workflow from create_workbook to save_workbook.

Exercises every tool in the standard authoring sequence and validates the
resulting TWB structure. Simulates real Claude agent usage patterns.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.server import (
    add_calculated_field,
    add_dashboard,
    add_worksheet,
    configure_chart,
    create_workbook,
    list_fields,
    save_workbook,
)

TEMPLATE = Path("templates/twb/superstore.twb")


@pytest.fixture(autouse=True)
def fresh_workbook():
    create_workbook(str(TEMPLATE), "E2E Test")


class TestFullWorkflow:
    def test_calculated_field_appears_in_list_fields(self):
        add_calculated_field(
            "Profit Ratio",
            "SUM([Profit (Orders)])/SUM([Sales (Orders)])",
            "real",
        )
        assert "Profit Ratio" in list_fields()

    def test_bar_chart_worksheet_written_to_twb(self, tmp_path):
        add_worksheet("Sales by Category")
        configure_chart(
            "Sales by Category",
            mark_type="Bar",
            rows=["Category"],
            columns=["SUM(Sales)"],
        )
        output = tmp_path / "e2e_bar.twb"
        save_workbook(str(output))

        root = ET.parse(output).getroot()
        ws = root.find(".//worksheet[@name='Sales by Category']")
        assert ws is not None
        assert ws.find(".//pane/mark[@class='Bar']") is not None

    def test_pie_chart_worksheet_written_to_twb(self, tmp_path):
        add_worksheet("Segment Pie")
        configure_chart("Segment Pie", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)")
        output = tmp_path / "e2e_pie.twb"
        save_workbook(str(output))

        root = ET.parse(output).getroot()
        ws = root.find(".//worksheet[@name='Segment Pie']")
        assert ws is not None
        assert ws.find(".//pane/mark[@class='Pie']") is not None

    def test_dashboard_contains_both_worksheets(self, tmp_path):
        add_worksheet("Sales by Category")
        configure_chart("Sales by Category", mark_type="Bar", rows=["Category"], columns=["SUM(Sales)"])
        add_worksheet("Segment Pie")
        configure_chart("Segment Pie", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)")
        add_dashboard("Overview", worksheet_names=["Sales by Category", "Segment Pie"], layout="horizontal")
        output = tmp_path / "e2e_dashboard.twb"
        save_workbook(str(output))

        root = ET.parse(output).getroot()
        db = root.find(".//dashboards/dashboard[@name='Overview']")
        assert db is not None
        zone_names = {z.get("name") for z in db.findall(".//zone[@name]")}
        assert "Sales by Category" in zone_names
        assert "Segment Pie" in zone_names

    def test_save_workbook_creates_file(self, tmp_path):
        output = tmp_path / "e2e_saved.twb"
        result = save_workbook(str(output))
        assert output.exists()
        assert isinstance(result, str)


class TestCalculatedFieldSemantics:
    def test_real_field_gets_quantitative_type(self, tmp_path):
        add_calculated_field("Revenue Delta", "SUM([Sales])-SUM([Profit])", "real")
        output = tmp_path / "e2e_real_field.twb"
        save_workbook(str(output))
        root = ET.parse(output).getroot()
        col = root.find(".//datasource/column[@caption='Revenue Delta']")
        assert col is not None
        assert col.get("type") == "quantitative"

    def test_string_field_gets_nominal_type(self, tmp_path):
        add_calculated_field(
            "Profit Category",
            'IF SUM([Profit]) > 0 THEN "Good" ELSE "Bad" END',
            "string",
        )
        output = tmp_path / "e2e_string_field.twb"
        save_workbook(str(output))
        root = ET.parse(output).getroot()
        col = root.find(".//datasource/column[@caption='Profit Category']")
        assert col is not None
        assert col.get("type") == "nominal"

    def test_workbook_has_no_spurious_top_level_elements(self, tmp_path):
        output = tmp_path / "e2e_clean.twb"
        save_workbook(str(output))
        root = ET.parse(output).getroot()
        assert root.find("worksheets") is None
        assert root.find("windows") is None
        assert root.find("thumbnails") is None
