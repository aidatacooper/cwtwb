"""Public tool forwarding for independent source and layout authoring."""

from unittest.mock import Mock

import pytest

from cwtwb.capability_registry import get_capability
from cwtwb.mcp import tools_workbook


@pytest.mark.parametrize(
    "name,args",
    [
        ("import_blended_field", ("Plan", "Targets", "SUM(Target)")),
        (
            "configure_datasource_blend",
            ("Viz", "Targets", {"Month": "Month"}, ["SUM(Target)"]),
        ),
        ("add_combined_set", ("Both", ["Top", "Bottom"])),
        ("enable_automatic_phone_layout", ("Dashboard", 300)),
    ],
)
def test_public_tool_forwards_arguments(monkeypatch, name, args):
    editor = Mock()
    getattr(editor, name).return_value = "configured"
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    assert getattr(tools_workbook, name)(*args) == "configured"
    getattr(editor, name).assert_called_once_with(*args)


def test_new_capabilities_are_declared():
    for kind, name in [
        ("connection", "configure_datasource_blend"),
        ("connection", "import_blended_field"),
        ("feature", "add_combined_set"),
        ("dashboard_zone", "enable_automatic_phone_layout"),
    ]:
        assert get_capability(kind, name).level == "advanced"
