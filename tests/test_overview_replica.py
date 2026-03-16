"""Integration test: Overview dashboard with parameters, calculated fields,
map chart, area charts, filter zones, and paramctrl zone.

Validates that the full pipeline (MCP tools → save → parse) produces the
expected XML structure without requiring Tableau Desktop.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.server import (
    add_calculated_field,
    add_dashboard,
    add_parameter,
    add_worksheet,
    configure_chart,
    create_workbook,
    save_workbook,
)

TEMPLATE = Path("templates/twb/superstore.twb")


@pytest.fixture(autouse=True)
def fresh_workbook():
    create_workbook(str(TEMPLATE), "Overview Replica")


def _build_overview(tmp_path) -> ET.Element:
    """Build the full Overview workbook and return the parsed XML root."""
    add_parameter(
        name="Target Profit",
        datatype="real",
        default_value="10000.0",
        domain_type="range",
        min_value="-30000.0",
        max_value="100000.0",
        granularity="10000.0",
    )
    add_parameter(
        name="Churn Rate",
        datatype="real",
        default_value="0.1",
        domain_type="range",
        min_value="0.0",
        max_value="1.0",
        granularity="0.05",
    )

    add_calculated_field("Profit Ratio", "SUM([Profit])/SUM([Sales])", "real")
    add_calculated_field(
        "Order Profitable?",
        "IF SUM([Profit]) > [Target Profit] THEN 'Profitable' ELSE 'Unprofitable' END",
        "string",
    )

    add_worksheet("SaleMap")
    configure_chart(
        "SaleMap", mark_type="Map",
        geographic_field="State/Province",
        color="Order Profitable?",
        size="SUM(Sales)",
    )

    add_worksheet("SalesbyProduct")
    configure_chart(
        "SalesbyProduct", mark_type="Area",
        columns=["MONTH(Order Date)"], rows=["SUM(Sales)"], color="Category",
    )

    add_worksheet("SalesbySegment")
    configure_chart(
        "SalesbySegment", mark_type="Area",
        columns=["MONTH(Order Date)"], rows=["SUM(Sales)"], color="Segment",
    )

    add_worksheet("Total Sales")
    configure_chart("Total Sales", mark_type="Text", label="SUM(Sales)")

    layout = {
        "type": "container",
        "direction": "horizontal",
        "children": [
            {
                "type": "container",
                "direction": "vertical",
                "weight": 3,
                "children": [
                    {
                        "type": "container",
                        "direction": "horizontal",
                        "children": [
                            {"type": "worksheet", "name": "SaleMap", "weight": 2},
                            {"type": "worksheet", "name": "Total Sales", "weight": 1},
                        ],
                    },
                    {
                        "type": "container",
                        "direction": "horizontal",
                        "children": [
                            {"type": "worksheet", "name": "SalesbyProduct"},
                            {"type": "worksheet", "name": "SalesbySegment"},
                        ],
                    },
                ],
            },
            {
                "type": "container",
                "direction": "vertical",
                "fixed_size": 180,
                "children": [
                    {"type": "filter", "worksheet": "SaleMap", "field": "Region",
                     "mode": "dropdown", "fixed_size": 60},
                    {"type": "filter", "worksheet": "SaleMap", "field": "State/Province",
                     "mode": "checkdropdown", "fixed_size": 60},
                    {"type": "paramctrl", "parameter": "Target Profit",
                     "mode": "slider", "fixed_size": 60},
                ],
            },
        ],
    }

    add_dashboard(
        "Overview",
        worksheet_names=["SaleMap", "SalesbyProduct", "SalesbySegment", "Total Sales"],
        width=936, height=650, layout=layout,
    )

    output = tmp_path / "overview_replica.twb"
    save_workbook(str(output))
    return ET.parse(output).getroot()


class TestOverviewWorksheets:
    def test_all_worksheets_present(self, tmp_path):
        root = _build_overview(tmp_path)
        expected = {"SaleMap", "SalesbyProduct", "SalesbySegment", "Total Sales"}
        found = {ws.get("name") for ws in root.findall(".//worksheet")}
        assert expected.issubset(found)

    def test_map_chart_mark_type(self, tmp_path):
        root = _build_overview(tmp_path)
        ws = root.find(".//worksheet[@name='SaleMap']")
        assert ws.find(".//pane/mark[@class='Multipolygon']") is not None

    def test_area_chart_mark_type(self, tmp_path):
        root = _build_overview(tmp_path)
        for ws_name in ("SalesbyProduct", "SalesbySegment"):
            ws = root.find(f".//worksheet[@name='{ws_name}']")
            assert ws.find(".//pane/mark[@class='Area']") is not None, ws_name

    def test_kpi_text_mark_type(self, tmp_path):
        root = _build_overview(tmp_path)
        ws = root.find(".//worksheet[@name='Total Sales']")
        assert ws.find(".//pane/mark[@class='Text']") is not None


class TestOverviewParameters:
    def test_target_profit_parameter_present(self, tmp_path):
        root = _build_overview(tmp_path)
        params_ds = root.find(".//datasource[@name='Parameters']")
        assert params_ds is not None
        col = params_ds.find("column[@caption='Target Profit']")
        assert col is not None

    def test_two_parameters_present(self, tmp_path):
        root = _build_overview(tmp_path)
        params_ds = root.find(".//datasource[@name='Parameters']")
        assert params_ds is not None
        assert len(params_ds.findall("column")) == 2


class TestOverviewDashboard:
    def test_dashboard_exists(self, tmp_path):
        root = _build_overview(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Overview']")
        assert db is not None

    def test_dashboard_contains_all_worksheets(self, tmp_path):
        root = _build_overview(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Overview']")
        zone_names = {z.get("name") for z in db.findall(".//zone[@name]")}
        for ws_name in ("SaleMap", "SalesbyProduct", "SalesbySegment", "Total Sales"):
            assert ws_name in zone_names, f"Missing zone: {ws_name}"

    def test_filter_zones_present(self, tmp_path):
        root = _build_overview(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Overview']")
        filter_zones = db.findall(".//zone[@type-v2='filter']")
        assert len(filter_zones) >= 2

    def test_paramctrl_zone_present(self, tmp_path):
        root = _build_overview(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Overview']")
        paramctrl_zones = db.findall(".//zone[@type-v2='paramctrl']")
        assert len(paramctrl_zones) >= 1
