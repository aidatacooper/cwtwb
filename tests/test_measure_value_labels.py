"""Regression contracts for ordered KPI labels and geographic role overrides."""
import pytest
from cwtwb import TWBEditor


def test_measure_values_keep_requested_order_and_virtual_rich_labels():
    editor = TWBEditor("")
    editor.add_calculated_field("First KPI", "1.0")
    editor.add_calculated_field("Second KPI", "2.0")
    editor.add_worksheet("KPIs")
    editor.configure_chart("KPIs", "Text", measure_values=["Second KPI", "First KPI"],
                           label_runs=[{"field": "Multiple Values", "fontsize": 24},
                                       {"text": "\n"}, {"field": "Measure Names", "fontsize": 10}])
    view = editor.root.find("worksheets/worksheet/table/view")
    buckets = view.findall("manual-sort/dictionary/bucket")
    assert len(buckets) == 2
    for node, name in zip(buckets, ["Second KPI", "First KPI"]):
        instance = editor.field_registry.parse_expression(name)
        assert node.text == '"' + editor.field_registry.resolve_full_reference(instance.instance_name) + '"'
    labels = editor.root.findall(".//customized-label/formatted-text/run")
    assert any("[Multiple Values]" in (run.text or "") and run.get("fontsize") == "24" for run in labels)
    assert any("[:Measure Names]" in (run.text or "") for run in labels)
    assert any(node.get("column").endswith(".[:Measure Names]") for node in editor.root.findall(".//pane/encodings/text"))


def test_geographic_role_updates_existing_dependency_and_can_clear():
    editor = TWBEditor("")
    editor.add_calculated_field("Area", "'California'", datatype="string", role="dimension")
    editor.add_worksheet("Map")
    editor.configure_chart("Map", "Map", geographic_field="Area")
    editor.set_field_geographic_role("Area", "state")
    source = editor.root.find("datasources/datasource/column[@caption='Area']")
    name = source.get("name")
    copies = editor.root.findall(f".//datasource-dependencies/column[@name='{name}']")
    assert copies and all(node.get("semantic-role") == "[State].[Name]" for node in copies)
    editor.set_field_geographic_role("Area", "")
    assert source.get("semantic-role") is None
    assert all(node.get("semantic-role") is None for node in copies)
    with pytest.raises(ValueError):
        editor.set_field_geographic_role("Area", "unsupported")
