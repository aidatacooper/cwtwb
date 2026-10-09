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
    template = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"
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


# ── advanced styling options ──────────────────────────────────────────────────

class TestAdvancedStylingOptions:
    def test_custom_table_dividers(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            table_dividers=[
                {"scope": "rows", "div-level": "1", "stroke-color": "#d4d4d4", "line-visibility": "on", "line-pattern-only": "dotted"},
                {"scope": "cols", "stroke-size": "0", "line-visibility": "off"},
            ],
        )
        ws = ws_editor._find_worksheet("Chart")
        tdiv_rule = ws.find("./table/style/style-rule[@element='table-div']")
        assert tdiv_rule is not None
        fmts = {(f.get("attr"), f.get("scope")): f.get("value") for f in tdiv_rule.findall("format")}
        assert fmts.get(("div-level", "rows")) == "1"
        assert fmts.get(("stroke-color", "rows")) == "#d4d4d4"
        assert fmts.get(("line-visibility", "rows")) == "on"
        assert fmts.get(("line-pattern-only", "rows")) == "dotted"
        assert fmts.get(("stroke-size", "cols")) == "0"
        assert fmts.get(("line-visibility", "cols")) == "off"

    def test_show_totals(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            show_column_totals=True,
            show_row_totals=True,
        )
        ws = ws_editor._find_worksheet("Chart")
        assert ws.find("./table/cols").get("total") == "true"
        assert ws.find("./table/rows").get("total") == "true"

    def test_panes_style_multi_pane(self, ws_editor):
        # Configure dual axis to create multiple panes
        ws_editor.configure_dual_axis(
            "Chart",
            mark_type_1="Pie",
            mark_type_2="Circle",
            columns=["SUM(Sales)", "AVG(Profit)"],
            rows=["Category"],
            dual_axis_shelf="columns",
        )
        ws_editor.configure_worksheet_style(
            "Chart",
            panes_style={
                "1": {"mark_style": {"size": "1.15"}},
                "2": {
                    "mark_style": {"size": "0.82"},
                    "cell_style": {"text-align": "center", "vertical-align": "center"},
                    "datalabel_style": {"font-size": "6", "color-mode": "auto"},
                },
            },
        )
        ws = ws_editor._find_worksheet("Chart")
        p1 = ws.find("./table/panes/pane[@id='1']")
        p2 = ws.find("./table/panes/pane[@id='2']")
        assert p1 is not None and p2 is not None
        # Verify p1 mark size
        p1_size = p1.find("./style/style-rule[@element='mark']/format[@attr='size']")
        assert p1_size is not None and p1_size.get("value") == "1.15"
        # Verify p2 mark size and cell style
        p2_size = p2.find("./style/style-rule[@element='mark']/format[@attr='size']")
        assert p2_size is not None and p2_size.get("value") == "0.82"
        p2_align = p2.find("./style/style-rule[@element='cell']/format[@attr='text-align']")
        assert p2_align is not None and p2_align.get("value") == "center"
        p2_fontsize = p2.find("./style/style-rule[@element='datalabel']/format[@attr='font-size']")
        assert p2_fontsize is not None and p2_fontsize.get("value") == "6"

    def test_header_formats_with_total_attributes(self, ws_editor):
        ws_editor.configure_worksheet_style(
            "Chart",
            header_formats=[
                {"attr": "height-header", "value": "12"},
                {"attr": "border-width", "data_class": "total", "scope": "cols", "value": "0"},
                {"field": "Category", "attr": "total-label", "data_class": "total", "value": "Last 7 days"},
            ],
        )
        ws = ws_editor._find_worksheet("Chart")
        hdr_rule = ws.find("./table/style/style-rule[@element='header']")
        assert hdr_rule is not None
        fmts = hdr_rule.findall("format")
        assert len(fmts) == 3
        f_h = hdr_rule.find("format[@attr='height-header']")
        assert f_h is not None and f_h.get("value") == "12"
        f_bw = hdr_rule.find("format[@attr='border-width']")
        assert f_bw is not None and f_bw.get("data-class") == "total" and f_bw.get("scope") == "cols" and f_bw.get("value") == "0"
        f_tl = hdr_rule.find("format[@attr='total-label']")
        assert f_tl is not None and f_tl.get("value") == "Last 7 days" and f_tl.get("data-class") == "total"


def test_style_scope_key_sets_scope_attribute_not_attr(ws_editor):
    """`scope` in a style spec selects the target; it must not become attr="scope"."""
    ws_editor.configure_worksheet_style(
        "Chart",
        header_formats=[{"scope": "rows", "band-color": "#d4d4d4"}],
    )
    rule = ws_editor._find_worksheet("Chart").find("table/style/style-rule[@element='header']")
    assert rule is not None
    formats = rule.findall("format")
    assert [f.get("attr") for f in formats] == ["band-color"]
    assert formats[0].get("scope") == "rows"
    assert all(f.get("attr") != "scope" for f in formats)
