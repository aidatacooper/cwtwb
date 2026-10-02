"""Public sorting contracts for outer ordinal and inner nominal dimensions."""
import pytest
from cwtwb import TWBEditor
from cwtwb.mcp import tools_workbook


def synthetic():
    editor = TWBEditor("")
    editor.add_calculated_field("Cohort", "1", datatype="integer", role="dimension", field_type="ordinal")
    editor.add_calculated_field("Label", "'A'", datatype="string", role="dimension", field_type="nominal")
    editor.add_calculated_field("Value", "1.0", datatype="real")
    editor.add_worksheet("Synthetic")
    return editor


@pytest.mark.parametrize("kind", ["basic", "text", "dual"])
def test_explicit_outer_ordinal_sort_and_default_inner_sort_through_public_mcp(kind, monkeypatch):
    editor = synthetic()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)

    def configure(sort_field=None):
        options = {"rows": ["Cohort", "Label"], "sort_descending": "SUM(Value)", "sort_field": sort_field}
        if kind == "dual":
            tools_workbook.configure_dual_axis("Synthetic", columns=["SUM(Value)", "SUM(Value)"], dual_axis_shelf="columns", **options)
        else:
            tools_workbook.configure_chart("Synthetic", mark_type="Text" if kind == "text" else "Bar", columns=[] if kind == "text" else ["SUM(Value)"], label="SUM(Value)" if kind == "text" else None, **options)

    configure("Cohort")
    sort = editor.root.find(".//shelf-sort-v2")
    assert sort.get("dimension-to-sort").endswith("." + editor.field_registry.parse_expression("Cohort").instance_name)
    assert sort.get("is-on-innermost-dimension") == "false"
    assert sort.get("direction") == "DESC"
    configure()
    sort = editor.root.find(".//shelf-sort-v2")
    assert sort.get("dimension-to-sort").endswith("." + editor.field_registry.parse_expression("Label").instance_name)
    assert sort.get("is-on-innermost-dimension") == "true"
    with pytest.raises(ValueError, match="dimension on the row shelf"):
        configure("SUM(Value)")
