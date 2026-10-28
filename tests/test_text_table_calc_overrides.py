"""Text tables must retain explicitly requested calculation partitions."""
import pytest
from lxml import etree
from cwtwb import TWBEditor


@pytest.mark.parametrize("measure_values", [False, True])
@pytest.mark.parametrize("entrypoint", ["python", "mcp", "run-spec"])
def test_text_table_keeps_field_addressing_after_save(tmp_path, measure_values, entrypoint, monkeypatch):
    editor = TWBEditor("")
    editor.add_calculated_field("District", "'North'", datatype="string", role="dimension", field_type="nominal")
    editor.add_calculated_field("Metric", "1.0")
    editor.add_calculated_field("Rank", "RANK(SUM([Metric]))", table_calc="Rows")
    editor.add_calculated_field("Share", "SUM([Metric]) / WINDOW_SUM(SUM([Metric]))", table_calc="Rows")
    editor.add_worksheet("Summary")
    options = dict(mark_type="Text", rows=["District"], label="Share",
                   label_extra=["Rank"], filters=[{"column": "Rank", "min": "1", "max": "3"}],
                   table_calc_overrides={name: [{"ordering_type": "Field", "order": ["District"]}]
                                         for name in ["Rank", "Share"]})
    if measure_values:
        options.update(measure_values=["Rank", "Share"])
    else:
        options.update(label_runs=[{"field": "District"}, {"text": ": "}, {"field": "Share"}])
    if entrypoint == "mcp":
        from cwtwb.mcp import tools_workbook
        monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
        tools_workbook.configure_chart("Summary", **options)
    elif entrypoint == "run-spec":
        from cwtwb.commands.run_spec import _apply_worksheets
        _apply_worksheets(editor, {"worksheets": [{"name": "Summary", **options}]})
    else:
        editor.configure_chart("Summary", **options)
    path = tmp_path / "text-addressing.twb"
    editor.save(str(path))
    sheet = etree.parse(str(path)).find(".//worksheet[@name='Summary']")
    for name in ["Rank", "Share"]:
        local = editor.field_registry.parse_expression(name).column_local_name
        instances = sheet.xpath('.//column-instance[@column=$column]', column=local)
        assert instances
        for instance in instances:
            calc = instance.find("table-calc")
            assert calc.get("ordering-type") == "Field"
            order = calc.find("order")
            assert order is not None
            assert order.get("field").endswith(editor.field_registry.parse_expression("District").column_local_name)


def test_text_table_rejects_unbound_override_instead_of_silently_ignoring_it():
    editor = TWBEditor("")
    editor.add_calculated_field("Metric", "1.0")
    editor.add_calculated_field("Unused", "WINDOW_SUM(SUM([Metric]))", table_calc="Rows")
    editor.add_worksheet("Summary")
    with pytest.raises(ValueError, match="Could not resolve table-calc override"):
        editor.configure_chart("Summary", mark_type="Text", label="SUM(Metric)",
                               table_calc_overrides={"Unused": [{"ordering_type": "Columns"}]})
