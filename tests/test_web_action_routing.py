"""Synthetic public API tests for named Web Page action destinations."""
import asyncio

import pytest
from lxml import etree

from cwtwb import TWBEditor
from cwtwb.validator import validate_against_schema


def portal():
    editor = TWBEditor("")
    editor.add_worksheet("Selector")
    editor.add_dashboard("Portal", layout={"type": "container", "children": [
        {"type": "worksheet", "name": "Selector"},
        {"type": "web", "name": "preview's page", "url": "https://example.org/?a=1&b=2"},
        {"type": "web", "name": "Other", "url": "https://example.net"},
    ]})
    return editor


def test_public_named_routing_saved_and_reopened(tmp_path):
    editor = portal()
    path = tmp_path / "portal.twb"
    editor.save(path)
    editor = TWBEditor(path, clear_existing_content=False)
    editor.add_dashboard_action(
        "Portal", "url", source_sheet="Selector",
        url="<[Link]>&:embed=yes&:showVizHome=no",
        target_web_zone="preview's page",
    )
    editor.save(path)
    root = etree.parse(str(path)).getroot()
    zone = root.xpath(".//zone[@name=$name]", name="preview's page")[0]
    link = root.find("actions/action/link")
    assert link.get("expression") == "<[Link]>&:embed=yes&:showVizHome=no"
    assert link.findtext("url-action-type") == "specific-zone"
    assert link.findtext("url-action-target") == zone.get("id")
    assert link.findtext("url-action-target") != root.find(".//zone[@name='Other']").get("id")
    assert len(root.findall(
        "document-format-change-manifest/SpecificWebTargetsForActions"
    )) == 1
    root.set("version", "26.2")
    result = validate_against_schema(root)
    assert result.schema_available
    assert not result.errors


@pytest.mark.parametrize("kwargs", [
    {"target_web_zone": ""},
    {"target_web_zone": " "},
    {"target_web_zone": 12},
    {"target_web_zone": "missing"},
    {"target_web_zone": "Selector"},
    {"target_web_zone": "Other", "action_type": "filter"},
    {"target_web_zone": "Other", "target_sheet": "Selector"},
])
def test_invalid_target_does_not_mutate(kwargs):
    editor = portal()
    before = etree.tostring(editor.root)
    args = dict(action_type="url", source_sheet="Selector", url="https://example.org")
    args.update(kwargs)
    with pytest.raises(ValueError):
        editor.add_dashboard_action("Portal", **args)
    assert etree.tostring(editor.root) == before


def test_other_dashboard_and_ambiguous_imported_targets_rejected():
    editor = portal()
    editor.add_dashboard("Elsewhere", worksheet_names=["Selector"])
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.add_dashboard_action("Elsewhere", "url", source_sheet="Selector",
                                    url="https://example.org", target_web_zone="Other")
    assert etree.tostring(editor.root) == before
    editor.root.find(".//zone[@name='Other']").set("name", "preview's page")
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.add_dashboard_action("Portal", "url", source_sheet="Selector",
                                    url="https://example.org", target_web_zone="preview's page")
    assert etree.tostring(editor.root) == before


@pytest.mark.parametrize("name", ["", " ", 12, None, "Other"])
def test_bad_layout_names_do_not_replace_dashboard(name):
    editor = portal()
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.add_dashboard("Portal", layout={"type": "container", "children": [
            {"type": "web", "name": "Other", "url": "https://example.org"},
            {"type": "web", "name": name, "url": "https://example.org"},
        ]})
    assert etree.tostring(editor.root) == before


def test_mcp_schema_and_call(monkeypatch):
    from cwtwb.mcp import tools_workbook as tools

    editor = portal()
    monkeypatch.setattr(tools, "get_editor", lambda: editor)
    tools.add_dashboard_action("Portal", "url", source_sheet="Selector",
                               url="https://example.org", target_web_zone="Other")
    link = editor.root.find("actions/action/link")
    assert link.findtext("url-action-type") == "specific-zone"
    registered = asyncio.run(tools.server.list_tools())
    action = next(tool for tool in registered if tool.name == "add_dashboard_action")
    assert "target_web_zone" in action.inputSchema["properties"]


def test_omitted_target_preserves_default_url_behavior():
    editor = portal()
    editor.add_dashboard_action("Portal", "url", source_sheet="Selector", url="https://example.org")
    assert len(editor.root.find("actions/action/link")) == 0
