"""Integration tests: Build dashboards from JSON layout files (screenshot-to-layout workflow).

Each test builds a multi-worksheet dashboard from a pre-saved JSON layout file
and asserts the resulting TWB has the expected worksheets and dashboard zone structure.

Tests are skipped if the layout JSON files are not present under
examples/screenshot2layout/, since those are optional example assets.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.server import (
    add_dashboard,
    add_worksheet,
    configure_chart,
    create_workbook,
    save_workbook,
)

TEMPLATE = Path("templates/twb/superstore.twb")
LAYOUT_DIR = Path("examples/screenshot2layout")
LAYOUT1 = LAYOUT_DIR / "layout_dashboard1.json"
LAYOUT2 = LAYOUT_DIR / "layout_dashboard2.json"


@pytest.fixture(autouse=True)
def fresh_workbook():
    create_workbook(str(TEMPLATE), "Screenshot2Layout Test")


# ── Dashboard 1: Superstore Shipping Metrics ──────────────────────────────────

SIDEBAR_KPIS = [
    ("Avg Delivery Days", "SUM(Quantity)"),
    ("Avg Fulfillment Days", "SUM(Discount)"),
    ("Orders KPI", "SUM(Quantity)"),
    ("Customers KPI", "SUM(Quantity)"),
    ("Returns KPI", "SUM(Quantity)"),
]
BREAKDOWN_SHEETS = ["Breakdown Customers", "Breakdown Orders", "Breakdown Returns"]
DASH1_ALL = (
    [n for n, _ in SIDEBAR_KPIS]
    + BREAKDOWN_SHEETS
    + ["Delivery Days Chart", "Customer Distribution Map", "Order Distribution Chart"]
)


def _build_dashboard1(tmp_path):
    create_workbook(str(TEMPLATE), "Shipping Metrics")

    for name, measure in SIDEBAR_KPIS:
        add_worksheet(name)
        configure_chart(name, mark_type="Text", label=measure)

    for name in BREAKDOWN_SHEETS:
        add_worksheet(name)
        configure_chart(name, mark_type="Bar", rows=["Ship Mode"], columns=["SUM(Sales)"])

    add_worksheet("Delivery Days Chart")
    configure_chart("Delivery Days Chart", mark_type="Bar",
                    columns=["SUM(Quantity)"], rows=["Ship Mode"], color="Segment")

    add_worksheet("Customer Distribution Map")
    configure_chart("Customer Distribution Map", mark_type="Bar",
                    rows=["Region"], columns=["SUM(Sales)"], color="Category")

    add_worksheet("Order Distribution Chart")
    configure_chart("Order Distribution Chart", mark_type="Circle",
                    rows=["Ship Mode"], columns=["SUM(Sales)"], size="SUM(Profit)")

    layout = str(LAYOUT1) if LAYOUT1.exists() else "horizontal"
    add_dashboard("Shipping Metrics", worksheet_names=DASH1_ALL,
                  width=1400, height=850, layout=layout)

    output = tmp_path / "screenshot_dashboard1.twb"
    save_workbook(str(output))
    return ET.parse(output).getroot()


class TestScreenshot2LayoutDashboard1:
    def test_all_worksheets_present(self, tmp_path):
        root = _build_dashboard1(tmp_path)
        found = {ws.get("name") for ws in root.findall(".//worksheet")}
        for name in DASH1_ALL:
            assert name in found, f"Missing worksheet: {name}"

    def test_kpi_worksheets_use_text_mark(self, tmp_path):
        root = _build_dashboard1(tmp_path)
        for name, _ in SIDEBAR_KPIS:
            ws = root.find(f".//worksheet[@name='{name}']")
            assert ws is not None
            assert ws.find(".//pane/mark[@class='Text']") is not None, name

    def test_dashboard_exists(self, tmp_path):
        root = _build_dashboard1(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Shipping Metrics']")
        assert db is not None

    def test_dashboard_contains_worksheets(self, tmp_path):
        root = _build_dashboard1(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Shipping Metrics']")
        zone_names = {z.get("name") for z in db.findall(".//zone[@name]")}
        for name in DASH1_ALL:
            assert name in zone_names, f"Dashboard missing zone: {name}"

    @pytest.mark.skipif(not LAYOUT1.exists(), reason="layout_dashboard1.json not present")
    def test_uses_json_layout_when_file_present(self, tmp_path):
        """When the JSON layout file exists, the dashboard should use it."""
        root = _build_dashboard1(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Shipping Metrics']")
        assert db is not None
        # Dashboard created from JSON layout will have nested zones
        root_zone = db.find("zones/zone")
        assert root_zone is not None


# ── Dashboard 2: Complaints Insights ─────────────────────────────────────────

SIDEBAR_COMPLAINTS = [
    ("YTD Total Complaints", "Text", "SUM(Quantity)"),
    ("Timely Response Pct", "Text", "SUM(Discount)"),
    ("Complaints by Channel", "Bar", None),
    ("Closed with Relief Pct", "Text", "SUM(Profit)"),
    ("Complaints Vol vs Relief", "Circle", None),
]
KPI_COMPLAINTS = [
    ("Total Complaints KPI", "SUM(Quantity)"),
    ("Timely Response KPI", "SUM(Discount)"),
    ("Closed with Monetary Relief KPI", "SUM(Profit)"),
]
YES_SHEETS = ["YES Count and Relief", "YES Top 10 Issues", "YES Complaint Details"]
NO_SHEETS = ["NO Count and Relief", "NO Top 10 Issues", "NO Complaint Details"]
DASH2_ALL = (
    [n for n, _, _ in SIDEBAR_COMPLAINTS]
    + [n for n, _ in KPI_COMPLAINTS]
    + YES_SHEETS
    + NO_SHEETS
)


def _build_dashboard2(tmp_path):
    create_workbook(str(TEMPLATE), "Complaints Insights")

    for name, mark, label in SIDEBAR_COMPLAINTS:
        add_worksheet(name)
        if mark == "Text":
            configure_chart(name, mark_type="Text", label=label)
        elif mark == "Bar":
            configure_chart(name, mark_type="Bar", rows=["Segment"], columns=["SUM(Sales)"])
        else:
            configure_chart(name, mark_type="Circle", rows=["Region"],
                            columns=["SUM(Sales)"], size="SUM(Profit)")

    for name, label in KPI_COMPLAINTS:
        add_worksheet(name)
        configure_chart(name, mark_type="Text", label=label)

    for name in YES_SHEETS + NO_SHEETS:
        add_worksheet(name)
        configure_chart(name, mark_type="Text", label="SUM(Sales)")

    layout = str(LAYOUT2) if LAYOUT2.exists() else "vertical"
    add_dashboard("Complaints Insights", worksheet_names=DASH2_ALL,
                  width=1500, height=800, layout=layout)

    output = tmp_path / "screenshot_dashboard2.twb"
    save_workbook(str(output))
    return ET.parse(output).getroot()


class TestScreenshot2LayoutDashboard2:
    def test_all_worksheets_present(self, tmp_path):
        root = _build_dashboard2(tmp_path)
        found = {ws.get("name") for ws in root.findall(".//worksheet")}
        for name in DASH2_ALL:
            assert name in found, f"Missing worksheet: {name}"

    def test_dashboard_exists(self, tmp_path):
        root = _build_dashboard2(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Complaints Insights']")
        assert db is not None

    def test_dashboard_contains_all_worksheets(self, tmp_path):
        root = _build_dashboard2(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Complaints Insights']")
        zone_names = {z.get("name") for z in db.findall(".//zone[@name]")}
        for name in DASH2_ALL:
            assert name in zone_names, f"Dashboard missing zone: {name}"

    @pytest.mark.skipif(not LAYOUT2.exists(), reason="layout_dashboard2.json not present")
    def test_uses_json_layout_when_file_present(self, tmp_path):
        root = _build_dashboard2(tmp_path)
        db = root.find(".//dashboards/dashboard[@name='Complaints Insights']")
        assert db is not None
        root_zone = db.find("zones/zone")
        assert root_zone is not None
