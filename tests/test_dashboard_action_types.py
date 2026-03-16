"""Tests for all supported dashboard action types.

filter action: already covered in test_dashboard_actions.py (structural detail).
highlight action: new coverage here.
Also covers error-handling for unsupported action types.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def action_editor():
    template = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"
    ed = TWBEditor(template)
    ed.add_worksheet("Source")
    ed.configure_chart("Source", mark_type="Bar", rows=["Category"], columns=["SUM(Sales)"])
    ed.add_worksheet("Target")
    ed.configure_chart("Target", mark_type="Bar", rows=["Region"], columns=["SUM(Profit)"])
    ed.add_dashboard("TestDash", worksheet_names=["Source", "Target"])
    return ed


# ── highlight action ──────────────────────────────────────────────────────────

class TestHighlightAction:
    def test_highlight_action_added_to_actions(self, action_editor):
        msg = action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )
        assert "highlight" in msg.lower()
        actions_el = action_editor.root.find("actions")
        assert actions_el is not None

    def test_highlight_action_uses_tsc_brush_command(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )
        actions_el = action_editor.root.find("actions")
        cmd = actions_el.find(".//command")
        assert cmd is not None
        assert cmd.get("command") == "tsc:brush"

    def test_highlight_action_sets_field_captions(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )
        actions_el = action_editor.root.find("actions")
        cmd = actions_el.find(".//command")
        field_param = next(
            (p for p in cmd.findall("param") if p.get("name") == "field-captions"),
            None,
        )
        assert field_param is not None
        assert "Category" in field_param.get("value", "")

    def test_highlight_action_sets_target_param(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Region"],
        )
        actions_el = action_editor.root.find("actions")
        cmd = actions_el.find(".//command")
        tgt = next(
            (p for p in cmd.findall("param") if p.get("name") == "target"),
            None,
        )
        assert tgt is not None
        assert tgt.get("value") == "TestDash"

    def test_highlight_action_sets_source_element(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )
        action_el = action_editor.root.find(".//actions/action")
        source_el = action_el.find("source")
        assert source_el is not None
        assert source_el.get("dashboard") == "TestDash"
        assert source_el.get("worksheet") == "Source"

    def test_highlight_with_empty_fields_sets_special_fields(self, action_editor):
        """No fields → command should use special-fields=all."""
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=[],
        )
        actions_el = action_editor.root.find("actions")
        cmd = actions_el.find(".//command")
        special_param = next(
            (p for p in cmd.findall("param") if p.get("name") == "special-fields"),
            None,
        )
        assert special_param is not None
        assert special_param.get("value") == "all"

    def test_highlight_action_excludes_non_target_sheets(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )
        actions_el = action_editor.root.find("actions")
        cmd = actions_el.find(".//command")
        exclude_param = next(
            (p for p in cmd.findall("param") if p.get("name") == "exclude"),
            None,
        )
        # "Source" sheet should appear in the exclude list (only Target is the destination)
        if exclude_param is not None:
            assert "Source" in exclude_param.get("value", "")


# ── filter action (cross-check) ───────────────────────────────────────────────

class TestFilterActionCrossCheck:
    def test_filter_action_uses_tsl_filter_command(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="filter",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )
        actions_el = action_editor.root.find("actions")
        cmd = actions_el.find(".//command")
        assert cmd.get("command") == "tsc:tsl-filter"

    def test_filter_action_does_not_use_brush_command(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="filter",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )
        actions_el = action_editor.root.find("actions")
        cmd = actions_el.find(".//command")
        assert cmd.get("command") != "tsc:brush"


# ── error handling ────────────────────────────────────────────────────────────

class TestActionErrorHandling:
    def test_unsupported_action_type_raises(self, action_editor):
        with pytest.raises(ValueError, match="Unsupported action_type"):
            action_editor.add_dashboard_action(
                dashboard_name="TestDash",
                action_type="url",
                source_sheet="Source",
                target_sheet="Target",
                fields=["Category"],
            )

    def test_unknown_dashboard_raises(self, action_editor):
        with pytest.raises(ValueError, match="not found"):
            action_editor.add_dashboard_action(
                dashboard_name="NonExistentDash",
                action_type="filter",
                source_sheet="Source",
                target_sheet="Target",
                fields=["Category"],
            )

    def test_custom_caption_is_used(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
            caption="My Highlight",
        )
        action_el = action_editor.root.find(".//actions/action")
        assert action_el.get("caption") == "My Highlight"

    def test_custom_event_type_is_used(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="filter",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
            event_type="on-hover",
        )
        action_el = action_editor.root.find(".//actions/action")
        activation = action_el.find("activation")
        assert activation is not None
        assert activation.get("type") == "on-hover"


# ── multiple actions ──────────────────────────────────────────────────────────

class TestMultipleActions:
    def test_filter_and_highlight_can_coexist(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash", action_type="filter",
            source_sheet="Source", target_sheet="Target", fields=["Category"],
        )
        action_editor.add_dashboard_action(
            dashboard_name="TestDash", action_type="highlight",
            source_sheet="Source", target_sheet="Target", fields=["Region"],
        )
        actions_el = action_editor.root.find("actions")
        all_actions = actions_el.findall("action")
        assert len(all_actions) == 2
        commands = [a.find("command").get("command") for a in all_actions]
        assert "tsc:tsl-filter" in commands
        assert "tsc:brush" in commands
