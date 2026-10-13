"""Custom geographic roles derived from another field.

Tableau's ``aggregate-role-from`` lets a calculated field inherit the geographic
role of another field (the article's "Region, created from State" custom role).
``set_field_aggregate_role_from`` writes the attribute on the datasource column
and its worksheet dependency copies. Synthetic fixture only; no author data.
"""

from __future__ import annotations

import pytest

from cwtwb import TWBEditor
from cwtwb.validator import validate_against_schema


def _editor() -> TWBEditor:
    editor = TWBEditor("")
    editor.add_calculated_field(
        "State Name",
        "'CA'",
        datatype="string",
        role="dimension",
        field_type="nominal",
    )
    editor.set_field_geographic_role("State Name", "state")
    editor.add_calculated_field(
        "West Region",
        "IF [State Name] = 'CA' THEN [State Name] END",
        datatype="string",
        role="dimension",
        field_type="nominal",
    )
    editor.add_worksheet("Map")
    editor.configure_chart("Map", mark_type="Map", geographic_field="West Region")
    return editor


def _column(editor: TWBEditor, field: str):
    info = editor.field_registry._find_field(field)
    return editor._datasource.find(f"column[@name='{info.local_name}']")


def test_aggregate_role_from_writes_source_local_name():
    editor = _editor()
    editor.set_field_aggregate_role_from("West Region", "State Name")

    source = editor.field_registry._find_field("State Name").local_name
    assert _column(editor, "West Region").get("aggregate-role-from") == source


def test_aggregate_role_from_updates_worksheet_dependencies():
    editor = _editor()
    editor.set_field_aggregate_role_from("West Region", "State Name")

    info = editor.field_registry._find_field("West Region")
    dependencies = editor._find_worksheet("Map").find(
        ".//datasource-dependencies"
    )
    dependency_column = dependencies.find(f"column[@name='{info.local_name}']")
    assert dependency_column is not None
    assert (
        dependency_column.get("aggregate-role-from")
        == editor.field_registry._find_field("State Name").local_name
    )


def test_aggregate_role_from_clears_with_empty_source():
    editor = _editor()
    editor.set_field_aggregate_role_from("West Region", "State Name")
    editor.set_field_aggregate_role_from("West Region", "")

    assert _column(editor, "West Region").get("aggregate-role-from") is None


def test_aggregate_role_from_requires_a_geographic_source():
    editor = _editor()
    editor.add_calculated_field(
        "Plain", "'x'", datatype="string", role="dimension", field_type="nominal"
    )
    with pytest.raises(ValueError, match="geographic role"):
        editor.set_field_aggregate_role_from("West Region", "Plain")


def test_aggregate_role_from_rejects_unknown_fields():
    editor = _editor()
    with pytest.raises(KeyError):
        editor.set_field_aggregate_role_from("Nope", "State Name")
    with pytest.raises(KeyError):
        editor.set_field_aggregate_role_from("West Region", "Nope")


def test_aggregate_role_from_is_idempotent_and_schema_valid(tmp_path):
    editor = _editor()
    baseline = validate_against_schema(editor.root)
    for _ in range(2):
        editor.set_field_aggregate_role_from("West Region", "State Name")

    assert len(editor._datasource.findall(
        "column[@aggregate-role-from]"
    )) == 1
    if baseline.schema_available:
        assert validate_against_schema(editor.root).errors == baseline.errors
    editor.save(str(tmp_path / "custom-role.twb"))


def test_aggregate_role_from_forwards_through_mcp_tool(monkeypatch):
    from cwtwb.mcp import tools_workbook

    editor = _editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    message = tools_workbook.set_field_aggregate_role_from("West Region", "State Name")
    assert "West Region" in message
    assert _column(editor, "West Region").get("aggregate-role-from") is not None
