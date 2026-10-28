"""Rich labels may depend on native sets without inventing physical columns."""
import pytest
from cwtwb import TWBEditor


@pytest.mark.parametrize("direct", [False, True])
@pytest.mark.parametrize("entrypoint", ["python", "mcp"])
def test_rich_label_resolves_native_set_dependency(tmp_path, direct, entrypoint, monkeypatch):
    editor = TWBEditor("")
    editor.add_calculated_field("Category", "'A'", datatype="string", role="dimension", field_type="nominal")
    editor.add_calculated_field("Metric", "1.0")
    editor.add_set("Picked", dimension_field="Category", members=["A"])
    editor.add_calculated_field("Selected Metric", "IF [Picked] THEN [Metric] END")
    editor.add_calculated_field("Peak", "WINDOW_MAX(SUM([Selected Metric]))", table_calc="Columns")
    editor.add_worksheet("Summary")
    editor.configure_chart("Summary", mark_type="Bar", rows=["Category"], columns=["SUM(Metric)"])
    if entrypoint == "mcp":
        from cwtwb.mcp import tools_workbook
        monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
        tools_workbook.configure_custom_label("Summary", [{"field": "Picked" if direct else "Peak"}])
    else:
        editor.configure_custom_label("Summary", [{"field": "Picked" if direct else "Peak"}])
    editor.configure_custom_label("Summary", [{"field": "Picked" if direct else "Peak"}])
    worksheet = editor.root.find(".//worksheet[@name='Summary']")
    assert editor.root.find("./datasources/datasource/group[@name='[Picked]']") is not None
    assert not worksheet.xpath('.//datasource-dependencies/column[@name="[Picked]"]')
    if direct:
        instance = worksheet.find(".//column-instance[@column='[Picked]']")
        assert instance.get("derivation") == "InOut"
    else:
        local = editor.field_registry.parse_expression("Selected Metric").column_local_name
        assert worksheet.xpath('.//datasource-dependencies/column[@name=$name]', name=local)
    path=tmp_path/'set-label.twb'
    editor.save(str(path))
    assert TWBEditor.open_existing(path).root.find(".//customized-label") is not None
