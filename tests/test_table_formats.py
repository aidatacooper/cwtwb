"""Synthetic grouped-band table formatting regressions (2020 WW11)."""
import inspect
import pytest
from cwtwb import TWBEditor
from cwtwb.mcp import tools_workbook

@pytest.fixture
def editor():
    editor = TWBEditor("")
    editor.add_worksheet("Bands")
    return editor

def formats(editor):
    return editor._find_worksheet("Bands").findall("table/style/style-rule[@element='table']/format")

def test_table_formats_upsert_by_attribute_and_scope_preserves_background(editor):
    editor.configure_worksheet_style("Bands", background_color="#f5f5f5", table_formats=[
        {"attr": "band_color", "value": "#eeeeee", "scope": "rows"},
        {"attr": "band-color", "value": "#ffffff", "scope": "cols"},
        {"attr": "band-level", "value": 3, "scope": "rows"},
    ])
    editor.configure_worksheet_style("Bands", table_formats=[
        {"attr": "band-color", "value": "#cccccc", "scope": "rows"},
        {"attr": "band-level", "value": 4, "scope": "rows"},
        {"attr": "band-size", "value": 1},
    ])
    values = {(node.get("attr"), node.get("scope")): node.get("value") for node in formats(editor)}
    assert len(formats(editor)) == len(values) == 5
    assert values == {("background-color", None): "#f5f5f5", ("band-color", "rows"): "#cccccc",
                      ("band-color", "cols"): "#ffffff", ("band-level", "rows"): "4", ("band-size", None): "1"}

@pytest.mark.parametrize("invalid", ["bad", {}, ["bad"], [{}], [{"attr": "band-size"}],
    [{"value": 1}], [{"attr": "band-size", "value": 1, "scope": "columns"}],
    [{"attr": "", "value": 1}], [{"attr": 1, "value": 1}], [{"attr": "band-size", "value": None}],
    [{"attr": "band-size", "value": 1, "unknown": 2}]])
def test_table_formats_reject_invalid_without_mutation(editor, invalid):
    with pytest.raises(ValueError, match="table_formats"):
        editor.configure_worksheet_style("Bands", table_formats=invalid)
    assert formats(editor) == []

def test_table_formats_mcp_signature_and_forwarding(editor, monkeypatch):
    assert inspect.signature(TWBEditor.configure_worksheet_style).parameters["table_formats"].default is None
    assert inspect.signature(tools_workbook.configure_worksheet_style).parameters["table_formats"].default is None
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_worksheet_style("Bands", table_formats=[{"attr": "band-level", "value": 3, "scope": "rows"}])
    assert [(node.get("attr"), node.get("value"), node.get("scope")) for node in formats(editor)] == [("band-level", "3", "rows")]
