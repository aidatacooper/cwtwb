"""Tests for configure_worksheet_style and all its styling options.

Covers every option exposed by the function, verifying the resulting
XML structure matches what apply_worksheet_style / helpers.py produces.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def ws_editor():
    """Editor with a single 'Chart' worksheet pre-configured as a bar chart."""
    template = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"
    ed = TWBEditor(template)
    ed.add_worksheet("Chart")
    ed.configure_chart("Chart", mark_type="Bar", rows=["Category"], columns=["SUM(Sales)"])
    return ed


def _table_style_formats(editor: TWBEditor, ws_name: str) -> dict[tuple, str]:
    """Return {(element, attr, scope, field): value} for all table-style formats."""
    ws = editor._find_worksheet(ws_name)
    result: dict[tuple, str] = {}
    for rule in ws.findall("./table/style/style-rule"):
        el = rule.get("element", "")
        for fmt in rule.findall("format"):
            key = (el, fmt.get("attr", ""), fmt.get("scope", ""), fmt.get("field", ""))
            result[key] = fmt.get("value", "")
    return result


# ── basic visibility toggles ─────────────────────────────────────────────────

class TestHideBasicOptions:
    def test_hide_axes(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_axes=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("axis", "display", "", "")) == "false"

    def test_hide_gridlines(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_gridlines=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("gridline", "line-visibility", "", "")) == "off"

    def test_hide_zeroline(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_zeroline=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("zeroline", "line-visibility", "", "")) == "off"
        assert fmts.get(("zeroline", "stroke-size", "", "")) == "0"

    def test_hide_borders(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_borders=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("pane", "border-width", "", "")) == "0"
        assert fmts.get(("pane", "border-style", "", "")) == "none"
        assert fmts.get(("header", "border-width", "", "")) == "0"

    def test_hide_band_color(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_band_color=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("pane", "band-color", "", "")) == "#00000000"

    def test_background_color(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", background_color="#001122")
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("table", "background-color", "", "")) == "#001122"


# ── field-label visibility ────────────────────────────────────────────────────

class TestHideFieldLabels:
    def test_hide_col_field_labels(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_col_field_labels=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("worksheet", "display-field-labels", "cols", "")) == "false"

    def test_hide_row_field_labels(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_row_field_labels=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("worksheet", "display-field-labels", "rows", "")) == "false"

    def test_hide_both_field_labels(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart", hide_col_field_labels=True, hide_row_field_labels=True
        )
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("worksheet", "display-field-labels", "cols", "")) == "false"
        assert fmts.get(("worksheet", "display-field-labels", "rows", "")) == "false"


# ── line / divider hiding ─────────────────────────────────────────────────────

class TestHideLines:
    def test_hide_droplines(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_droplines=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("dropline", "line-visibility", "", "")) == "off"
        assert fmts.get(("dropline", "stroke-size", "", "")) == "0"

    def test_hide_reflines(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_reflines=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("refline", "line-visibility", "", "")) == "off"
        assert fmts.get(("refline", "stroke-size", "", "")) == "0"

    def test_hide_table_dividers(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", hide_table_dividers=True)
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("table-div", "line-visibility", "rows", "")) == "off"
        assert fmts.get(("table-div", "line-visibility", "cols", "")) == "off"
        assert fmts.get(("table-div", "stroke-size", "rows", "")) == "0"


# ── tooltip disable ───────────────────────────────────────────────────────────

class TestDisableTooltip:
    def test_disable_tooltip_adds_element(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", disable_tooltip=True)
        ws = ws_editor._find_worksheet("Chart")
        ts = ws.find("./table/tooltip-style")
        assert ts is not None
        assert ts.get("tooltip-mode") == "none"

    def test_no_tooltip_element_by_default(self, ws_editor):
        ws = ws_editor._find_worksheet("Chart")
        assert ws.find("./table/tooltip-style") is None


# ── pane-level styles ─────────────────────────────────────────────────────────

class TestPaneStyles:
    def _pane_style_formats(self, editor, ws_name):
        ws = editor._find_worksheet(ws_name)
        result = {}
        pane = ws.find(".//pane")
        if pane is None:
            return result
        for rule in pane.findall("./style/style-rule"):
            el = rule.get("element", "")
            for fmt in rule.findall("format"):
                key = (el, fmt.get("attr", ""))
                result[key] = fmt.get("value", "")
        return result

    def test_pane_cell_style(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            pane_cell_style={"text-align": "center", "vertical-align": "center"},
        )
        fmts = self._pane_style_formats(ws_editor, "Chart")
        assert fmts.get(("cell", "text-align")) == "center"
        assert fmts.get(("cell", "vertical-align")) == "center"

    def test_pane_datalabel_style(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            pane_datalabel_style={"font-size": "18", "font-family": "Tableau Medium"},
        )
        fmts = self._pane_style_formats(ws_editor, "Chart")
        assert fmts.get(("datalabel", "font-size")) == "18"
        assert fmts.get(("datalabel", "font-family")) == "Tableau Medium"

    def test_pane_mark_style(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            pane_mark_style={"mark-color": "#5a6dff", "has-stroke": "true"},
        )
        fmts = self._pane_style_formats(ws_editor, "Chart")
        assert fmts.get(("mark", "mark-color")) == "#5a6dff"
        assert fmts.get(("mark", "has-stroke")) == "true"

    def test_pane_trendline_hidden(self, ws_editor):
        ws_editor.configure_worksheet_style("Chart", pane_trendline_hidden=True)
        fmts = self._pane_style_formats(ws_editor, "Chart")
        assert fmts.get(("trendline", "line-visibility")) == "off"
        assert fmts.get(("trendline", "stroke-size")) == "0"


# ── per-field format lists ────────────────────────────────────────────────────

class TestPerFieldFormats:
    def test_label_formats(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            label_formats=[{"field": "MONTH(Order Date)", "font-family": "Tableau Medium"}],
        )
        ws = ws_editor._find_worksheet("Chart")
        label_rule = ws.find("./table/style/style-rule[@element='label']")
        assert label_rule is not None
        fmt = label_rule.find("format[@attr='font-family']")
        assert fmt is not None
        assert fmt.get("value") == "Tableau Medium"

    def test_cell_formats(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            cell_formats=[{"field": "SUM(Sales)", "font-weight": "bold"}],
        )
        ws = ws_editor._find_worksheet("Chart")
        cell_rule = ws.find("./table/style/style-rule[@element='cell']")
        assert cell_rule is not None
        fmt = cell_rule.find("format[@attr='font-weight']")
        assert fmt is not None
        assert fmt.get("value") == "bold"

    def test_header_formats(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            header_formats=[{"field": "Category", "height": "28"}],
        )
        ws = ws_editor._find_worksheet("Chart")
        header_rule = ws.find("./table/style/style-rule[@element='header']")
        assert header_rule is not None
        fmt = header_rule.find("format[@attr='height']")
        assert fmt is not None
        assert fmt.get("value") == "28"


# ── axis_style ────────────────────────────────────────────────────────────────

class TestAxisStyle:
    def test_axis_style_global_attr(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            axis_style={"tick-color": "#00000000"},
        )
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("axis", "tick-color", "", "")) == "#00000000"

    def test_axis_style_per_field(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            axis_style={
                "per_field": [{"field": "SUM(Sales)", "attr": "height", "value": "35"}]
            },
        )
        ws = ws_editor._find_worksheet("Chart")
        rule = ws.find("./table/style/style-rule[@element='axis']")
        assert rule is not None
        # A format with attr=height should be present
        fmt = rule.find("format[@attr='height']")
        assert fmt is not None
        assert fmt.get("value") == "35"


# ── combined options ──────────────────────────────────────────────────────────

class TestCombinedOptions:
    def test_transparent_kpi_strip_style(self, ws_editor):
        """Simulates the 'CY Sales Labels' KPI strip pattern from MEMORY.md."""
        ws_editor.configure_worksheet_style(
            "Chart",
            background_color="#00000000",
            hide_axes=True,
            hide_gridlines=True,
            hide_zeroline=True,
            hide_borders=True,
            hide_band_color=True,
            hide_col_field_labels=True,
            hide_droplines=True,
            hide_table_dividers=True,
        )
        fmts = _table_style_formats(ws_editor, "Chart")
        assert fmts.get(("table", "background-color", "", "")) == "#00000000"
        assert fmts.get(("axis", "display", "", "")) == "false"
        assert fmts.get(("gridline", "line-visibility", "", "")) == "off"
        assert fmts.get(("worksheet", "display-field-labels", "cols", "")) == "false"
