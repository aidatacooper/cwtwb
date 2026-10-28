"""Rich labels may depend on native sets without inventing physical columns."""
import pytest
from lxml import etree
from cwtwb import TWBEditor


@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("prebound", [False, True])
@pytest.mark.parametrize("entrypoint", ["python", "mcp", "run-spec"])
def test_rich_label_resolves_native_set_dependency(tmp_path, direct, prebound, entrypoint, monkeypatch):
    editor = TWBEditor("")
    editor.add_calculated_field("Category", "'A'", datatype="string", role="dimension", field_type="nominal")
    editor.add_calculated_field("Metric", "1.0")
    editor.add_set("Picked", dimension_field="Category", members=["A"])
    group_before = etree.tostring(editor._datasource.find("group[@name='[Picked]']"))
    editor.add_calculated_field("Selected Metric", "IF [Picked] THEN [Metric] END")
    editor.add_calculated_field("Peak", "WINDOW_MAX(SUM([Selected Metric]))", table_calc="Columns")
    editor.add_worksheet("Summary")
    field = "Picked" if direct else "Peak"
    options = dict(mark_type="Bar", rows=["Category"], columns=["SUM(Metric)"])
    if prebound:
        options["label"] = field
        if not direct:
            options["table_calc_overrides"] = {
                "Peak": [{"ordering_type": "Field", "order": ["Category"]}]
            }
    editor.configure_chart("Summary", **options)
    if entrypoint == "mcp":
        from cwtwb.mcp import tools_workbook
        monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
        tools_workbook.configure_custom_label("Summary", [{"field": field}])
    elif entrypoint == "run-spec":
        from cwtwb.commands.run_spec import _apply_worksheets
        _apply_worksheets(editor, {"worksheets": [{
            "name": "Summary", **options, "custom_labels": [{"runs": [{"field": field}]}],
        }]})
    else:
        editor.configure_custom_label("Summary", [{"field": field}])
    editor.configure_custom_label("Summary", [{"field": field}])
    worksheet = editor.root.find(".//worksheet[@name='Summary']")
    assert editor.root.find("./datasources/datasource/group[@name='[Picked]']") is not None
    assert etree.tostring(editor._datasource.find("group[@name='[Picked]']")) == group_before
    assert not worksheet.xpath('.//datasource-dependencies/column[@name="[Picked]"]')
    if direct:
        instance = worksheet.find(".//column-instance[@column='[Picked]']")
        assert instance.get("derivation") == "InOut"
    else:
        local = editor.field_registry.parse_expression("Selected Metric").column_local_name
        assert worksheet.xpath('.//datasource-dependencies/column[@name=$name]', name=local)
        peak = editor.field_registry.parse_expression("Peak").column_local_name
        calc = worksheet.find(f".//column-instance[@column='{peak}']/table-calc")
        assert calc is not None
        assert calc.get("ordering-type") == ("Field" if prebound else "Columns")
        if prebound:
            assert calc.find("order") is not None
    path=tmp_path/'set-label.twb'
    editor.save(str(path))
    assert TWBEditor.open_existing(path).root.find(".//customized-label") is not None
