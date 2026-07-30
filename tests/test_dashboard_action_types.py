"""Tests for supported dashboard action types."""

from __future__ import annotations

from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def action_editor():
    template = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"
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
    def test_go_to_sheet_action_uses_native_nav_action(self, action_editor):
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="go-to-sheet",
            source_sheet="Source",
            target_sheet="Detail",
            caption="Open Detail Sheet",
        )

        action_el = action_editor.root.find(".//actions/nav-action")
        assert action_el is not None
        source = action_el.find("source")
        assert source is not None
        assert source.get("dashboard") == "TestDash"
        assert source.get("worksheet") == "Source"

        target = next(
            (
                param
                for param in action_el.findall("params/param")
                if param.get("name") == "sheet"
            ),
            None,
        )
        assert target is not None
        assert target.get("value") == "Detail"

    def test_go_to_sheet_action_accepts_dashboard_target(self, action_editor):
        action_editor.add_dashboard(
            "Detail Dashboard",
            layout={
                "type": "worksheet",
                "name": "Detail",
            },
            worksheet_names=["Detail"],
        )
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="go-to-sheet",
            source_sheet="Source",
            target_sheet="Detail Dashboard",
        )

        target = action_editor.root.find(
            ".//actions/nav-action/params/param[@name='sheet']"
        )
        assert target is not None
        assert target.get("value") == "Detail Dashboard"

    def test_go_to_sheet_action_requires_target_sheet(self, action_editor):
        with pytest.raises(ValueError, match="requires a non-empty target_sheet"):
            action_editor.add_dashboard_action(
                dashboard_name="TestDash",
                action_type="go-to-sheet",
                source_sheet="Source",
            )


class TestParameterAction:
    def test_parameter_action_matches_tableau_native_structure(self, action_editor):
        action_editor.add_parameter(
            name="Selected Category",
            datatype="string",
            default_value="All",
            domain_type="list",
            allowed_values=["All", "Furniture"],
        )

        result = action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="parameter",
            source_sheet="Source",
            source_field="Category",
            target_parameter="Selected Category",
            caption="Set Selected Category",
            aggregation="attr",
            clear_behavior="keep-current",
            clear_value="s:LROOT:All",
        )

        assert "Added parameter action" in result
        action = action_editor.root.find(".//actions/edit-parameter-action")
        assert action is not None
        assert action.get("caption") == "Set Selected Category"
        manifest = action_editor.root.find("document-format-change-manifest")
        assert manifest.find("ParameterAction") is not None
        assert manifest.find("ParameterActionClearSelection") is not None
        assert action.find("activation").attrib == {"type": "on-select"}
        assert action.find("agg-type").attrib == {"type": "attr"}
        assert action.find("clear-option").attrib == {
            "type": "do-nothing",
            "value": "s:LROOT:All",
        }
        params = {
            param.get("name"): param.get("value")
            for param in action.findall("./params/param")
        }
        assert params["source-field"].endswith(".[none:Category (Orders):nk]")
        assert params["target-parameter"].startswith("[Parameters].[Parameter ")

    def test_parameter_action_supports_fixed_clear_value(self, action_editor):
        action_editor.add_parameter(
            name="Minimum Date",
            datatype="date",
            default_value="2026-02-12",
            domain_type="range",
        )
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="parameter",
            source_sheet="Detail",
            source_field="MIN(Order Date)",
            target_parameter="Minimum Date",
            aggregation="min",
            clear_behavior="set-value",
            clear_value="d:2026-02-12",
        )

        action = action_editor.root.find(".//actions/edit-parameter-action")
        assert action.find("agg-type").get("type") == "min"
        assert action.find("clear-option").attrib == {
            "type": "assign-fixed-value",
            "value": "d:2026-02-12",
        }

    @pytest.mark.parametrize(
        ("kwargs", "message"),
        [
            ({"source_field": ""}, "source_field"),
            ({"target_parameter": "Missing"}, "not found"),
            ({"aggregation": "median"}, "aggregation"),
            ({"clear_behavior": "reset"}, "clear_behavior"),
            ({"clear_value": ""}, "clear_value"),
        ],
    )
    def test_parameter_action_validates_required_semantics(
        self, action_editor, kwargs, message
    ):
        action_editor.add_parameter(
            name="Selected Category",
            datatype="string",
            default_value="All",
            domain_type="list",
            allowed_values=["All"],
        )
        arguments = {
            "dashboard_name": "TestDash",
            "action_type": "parameter",
            "source_sheet": "Source",
            "source_field": "Category",
            "target_parameter": "Selected Category",
            "clear_value": "s:LROOT:All",
            **kwargs,
        }
        with pytest.raises(ValueError, match=message):
            action_editor.add_dashboard_action(**arguments)


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
    def test_all_action_types_can_coexist(self, action_editor):
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
        action_editor.add_parameter(
            name="Selected Category",
            datatype="string",
            default_value="All",
            domain_type="list",
            allowed_values=["All"],
        )
        action_editor.add_dashboard_action(
            dashboard_name="TestDash",
            action_type="parameter",
            source_sheet="Source",
            source_field="Category",
            target_parameter="Selected Category",
            clear_value="s:LROOT:All",
        )

        actions = action_editor.root.findall(".//actions/action")
        assert len(actions) == 3
        assert len(action_editor.root.findall(".//actions/nav-action")) == 1
        assert len(action_editor.root.findall(".//actions/edit-parameter-action")) == 1
        commands = [
            action.find("command").get("command")
            for action in actions
            if action.find("command") is not None
        ]
        assert "tsc:tsl-filter" in commands
        assert "tsc:brush" in commands
