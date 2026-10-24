"""Public tool forwarding for independent source and layout authoring."""

from unittest.mock import Mock

import pytest

from cwtwb.capability_registry import get_capability, list_capabilities
from cwtwb.mcp import tools_workbook


@pytest.mark.parametrize(
    "name,args",
    [
        ("import_blended_field", ("Plan", "Targets", "SUM(Target)")),
        (
            "configure_datasource_blend",
            ("Viz", "Targets", {"Month": "Month"}, ["SUM(Target)"]),
        ),
        ("enable_automatic_phone_layout", ("Dashboard", 300)),
    ],
)
def test_public_tool_forwards_arguments(monkeypatch, name, args):
    editor = Mock()
    getattr(editor, name).return_value = "configured"
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    assert getattr(tools_workbook, name)(*args) == "configured"
    getattr(editor, name).assert_called_once_with(*args)


def test_combined_set_tool_forwards_default_operator(monkeypatch):
    editor = Mock()
    editor.add_combined_set.return_value = "configured"
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)

    assert tools_workbook.add_combined_set("Both", ["Top", "Bottom"]) == "configured"
    editor.add_combined_set.assert_called_once_with(
        "Both", ["Top", "Bottom"], operator="union"
    )


def test_combined_set_tool_forwards_intersection(monkeypatch):
    editor = Mock()
    editor.add_combined_set.return_value = "configured"
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)

    assert (
        tools_workbook.add_combined_set(
            "Both", ["Top", "Selected"], operator="intersection"
        )
        == "configured"
    )
    editor.add_combined_set.assert_called_once_with(
        "Both", ["Top", "Selected"], operator="intersection"
    )


def test_new_capabilities_are_declared():
    for kind, name in [
        ("connection", "configure_datasource_blend"),
        ("connection", "import_blended_field"),
        ("feature", "add_combined_set"),
        ("dashboard_zone", "enable_automatic_phone_layout"),
    ]:
        assert get_capability(kind, name).level == "advanced"

    keys = {spec.key for spec in list_capabilities(level="advanced")}
    assert {
        "dynamic-set-intersection",
        "discrete-aggregate-pill",
        "source-field-metadata-overrides",
    } <= keys
