"""Synthetic regressions for parallel coordinates and grouped bar layers."""
import pytest
from cwtwb import TWBEditor
from cwtwb.mcp import tools_workbook


def synthetic():
    editor = TWBEditor("")
    for name, formula, datatype, role, field_type in [
        ("Item", "'A'", "string", "dimension", "nominal"),
        ("Venue", "'Home'", "string", "dimension", "nominal"),
        ("Selected", "TRUE", "boolean", "dimension", "nominal"),
        ("Value", "1.0", "real", "measure", "quantitative"),
        ("Normalized", "SUM([Value])/WINDOW_MAX(SUM([Value]))", "real", "measure", "quantitative"),
    ]:
        editor.add_calculated_field(name, formula, datatype=datatype, role=role, field_type=field_type)
    editor.add_worksheet("Synthetic")
    return editor


def test_independent_measure_panes_and_hidden_sort_controls_through_mcp(monkeypatch, tmp_path):
    editor = synthetic()
    editor.add_calculated_field("Other", "2.0", datatype="real")
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_layered_chart(
        "Synthetic", rows=["Item"], columns=["SUM(Value)", "SUM(Other)"],
        axis_shelf="columns", fold_axes=False, hide_axes=True,
        panes=[{"axis": "SUM(Value)", "mark_type": "Bar"},
               {"axis": "SUM(Other)", "mark_type": "Text"}],
    )
    table = editor.root.find("worksheets/worksheet/table")
    assert len(table.findall("panes/pane")) == 2
    assert table.find("style/style-rule/encoding[@fold='true']") is None
    assert len(table.findall("style/style-rule[@element='axis']/format[@attr='display']")) == 2
    tools_workbook.configure_worksheet_style("Synthetic", hide_sort_controls=True)
    tools_workbook.configure_worksheet_style("Synthetic", hide_sort_controls=True)
    assert len(table.findall("view/hide-sort-controls")) == 1
    tools_workbook.configure_worksheet_style("Synthetic", hide_gridlines=True)
    assert table.find("view/hide-sort-controls") is not None
    tools_workbook.configure_worksheet_style("Synthetic", hide_sort_controls=False)
    assert table.find("view/hide-sort-controls") is None
    tools_workbook.configure_worksheet_style("Synthetic", hide_sort_controls=True)
    output = tmp_path / "independent.twb"
    editor.save(output)
    assert TWBEditor.open_existing(output).root.find(".//view/hide-sort-controls") is not None


def test_independent_pane_options_reject_non_boolean_values():
    editor = synthetic()
    with pytest.raises(ValueError, match="fold_axes"):
        editor.configure_layered_chart("Synthetic", fold_axes="false")
    with pytest.raises(ValueError, match="hide_sort_controls"):
        editor.configure_worksheet_style("Synthetic", hide_sort_controls="true")


@pytest.mark.parametrize("source", ["Measure Names", "[:Measure Names]"])
def test_parameter_action_accepts_virtual_measure_names_without_physical_field(source, monkeypatch):
    editor = synthetic()
    editor.configure_chart("Synthetic", rows=["Item"], columns=["SUM(Value)"])
    editor.add_parameter("Selected Metric", datatype="string", default_value="Value", domain_type="any")
    editor.add_dashboard("Comparison", worksheet_names=["Synthetic"])
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.add_dashboard_action(
        dashboard_name="Comparison", action_type="parameter", source_sheet="Synthetic",
        source_field=source, target_parameter="Selected Metric",
    )
    source = editor.root.find("actions/edit-parameter-action/params/param[@name='source-field']")
    assert source.get("value").endswith(".[:Measure Names]")
    assert not editor.root.xpath("datasources/datasource/column[@caption='Measure Names']")


def test_repeated_measure_axes_keep_path_compound_color_and_metric_order(monkeypatch, tmp_path):
    editor = synthetic()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_layered_chart(
        "Synthetic", columns=["Measure Names"], rows=["Multiple Values", "Multiple Values"],
        hide_axes=True,
        panes=[
            {"axis": "Multiple Values", "mark_type": "Line", "detail": "Item", "color": "Selected", "color_extra": ["ATTR(Venue)"], "measure_values": ["Normalized", "SUM(Value)"]},
            {"axis": "Multiple Values", "mark_type": "Line", "path": "Item", "label": "Measure Names"},
        ],
        table_calc_overrides={"Normalized": [{"ordering_type": "Field", "order": ["Item", "Selected"], "sort": {"direction": "DESC", "using": "SUM(Value)"}}]},
    )
    table = editor.root.find("worksheets/worksheet/table")
    panes = table.findall("panes/pane")
    assert [p.get("y-index") for p in panes] == ["0", "1"]
    assert len(panes[0].findall("encodings/color")) == 2
    item = editor.field_registry.parse_expression("Item")
    assert panes[1].find("encodings/path").get("column").endswith("." + item.instance_name)
    assert panes[1].find("encodings/text").get("column").endswith(".[:Measure Names]")
    fold = table.find("style/style-rule/encoding[@fold='true']")
    assert fold.get("class") == "1" and fold.get("synchronized") == "true"
    buckets = table.findall("view/manual-sort/dictionary/bucket")
    assert editor.field_registry.parse_expression("Normalized").instance_name in buckets[0].text
    assert editor.field_registry.parse_expression("SUM(Value)").instance_name in buckets[1].text
    tc = table.find("view/datasource-dependencies/column-instance/table-calc")
    assert [n.get("field").split(".")[-1] for n in tc.findall("order")] == [item.column_local_name, editor.field_registry.parse_expression("Selected").column_local_name]
    assert tc.find("sort").get("direction") == "DESC"
    output = tmp_path / "synthetic.twb"
    editor.save(output, validate=False)
    loaded = TWBEditor.open_existing(output)
    assert len(loaded.root.findall(".//encodings/path")) == 1


def test_layered_descending_sort_is_forwarded_through_mcp(monkeypatch):
    editor = synthetic()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_layered_chart("Synthetic", rows=["Item"], columns=["SUM(Value)"], axis_shelf="columns", sort_descending="SUM(Value)", panes=[{"axis": "SUM(Value)", "mark_type": "Bar"}])
    sort = editor.root.find(".//shelf-sort-v2")
    assert sort is not None and sort.get("direction") == "DESC"
    assert sort.get("dimension-to-sort").endswith("." + editor.field_registry.parse_expression("Item").instance_name)


def test_shelf_sort_targets_inner_dimension_preserving_outer_partitions():
    editor = synthetic()
    editor.configure_chart("Synthetic", rows=["Venue", "Item"], columns=["SUM(Value)"], sort_descending="SUM(Value)")
    sort = editor.root.find(".//shelf-sort-v2")
    assert sort.get("dimension-to-sort").endswith("." + editor.field_registry.parse_expression("Item").instance_name)


@pytest.mark.parametrize("spec", [{"order": "Item"}, {"order": [12]}, {"sort": {"direction": "sideways", "using": "SUM(Value)"}}])
def test_layered_rejects_invalid_addressing_instead_of_stringifying_lists(spec):
    editor = synthetic()
    with pytest.raises(ValueError):
        editor.configure_layered_chart("Synthetic", rows=["Normalized"], panes=[{"axis": "Normalized", "mark_type": "Line"}], table_calc_overrides={"Normalized": [spec]})


def test_numeric_palettes_bind_unquoted_members_and_strings_remain_quoted():
    editor = synthetic()
    editor.add_calculated_field("Group", "0", datatype="integer", role="dimension", field_type="ordinal")
    editor.configure_layered_chart("Synthetic", rows=["Item"], columns=["SUM(Value)"], axis_shelf="columns", panes=[{"axis": "SUM(Value)", "color": "Group", "color_map": {"0": "#28a1a7", "1": "#bab0ac"}}, {"axis": "SUM(Value)", "color": "Venue", "color_map": {"Home": "#abcdef"}}])
    buckets = editor.root.findall("datasources/datasource/style/style-rule/encoding/map/bucket")
    assert [n.text for n in buckets] == ["0", "1", '"Home"']


def test_group_can_preserve_unmapped_members_through_mcp(monkeypatch, tmp_path):
    editor = synthetic()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.add_group("Partial Group", "Item", {"Named": ["A"]}, default_value=None)
    calculation = editor.root.find("datasources/datasource/column[@caption='Partial Group']/calculation")
    assert calculation.get("default") is None
    assert calculation.find("bin/value").text == '"A"'
    output = tmp_path / "group.twb"
    editor.save(output, validate=False)
    loaded = TWBEditor.open_existing(output)
    assert loaded.root.find("datasources/datasource/column[@caption='Partial Group']/calculation").get("default") is None


def test_categorical_bins_escape_quotes_and_pattern_characters(tmp_path):
    editor = synthetic()
    editor.add_group("Escaped", "Item", {"Brand": ['ACME 5" #1 50%', r"A\B"]}, default_value=None)
    values = editor.root.findall("datasources/datasource/column[@caption='Escaped']/calculation/bin/value")
    assert [n.text for n in values] == ['"ACME 5\\" \\#1 50\\%"', '"A\\\\B"']
    output = tmp_path / "escaped.twb"
    editor.save(output, validate=False)
    loaded = TWBEditor.open_existing(output)
    assert [n.text for n in loaded.root.findall("datasources/datasource/column[@caption='Escaped']/calculation/bin/value")] == [n.text for n in values]


@pytest.mark.parametrize("name,datatype,field_type,suffix", [("Text", "string", "nominal", "nk"), ("Day", "date", "ordinal", "ok"), ("Number", "real", "quantitative", "qk")])
def test_attr_preserves_field_domain(name, datatype, field_type, suffix):
    editor = TWBEditor("")
    editor.add_calculated_field(name, "'a'" if datatype == "string" else "#2026-01-01#" if datatype == "date" else "1.0", datatype=datatype, role="dimension", field_type=field_type)
    instance = editor.field_registry.parse_expression(f"ATTR({name})")
    assert instance.ci_type == field_type
    assert instance.instance_name.endswith(f":{suffix}]")


def test_measure_names_header_styles_use_virtual_field_without_registration():
    editor = synthetic()
    editor.configure_layered_chart("Synthetic", columns=["Measure Names"], rows=["Multiple Values"], panes=[{"axis": "Multiple Values", "measure_values": ["SUM(Value)"]}])
    editor.configure_worksheet_style("Synthetic", label_formats=[{"field": "Measure Names", "display": "false"}])
    formats = editor.root.findall(".//style-rule[@element='label']/format")
    assert any(f.get("field", "").endswith(".[:Measure Names]") and f.get("attr") == "display" for f in formats)
    assert editor.field_registry.get("Measure Names") is None
