"""Native Pages shelf regression.

``set_pages_shelf`` binds discrete dimensions to the worksheet's native
``<pages>`` shelf so a view can be stepped through one member at a time (the
interactive equivalent of the author's animated year pager). Synthetic fixture
only; no author data.
"""

from __future__ import annotations

import pytest

from cwtwb import TWBEditor
from cwtwb.validator import validate_against_schema


def _editor() -> TWBEditor:
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Year Dim", "1", datatype="integer", role="dimension", field_type="ordinal"
    )
    editor.add_calculated_field(
        "Region Dim", "2", datatype="integer", role="dimension", field_type="ordinal"
    )
    editor.add_worksheet("Viz")
    editor.configure_chart(
        "Viz", mark_type="Bar", columns=["SUM(Sales)"], rows=["Year Dim"]
    )
    return editor


def test_pages_shelf_writes_qualified_column():
    editor = _editor()
    editor.set_pages_shelf("Viz", ["Year Dim"])

    table = editor._find_worksheet("Viz").find("table")
    pages = table.find("pages")
    assert pages is not None
    instance = editor.field_registry.parse_expression("Year Dim")
    expected = editor.field_registry.resolve_full_reference(instance.instance_name)
    assert [column.text for column in pages.findall("column")] == [expected]


def test_pages_shelf_follows_cols_in_schema_order():
    editor = _editor()
    editor.set_pages_shelf("Viz", ["Year Dim"])

    table = editor._find_worksheet("Viz").find("table")
    children = [child.tag for child in table]
    assert children.index("pages") > children.index("cols")


def test_pages_shelf_is_idempotent():
    editor = _editor()
    for _ in range(2):
        editor.set_pages_shelf("Viz", ["Year Dim"])

    table = editor._find_worksheet("Viz").find("table")
    assert len(table.findall("pages")) == 1


def test_pages_shelf_clears_with_empty_list():
    editor = _editor()
    editor.set_pages_shelf("Viz", ["Year Dim"])
    editor.set_pages_shelf("Viz", [])

    table = editor._find_worksheet("Viz").find("table")
    assert table.find("pages") is None


def test_pages_shelf_rejects_measure_and_continuous_fields():
    editor = _editor()
    with pytest.raises(ValueError, match="Unknown field"):
        editor.set_pages_shelf("Viz", ["SUM(Sales)"])
    with pytest.raises(ValueError, match="Unknown field"):
        editor.set_pages_shelf("Viz", ["Nope"])
    with pytest.raises(ValueError, match="not used"):
        editor.set_pages_shelf("Viz", ["Region Dim"])


def test_pages_shelf_rejects_a_measure_field():
    editor = _editor()
    editor.add_calculated_field(
        "Metric", "1.0", datatype="real", role="measure", field_type="quantitative"
    )
    editor.configure_chart(
        "Viz", mark_type="Bar", columns=["Metric"], rows=["Year Dim"]
    )
    with pytest.raises(ValueError, match="dimension"):
        editor.set_pages_shelf("Viz", ["Metric"])


def test_pages_shelf_rejects_a_continuous_dimension():
    editor = _editor()
    editor.add_calculated_field(
        "Continuous Dim",
        "1.0",
        datatype="real",
        role="dimension",
        field_type="quantitative",
    )
    editor.configure_chart(
        "Viz", mark_type="Bar", columns=["SUM(Sales)"], rows=["Continuous Dim"]
    )
    with pytest.raises(ValueError, match="continuous"):
        editor.set_pages_shelf("Viz", ["Continuous Dim"])


def test_pages_shelf_rejection_leaves_worksheet_unchanged():
    editor = _editor()
    table = editor._find_worksheet("Viz").find("table")
    before = len(table)
    with pytest.raises(ValueError):
        editor.set_pages_shelf("Viz", ["SUM(Sales)"])
    assert len(table) == before
    assert table.find("pages") is None


def test_pages_shelf_adds_no_schema_errors(tmp_path):
    editor = _editor()
    baseline = validate_against_schema(editor.root)
    if not baseline.schema_available:
        pytest.skip("Vendored Tableau schema unavailable")
    editor.set_pages_shelf("Viz", ["Year Dim"])
    assert validate_against_schema(editor.root).errors == baseline.errors
    editor.save(str(tmp_path / "pages.twb"))


def test_pages_shelf_forwards_through_mcp_tool(monkeypatch):
    from cwtwb.mcp import tools_workbook

    editor = _editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    message = tools_workbook.set_pages_shelf("Viz", ["Year Dim"])
    assert "Pages shelf" in message
    assert editor._find_worksheet("Viz").find("table/pages") is not None
