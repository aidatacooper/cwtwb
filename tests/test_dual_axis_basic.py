"""Tests for basic dual-axis chart configurations.

Covers horizontal/vertical dual-axis combos (lollipop style) through the SDK.
Advanced options (mark_color, color_map_1, reverse_axis) are in test_dual_axis_advanced.py.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor


TEMPLATE = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"


@pytest.fixture
def editor():
    return TWBEditor(TEMPLATE)


class TestDualAxisHorizontal:
    """Horizontal dual-axis: two measures on the column shelf."""

    def test_lollipop_horizontal_generates_worksheet(self, editor, tmp_path):
        editor.add_worksheet("Lollipop Horizontal")
        editor.configure_dual_axis(
            "Lollipop Horizontal",
            columns=["SUM(Sales)", "SUM(Sales)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            mark_type_1="Bar",
            mark_type_2="Circle",
        )
        output = tmp_path / "lollipop_horizontal.twb"
        editor.save(output)
        root = ET.parse(output).getroot()
        ws = root.find(".//worksheet[@name='Lollipop Horizontal']")
        assert ws is not None

    def test_lollipop_horizontal_pane_marks(self, editor):
        editor.add_worksheet("Lollipop H")
        editor.configure_dual_axis(
            "Lollipop H",
            columns=["SUM(Sales)", "SUM(Sales)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            mark_type_1="Bar",
            mark_type_2="Circle",
        )
        ws = editor._find_worksheet("Lollipop H")
        pane1 = ws.find(".//pane[@id='1']")
        pane2 = ws.find(".//pane[@id='2']")
        assert pane1 is not None
        assert pane2 is not None
        assert pane1.find("mark").get("class") == "Bar"
        assert pane2.find("mark").get("class") == "Circle"

    def test_horizontal_dual_axis_pane2_has_x_index(self, editor):
        editor.add_worksheet("Lollipop H2")
        editor.configure_dual_axis(
            "Lollipop H2",
            columns=["SUM(Sales)", "SUM(Sales)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            mark_type_1="Bar",
            mark_type_2="Circle",
        )
        ws = editor._find_worksheet("Lollipop H2")
        pane2 = ws.find(".//pane[@id='2']")
        assert pane2 is not None
        assert pane2.get("x-index") == "1"

    def test_horizontal_dual_axis_panes_share_x_axis(self, editor):
        editor.add_worksheet("Lollipop H3")
        editor.configure_dual_axis(
            "Lollipop H3",
            columns=["SUM(Sales)", "SUM(Sales)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            mark_type_1="Bar",
            mark_type_2="Circle",
            synchronized=True,
        )
        ws = editor._find_worksheet("Lollipop H3")
        pane1 = ws.find(".//pane[@id='1']")
        pane2 = ws.find(".//pane[@id='2']")
        assert pane1 is not None and pane2 is not None
        assert pane1.get("x-axis-name") == pane2.get("x-axis-name")


class TestDualAxisVertical:
    """Vertical dual-axis: two measures on the rows shelf (typical bar+line combo)."""

    def test_bar_line_combo_generates_two_panes(self, editor):
        editor.add_worksheet("Combo V")
        editor.configure_dual_axis(
            "Combo V",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Profit)"],
            dual_axis_shelf="rows",
            mark_type_1="Bar",
            mark_type_2="Line",
        )
        ws = editor._find_worksheet("Combo V")
        panes = ws.findall(".//pane[@id]")
        assert len(panes) >= 2

    def test_bar_line_combo_marks(self, editor):
        editor.add_worksheet("Combo V2")
        editor.configure_dual_axis(
            "Combo V2",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Profit)"],
            dual_axis_shelf="rows",
            mark_type_1="Bar",
            mark_type_2="Line",
        )
        ws = editor._find_worksheet("Combo V2")
        assert ws.find(".//pane[@id='1']/mark[@class='Bar']") is not None
        assert ws.find(".//pane[@id='2']/mark[@class='Line']") is not None

    def test_dual_axis_with_color_encoding(self, editor):
        editor.add_worksheet("Combo Color")
        editor.configure_dual_axis(
            "Combo Color",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Profit)"],
            dual_axis_shelf="rows",
            mark_type_1="Bar",
            mark_type_2="Line",
            color_1="Category",
        )
        ws = editor._find_worksheet("Combo Color")
        pane1 = ws.find(".//pane[@id='1']")
        assert pane1 is not None
        enc = pane1.find("./encodings/color")
        assert enc is not None
        assert "Category" in enc.get("column", "")


class TestDualAxisWithFilters:
    def test_dual_axis_accepts_filters(self, editor):
        editor.add_worksheet("Combo Filtered")
        editor.configure_dual_axis(
            "Combo Filtered",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Profit)"],
            dual_axis_shelf="rows",
            mark_type_1="Bar",
            mark_type_2="Line",
            filters=[{"column": "Region", "values": ["East", "West"]}],
        )
        ws = editor._find_worksheet("Combo Filtered")
        filter_el = ws.find(".//view/filter[@class='categorical']")
        assert filter_el is not None
        assert "Region" in filter_el.get("column", "")
