"""Tests for label_runs (rich-text customized-label) feature.

Covers text runs, field runs, newline separator, font styling,
fontalignment suppression, and combined title patterns.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def lr_editor():
    template = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"
    ed = TWBEditor(template)
    ed.add_worksheet("LRSheet")
    return ed


def _get_customized_label(editor: TWBEditor, ws_name: str):
    ws = editor._find_worksheet(ws_name)
    pane = ws.find(".//pane")
    assert pane is not None, "No pane found"
    cl = pane.find("customized-label")
    return cl


def _runs(cl) -> list:
    """Return all <run> elements inside the customized-label."""
    ft = cl.find("formatted-text")
    assert ft is not None
    return ft.findall("run")


# ── text-only runs ────────────────────────────────────────────────────────────

class TestTextRuns:
    def test_literal_text_run(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[{"text": "Hello World", "fontsize": 14}],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        assert cl is not None
        runs = _runs(cl)
        assert len(runs) == 1
        assert runs[0].text == "Hello World"
        assert runs[0].get("fontsize") == "14"

    def test_newline_run_produces_tableau_paragraph_separator(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[
                {"text": "Line 1"},
                {"text": "\n"},
                {"text": "Line 2"},
            ],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        assert len(runs) == 3
        # Middle run must contain the Tableau paragraph separator (U+00C6 + newline)
        sep_text = runs[1].text or ""
        assert "\u00c6" in sep_text

    def test_multiple_text_runs_with_fonts(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[
                {"text": "Sales", "fontname": "Tableau Regular", "fontsize": 10},
                {"text": "\n"},
                {"text": "Value", "fontname": "Tableau Bold", "fontsize": 14, "bold": True},
            ],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        assert runs[0].get("fontname") == "Tableau Regular"
        assert runs[0].get("fontsize") == "10"
        assert runs[2].get("fontname") == "Tableau Bold"
        assert runs[2].get("bold") == "true"


# ── field-reference runs ──────────────────────────────────────────────────────

class TestFieldRuns:
    def test_field_run_produces_cdata(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[{"field": "SUM(Sales)", "fontsize": 12}],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        assert len(runs) == 1
        # Content must be a CDATA containing a <field_ref> style token
        run_text = runs[0].text or ""
        assert "<" in run_text and ">" in run_text
        assert "Sales" in run_text

    def test_field_run_with_prefix(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[{"field": "SUM(Sales)", "prefix": " "}],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        run_text = runs[0].text or ""
        # Prefix should precede the field ref
        assert run_text.startswith(" ")

    def test_field_run_with_fontcolor(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[{"field": "SUM(Sales)", "fontcolor": "#5a6dff"}],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        assert runs[0].get("fontcolor") == "#5a6dff"


# ── fontalignment ─────────────────────────────────────────────────────────────

class TestFontalignment:
    def test_default_fontalignment_is_2(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[{"text": "Test"}],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        assert runs[0].get("fontalignment") == "2"

    def test_fontalignment_suppressed_when_none(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[{"text": "Test", "fontalignment": None}],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        # fontalignment attribute must not be present when explicitly set to None
        assert runs[0].get("fontalignment") is None

    def test_custom_fontalignment(self, lr_editor):
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[{"text": "Test", "fontalignment": "3"}],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        assert runs[0].get("fontalignment") == "3"


# ── combined / real-world patterns ────────────────────────────────────────────

class TestRealWorldPatterns:
    def test_kpi_card_sales_value(self, lr_editor):
        """Pattern from MEMORY.md: 'Sales\n$value' KPI card."""
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[
                {"text": "Sales", "fontname": "Tableau Regular", "fontsize": 10, "fontalignment": "2"},
                {"text": "\n"},
                {"field": "SUM(Sales)", "fontname": "Tableau Bold", "fontsize": 12,
                 "fontcolor": "#555555", "bold": True, "fontalignment": "2"},
            ],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        assert len(runs) == 3
        assert runs[0].text == "Sales"
        assert "\u00c6" in (runs[1].text or "")
        assert runs[2].get("fontcolor") == "#555555"
        assert runs[2].get("bold") == "true"

    def test_dynamic_title_with_pipe_separator(self, lr_editor):
        """Pattern from MEMORY.md: 'TITLE | <value>' executive title."""
        lr_editor.configure_chart(
            "LRSheet",
            mark_type="Text",
            label="SUM(Sales)",
            label_runs=[
                {"text": "EXECUTIVE OVERVIEW ", "fontname": "Tableau Medium", "fontsize": 22},
                {"text": "|", "fontname": "Tableau Medium", "fontsize": 22, "bold": True, "fontcolor": "#5a6dff"},
                {"field": "SUM(Sales)", "fontname": "Tableau Medium", "fontsize": 22, "prefix": " "},
            ],
        )
        cl = _get_customized_label(lr_editor, "LRSheet")
        runs = _runs(cl)
        assert len(runs) == 3
        assert runs[1].text == "|"
        assert runs[1].get("fontcolor") == "#5a6dff"
        field_text = runs[2].text or ""
        assert field_text.startswith(" ")

    def test_label_runs_replaces_existing_customized_label(self, lr_editor):
        """Calling configure_chart twice should replace the customized-label."""
        lr_editor.configure_chart(
            "LRSheet", mark_type="Text", label="SUM(Sales)",
            label_runs=[{"text": "First"}],
        )
        lr_editor.configure_chart(
            "LRSheet", mark_type="Text", label="SUM(Sales)",
            label_runs=[{"text": "Second"}],
        )
        ws = lr_editor._find_worksheet("LRSheet")
        pane = ws.find(".//pane")
        cls = pane.findall("customized-label")
        assert len(cls) == 1, "Should replace, not duplicate"
        runs = _runs(cls[0])
        assert runs[0].text == "Second"
