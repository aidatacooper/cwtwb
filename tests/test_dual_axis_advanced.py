"""Tests for advanced configure_dual_axis options.

Covers mark_color_1/2, color_map_1, reverse_axis_1, hide_zeroline,
synchronized axis, and their XML representations.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def da_editor():
    template = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"
    ed = TWBEditor(template)
    ed.add_worksheet("Combo")
    return ed


def _pane_mark_color(editor: TWBEditor, ws_name: str, pane_id: int) -> str | None:
    ws = editor._find_worksheet(ws_name)
    pane = ws.find(f".//pane[@id='{pane_id}']")
    if pane is None:
        return None
    rule = pane.find("./style/style-rule[@element='mark']")
    if rule is None:
        return None
    for fmt in rule.findall("format"):
        if fmt.get("attr") == "mark-color":
            return fmt.get("value")
    return None


# ── mark_color_1 and mark_color_2 ────────────────────────────────────────────

class TestMarkColors:
    def test_mark_color_2_sets_pane2_color(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Line",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Profit)"],
            dual_axis_shelf="rows",
            mark_color_2="#4e79a7",
        )
        color = _pane_mark_color(da_editor, "Combo", 2)
        assert color == "#4e79a7"

    def test_mark_color_1_sets_pane1_color(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="GanttBar",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Sales)"],
            dual_axis_shelf="rows",
            mark_color_1="#adb1c5",
        )
        color = _pane_mark_color(da_editor, "Combo", 1)
        assert color == "#adb1c5"

    def test_both_mark_colors(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="GanttBar",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Sales)"],
            dual_axis_shelf="rows",
            mark_color_1="#adb1c5",
            mark_color_2="#4e79a7",
        )
        assert _pane_mark_color(da_editor, "Combo", 1) == "#adb1c5"
        assert _pane_mark_color(da_editor, "Combo", 2) == "#4e79a7"

    def test_no_mark_color_when_omitted(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Line",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Profit)"],
            dual_axis_shelf="rows",
        )
        # No explicit mark-color should be set for either pane
        assert _pane_mark_color(da_editor, "Combo", 1) is None
        assert _pane_mark_color(da_editor, "Combo", 2) is None


# ── color_map_1 (palette) ─────────────────────────────────────────────────────

class TestColorMap1:
    def test_color_map_1_writes_datasource_encoding(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="GanttBar",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Sales)"],
            dual_axis_shelf="rows",
            color_1="Target Reached",
            color_map_1={"⬤": "#b2e1c1", " ": "#adb1c5"},
        )
        ds = da_editor._datasource
        encoding = ds.find(".//encoding[@attr='color']")
        assert encoding is not None
        buckets = encoding.findall("bucket")
        bucket_values = [b.get("color") for b in buckets]
        assert "#b2e1c1" in bucket_values
        assert "#adb1c5" in bucket_values


# ── reverse_axis_1 (butterfly chart) ─────────────────────────────────────────

class TestReverseAxis:
    def test_reverse_axis_1_sets_encoding(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Bar",
            columns=["SUM(Sales)", "SUM(Profit)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            reverse_axis_1=True,
        )
        ws = da_editor._find_worksheet("Combo")
        axis_rule = ws.find("./table/style/style-rule[@element='axis']")
        assert axis_rule is not None
        # Must have an encoding with reverse=true for class=0
        reverse_enc = axis_rule.find("./encoding[@reverse='true'][@class='0']")
        assert reverse_enc is not None

    def test_reverse_axis_not_set_by_default(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Line",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Profit)"],
            dual_axis_shelf="rows",
        )
        ws = da_editor._find_worksheet("Combo")
        axis_rule = ws.find("./table/style/style-rule[@element='axis']")
        if axis_rule is not None:
            assert axis_rule.find("./encoding[@reverse='true']") is None


# ── hide_zeroline ─────────────────────────────────────────────────────────────

class TestHideZeroline:
    def test_hide_zeroline_adds_style_rule(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Line",
            columns=["MONTH(Order Date)"],
            rows=["SUM(Sales)", "SUM(Profit)"],
            dual_axis_shelf="rows",
            hide_zeroline=True,
        )
        ws = da_editor._find_worksheet("Combo")
        zeroline = ws.find("./table/style/style-rule[@element='zeroline']")
        assert zeroline is not None
        fmts = {f.get("attr"): f.get("value") for f in zeroline.findall("format")}
        assert fmts.get("line-visibility") == "off"
        assert fmts.get("stroke-size") == "0"


# ── synchronized axis ─────────────────────────────────────────────────────────

class TestSynchronized:
    def test_synchronized_axis_encoding(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Circle",
            columns=["SUM(Sales)", "SUM(Sales)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            synchronized=True,
        )
        ws = da_editor._find_worksheet("Combo")
        axis_rule = ws.find("./table/style/style-rule[@element='axis']")
        assert axis_rule is not None
        sync_enc = axis_rule.find("./encoding[@synchronized='true']")
        assert sync_enc is not None

    def test_unsynchronized_has_no_sync_encoding(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Bar",
            columns=["SUM(Sales)", "SUM(Profit)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            synchronized=False,
        )
        ws = da_editor._find_worksheet("Combo")
        axis_rule = ws.find("./table/style/style-rule[@element='axis']")
        if axis_rule is not None:
            assert axis_rule.find("./encoding[@synchronized='true']") is None


# ── show_labels / mark_sizing_off ─────────────────────────────────────────────

class TestLabelAndSizing:
    def test_show_labels_false_sets_mark_labels_show(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Circle",
            columns=["SUM(Sales)", "SUM(Sales)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            show_labels=False,
        )
        ws = da_editor._find_worksheet("Combo")
        for pane_id in (1, 2):
            pane = ws.find(f".//pane[@id='{pane_id}']")
            if pane is None:
                continue
            rule = pane.find("./style/style-rule[@element='mark']")
            if rule is None:
                continue
            labels_show = next(
                (f.get("value") for f in rule.findall("format") if f.get("attr") == "mark-labels-show"),
                None,
            )
            assert labels_show == "false", f"pane {pane_id} should have mark-labels-show=false"

    def test_size_values_propagate_to_panes(self, da_editor):
        da_editor.configure_dual_axis(
            "Combo",
            mark_type_1="Bar",
            mark_type_2="Circle",
            columns=["SUM(Sales)", "SUM(Sales)"],
            rows=["Category"],
            dual_axis_shelf="columns",
            mark_sizing_off=True,
            size_value_1="0.15",
            size_value_2="3.5",
        )
        ws = da_editor._find_worksheet("Combo")

        def get_size(pane_id):
            pane = ws.find(f".//pane[@id='{pane_id}']")
            if pane is None:
                return None
            rule = pane.find("./style/style-rule[@element='mark']")
            if rule is None:
                return None
            return next(
                (f.get("value") for f in rule.findall("format") if f.get("attr") == "size"),
                None,
            )

        s1, s2 = get_size(1), get_size(2)
        assert s1 is not None and s2 is not None
        assert float(s1) < float(s2)
