"""Tests for pie chart generation through the SDK.

Verifies that a pie chart worksheet is correctly configured with color and
wedge-size encodings, and produces valid TWB XML.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor

TEMPLATE = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"


@pytest.fixture
def pie_editor():
    ed = TWBEditor(TEMPLATE)
    ed.clear_worksheets()
    return ed


class TestPieChartGeneration:
    def test_pie_chart_mark_type(self, pie_editor):
        pie_editor.add_worksheet("pie_test")
        pie_editor.configure_chart(
            "pie_test",
            mark_type="Pie",
            color="Segment",
            wedge_size="SUM(Sales)",
        )
        ws = pie_editor._find_worksheet("pie_test")
        mark = ws.find(".//pane/mark")
        assert mark is not None
        assert mark.get("class") == "Pie"

    def test_pie_chart_color_encoding(self, pie_editor):
        pie_editor.add_worksheet("pie_test")
        pie_editor.configure_chart(
            "pie_test", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)"
        )
        ws = pie_editor._find_worksheet("pie_test")
        enc = ws.find(".//pane/encodings/color")
        assert enc is not None
        assert "Segment" in enc.get("column", "")

    def test_pie_chart_wedge_size_encoding(self, pie_editor):
        pie_editor.add_worksheet("pie_test")
        pie_editor.configure_chart(
            "pie_test", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)"
        )
        ws = pie_editor._find_worksheet("pie_test")
        enc = ws.find(".//pane/encodings/wedge-size")
        assert enc is not None
        assert "Sales" in enc.get("column", "")

    def test_pie_chart_saves_valid_twb(self, pie_editor, tmp_path):
        pie_editor.add_worksheet("pie_test")
        pie_editor.configure_chart(
            "pie_test", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)"
        )
        output = tmp_path / "pie_test.twb"
        pie_editor.save(output)
        assert output.exists()
        root = ET.parse(output).getroot()
        assert root.find(".//worksheet[@name='pie_test']") is not None

    def test_pie_chart_has_no_row_col_shelf(self, pie_editor):
        """Pie charts should not need rows/cols shelf."""
        pie_editor.add_worksheet("pie_test")
        pie_editor.configure_chart(
            "pie_test", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)"
        )
        ws = pie_editor._find_worksheet("pie_test")
        rows_text = (ws.findtext("./table/rows") or "").strip()
        cols_text = (ws.findtext("./table/cols") or "").strip()
        assert rows_text == ""
        assert cols_text == ""
