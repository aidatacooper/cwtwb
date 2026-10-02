"""Synthetic source and target scope contracts for dashboard actions."""
import pytest
from lxml import etree
from cwtwb import TWBEditor


def fixture():
    editor = TWBEditor("")
    for name in ["Year", "A", "B", "Map"]:
        editor.add_worksheet(name)
        editor.configure_chart(name, "Text", label="SUM(Sales)")
    editor.add_dashboard("Overview", layout={"type": "container", "direction": "horizontal", "children": [
        {"type": "worksheet", "name": name} for name in ["Year", "A", "B", "Map"]]})
    return editor


def test_multi_sheet_highlight_excludes_unselected_sources_and_targets():
    editor = fixture()
    editor.add_dashboard_action("Overview", action_type="highlight", source_sheets=["A", "B"],
                                target_sheets=["A", "B"], event_type="on-hover")
    action = editor.root.find("actions/action")
    assert action.find("source").get("worksheet") is None
    assert {node.get("name") for node in action.findall("source/exclude-sheet")} == {"Year", "Map"}
    assert action.find("activation").get("type") == "on-hover"
    assert "Year" in etree.tostring(action.find("command"), encoding="unicode")
    assert "Map" in etree.tostring(action.find("command"), encoding="unicode")


def test_filter_action_can_target_all_sheets():
    editor = fixture()
    editor.add_dashboard_action("Overview", action_type="filter", source_sheet="Year",
                                target_sheets=["Year", "A", "B", "Map"])
    action = editor.root.find("actions/action")
    assert action.find("source").get("worksheet") == "Year"
    assert not action.findall("command/exclude-sheet")


@pytest.mark.parametrize("sources", [[], ["A", "A"], ["Missing"]])
def test_invalid_scope_does_not_add_action(sources):
    editor = fixture()
    before = etree.tostring(editor.root.find("actions")) if editor.root.find("actions") is not None else None
    with pytest.raises(ValueError):
        editor.add_dashboard_action("Overview", action_type="highlight", source_sheets=sources, target_sheets=["A"])
    after = etree.tostring(editor.root.find("actions")) if editor.root.find("actions") is not None else None
    assert before == after
