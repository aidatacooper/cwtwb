"""Tests for supported dashboard action types."""

from __future__ import annotations

from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def action_editor():
    template = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"
    editor = TWBEditor(template)
    editor.add_worksheet("Source")
    editor.configure_chart("Source", mark_type="Bar", rows=["Category"], columns=["SUM(Sales)"])
    editor.add_worksheet("Target")
    editor.configure_chart("Target", mark_type="Bar", rows=["Region"], columns=["SUM(Profit)"])
    editor.add_worksheet("Detail")
    editor.configure_chart("Detail", mark_type="Line", columns=["MONTH(Order Date)"], rows=["SUM(Sales)"])
    editor.add_dashboard("TestDash", worksheet_names=["Source", "Target", "Detail"])
    return editor


class TestHighlightAction:
    def test_highlight_action_uses_brush_command(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )

        cmd = action_editor.root.find(".//actions/action/command")
        assert cmd is not None
        assert cmd.get("command") == "tsc:brush"

    def test_highlight_action_with_empty_fields_sets_special_fields(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=[],
        )

        cmd = action_editor.root.find(".//actions/action/command")
        special = next(
            (param for param in cmd.findall("param") if param.get("name") == "special-fields"),
            None,
        )
        assert special is not None
        assert special.get("value") == "all"


class TestUrlAction:
    def test_url_action_creates_link_without_command(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="url",
            source_sheet="Source",
            url="https://example.com/detail",
            caption="Open Detail",
        )

        action_el = action_editor.root.find(".//actions/action")
        assert action_el is not None
        assert action_el.find("command") is None
        link = action_el.find("link")
        assert link is not None
        assert link.get("expression") == "https://example.com/detail"
        assert link.get("caption") == "Open Detail"

    def test_url_action_requires_url(self, action_editor):
        with pytest.raises(ValueError, match="requires a non-empty url"):
            action_editor.add_dashboard_action(
                dashboard_name="TestDash",
                action_type="url",
                source_sheet="Source",
            )


class TestGoToSheetAction:
    def test_go_to_sheet_action_uses_navigation_command(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="go-to-sheet",
            source_sheet="Source",
            target_sheet="Detail",
            caption="Open Detail Sheet",
        )

        action_el = action_editor.root.find(".//actions/action")
        assert action_el is not None
        cmd = action_el.find("command")
        assert cmd is not None
        assert cmd.get("command") == "tabdoc:goto-sheet"

        target = next(
            (param for param in cmd.findall("param") if param.get("name") == "target"),
            None,
        )
        assert target is not None
        assert target.get("value") == "Detail"

    def test_go_to_sheet_action_requires_target_sheet(self, action_editor):
        with pytest.raises(ValueError, match="requires a non-empty target_sheet"):
            action_editor.add_dashboard_action(
                dashboard_name="TestDash",
                action_type="go-to-sheet",
                source_sheet="Source",
            )


class TestActionValidation:
    def test_unknown_dashboard_raises(self, action_editor):
        with pytest.raises(ValueError, match="not found"):
            action_editor.add_dashboard_action(
                dashboard_name="MissingDash",
                action_type="filter",
                source_sheet="Source",
                target_sheet="Target",
                fields=["Category"],
            )

    def test_unsupported_action_type_raises(self, action_editor):
        with pytest.raises(ValueError, match="Unsupported action_type"):
            action_editor.add_dashboard_action(
                dashboard_name="TestDash",
                action_type="drill-anywhere",
                source_sheet="Source",
                target_sheet="Target",
            )

    def test_custom_caption_and_event_type_are_preserved(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="filter",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
            caption="Filter Details",
            event_type="on-hover",
        )

        action_el = action_editor.root.find(".//actions/action")
        assert action_el is not None
        assert action_el.get("caption") == "Filter Details"
        activation = action_el.find("activation")
        assert activation is not None
        assert activation.get("type") == "on-hover"


class TestMultipleActions:
    def test_filter_highlight_url_and_go_to_sheet_can_coexist(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="filter",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Category"],
        )
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="highlight",
            source_sheet="Source",
            target_sheet="Target",
            fields=["Region"],
        )
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="url",
            source_sheet="Target",
            url="https://example.com/detail",
        )
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="go-to-sheet",
            source_sheet="Source",
            target_sheet="Detail",
        )

        actions = action_editor.root.findall(".//actions/action")
        assert len(actions) == 4
        commands = [
            action.find("command").get("command")
            for action in actions
            if action.find("command") is not None
        ]
        assert "tsc:tsl-filter" in commands
        assert "tsc:brush" in commands
        assert "tabdoc:goto-sheet" in commands
