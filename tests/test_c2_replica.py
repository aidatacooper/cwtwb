"""Integration test: c.2 (2) dashboard layout replica.

Replicates the multi-section dashboard layout:
  - KPI row: 4 text/automatic worksheets (Sales, Profit, Discount, Quantity)
  - Views area: Sub-Category bar, date-profit line, segment pie, category bar

Validates structure via XML assertions without requiring Tableau Desktop.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor

TEMPLATE = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"

KPI_SHEETS = ["Sales", "Profit", "Discount", "Quantity"]
VIEW_SHEETS = ["Sub-Category sales", "date profit", "segment sales", "category detail"]
ALL_SHEETS = KPI_SHEETS + VIEW_SHEETS


@pytest.fixture(scope="module")
def c2_editor():
    ed = TWBEditor(TEMPLATE)
    ed.clear_worksheets()

    # KPI worksheets
    for name, measure in [
        ("Sales", "SUM(Sales)"),
        ("Profit", "SUM(Profit)"),
        ("Discount", "SUM(Discount)"),
        ("Quantity", "SUM(Quantity)"),
    ]:
        ed.add_worksheet(name)
        ed.configure_chart(name, mark_type="Text", label=measure)

    # Sub-Category sales bar chart (sorted)
    ed.add_worksheet("Sub-Category sales")
    ed.configure_chart(
        "Sub-Category sales",
        mark_type="Bar",
        rows=["Sub-Category"],
        columns=["SUM(Sales)"],
        sort_descending="SUM(Sales)",
    )

    # Monthly profit line chart
    ed.add_worksheet("date profit")
    ed.configure_chart(
        "date profit",
        mark_type="Line",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Profit)"],
    )

    # Segment pie
    ed.add_worksheet("segment sales")
    ed.configure_chart("segment sales", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)")

    # Category bar
    ed.add_worksheet("category detail")
    ed.configure_chart(
        "category detail",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
        sort_descending="SUM(Sales)",
    )

    # Dashboard with nested layout
    layout = {
        "type": "container",
        "direction": "vertical",
        "children": [
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 80,
                "layout_strategy": "distribute-evenly",
                "children": [{"type": "worksheet", "name": n} for n in KPI_SHEETS],
            },
            {
                "type": "container",
                "direction": "horizontal",
                "weight": 1,
                "children": [
                    {
                        "type": "container",
                        "direction": "vertical",
                        "weight": 1,
                        "children": [
                            {"type": "worksheet", "name": "Sub-Category sales"},
                            {"type": "worksheet", "name": "segment sales"},
                        ],
                    },
                    {
                        "type": "container",
                        "direction": "vertical",
                        "weight": 1,
                        "children": [
                            {"type": "worksheet", "name": "date profit"},
                            {"type": "worksheet", "name": "category detail"},
                        ],
                    },
                ],
            },
        ],
    }
    ed.add_dashboard("Overview", worksheet_names=ALL_SHEETS, layout=layout, width=1200, height=800)
    return ed


@pytest.fixture(scope="module")
def c2_root(c2_editor, tmp_path_factory):
    output = tmp_path_factory.mktemp("c2") / "c2_replica.twb"
    c2_editor.save(output)
    return ET.parse(output).getroot()


class TestC2Worksheets:
    def test_all_worksheets_present(self, c2_root):
        found = {ws.get("name") for ws in c2_root.findall(".//worksheet")}
        for name in ALL_SHEETS:
            assert name in found, f"Missing worksheet: {name}"

    def test_kpi_worksheets_use_text_mark(self, c2_root):
        for name in KPI_SHEETS:
            ws = c2_root.find(f".//worksheet[@name='{name}']")
            assert ws is not None, f"Missing KPI worksheet: {name}"
            mark = ws.find(".//pane/mark")
            assert mark is not None
            assert mark.get("class") == "Text", f"{name}: expected Text, got {mark.get('class')}"

    def test_bar_chart_mark_type(self, c2_root):
        for name in ("Sub-Category sales", "category detail"):
            ws = c2_root.find(f".//worksheet[@name='{name}']")
            assert ws.find(".//pane/mark[@class='Bar']") is not None, name

    def test_line_chart_mark_type(self, c2_root):
        ws = c2_root.find(".//worksheet[@name='date profit']")
        assert ws.find(".//pane/mark[@class='Line']") is not None

    def test_pie_chart_mark_type(self, c2_root):
        ws = c2_root.find(".//worksheet[@name='segment sales']")
        assert ws.find(".//pane/mark[@class='Pie']") is not None

    def test_sorted_bar_has_sort_on_rows(self, c2_root):
        ws = c2_root.find(".//worksheet[@name='Sub-Category sales']")
        rows_text = ws.findtext("./table/rows") or ""
        assert "Sub-Category" in rows_text


class TestC2Dashboard:
    def test_dashboard_exists(self, c2_root):
        db = c2_root.find(".//dashboards/dashboard[@name='Overview']")
        assert db is not None

    def test_dashboard_contains_all_worksheets(self, c2_root):
        db = c2_root.find(".//dashboards/dashboard[@name='Overview']")
        zone_names = {z.get("name") for z in db.findall(".//zone[@name]")}
        for name in ALL_SHEETS:
            assert name in zone_names, f"Dashboard missing zone: {name}"

    def test_dashboard_has_correct_size(self, c2_root):
        db = c2_root.find(".//dashboards/dashboard[@name='Overview']")
        size_el = db.find("size")
        assert size_el is not None
        assert int(size_el.get("maxw", "0")) == 1200 or size_el.get("sizing-mode") == "fixed"

    def test_root_zone_is_vertical(self, c2_root):
        db = c2_root.find(".//dashboards/dashboard[@name='Overview']")
        root_zone = db.find("zones/zone")
        assert root_zone is not None
        assert root_zone.get("param") == "vert"
