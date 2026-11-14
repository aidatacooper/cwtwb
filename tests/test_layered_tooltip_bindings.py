"""Synthetic regressions for tooltip bindings across layered axes."""

import pytest

from cwtwb import TWBEditor
from cwtwb.validator import load_workbook_root


@pytest.mark.parametrize("axis_shelf", ["columns", "rows"])
@pytest.mark.parametrize("fold_axes", [True, False])
def test_other_pane_axis_remains_available_as_tooltip(tmp_path, axis_shelf, fold_axes):
    editor = TWBEditor("")
    editor.add_calculated_field("Revenue", "10.0", datatype="real")
    editor.add_calculated_field("Latest Revenue", "[Revenue]", datatype="real")
    editor.add_calculated_field(
        "Period", "'Current'", datatype="string", role="dimension",
        field_type="nominal",
    )
    editor.add_worksheet("Layered")
    shared_shelf = "rows" if axis_shelf == "columns" else "columns"
    editor.configure_layered_chart(
        "Layered",
        **{axis_shelf: ["SUM(Revenue)", "MIN(Latest Revenue)"],
           shared_shelf: ["Period"]},
        axis_shelf=axis_shelf,
        fold_axes=fold_axes,
        panes=[
            {"axis": "SUM(Revenue)", "mark_type": "Line",
             "tooltip": ["SUM(Revenue)", "Period"]},
            {"axis": "MIN(Latest Revenue)", "mark_type": "Circle",
             "tooltip": ["SUM(Revenue)", "MIN(Latest Revenue)", "Period",
                         "SUM(Revenue)"]},
        ],
    )
    panes = editor.root.findall(".//worksheet/table/panes/pane")
    assert panes[0].findall("encodings/tooltip") == []
    tooltips = panes[1].findall("encodings/tooltip")
    assert len(tooltips) == 1
    expected = editor.field_registry.resolve_full_reference(
        editor.field_registry.parse_expression("SUM(Revenue)").instance_name
    )
    assert tooltips[0].get("column") == expected
    output = tmp_path / "layered.twbx"
    editor.save(output)
    reopened = load_workbook_root(output)
    assert [
        tooltip.get("column")
        for tooltip in reopened.findall(".//pane[@id='2']/encodings/tooltip")
    ] == [expected]
