"""Synthetic continuous palette and map-layer style contracts."""
import pytest
from lxml import etree
from cwtwb import TWBEditor


def fixture():
    editor = TWBEditor("")
    editor.add_worksheet("Sales")
    editor.configure_chart("Sales", "Bar", rows=["Category"], columns=["SUM(Sales)"], color="SUM(Sales)")
    return editor


def test_custom_continuous_palette_replaces_previous_encoding():
    editor = fixture()
    for colors in [["#ffffff", "#222222"], ["#f1f1f1", "#ccaaaa", "#83514a"]]:
        editor.configure_worksheet_style("Sales", color_style={"field": "SUM(Sales)", "colors": colors})
    encodings = editor.root.findall(".//table/style/style-rule/encoding[@attr='color']")
    assert len(encodings) == 1
    assert encodings[0].get("type") == "custom-interpolated"
    assert [c.text for c in encodings[0].findall("color-palette/color")] == colors
    before = etree.tostring(encodings[0])
    with pytest.raises(ValueError):
        editor.configure_worksheet_style("Sales", color_style={"field": "SUM(Sales)", "colors": ["bad", "#fff"]})
    assert etree.tostring(editor.root.find(".//table/style/style-rule/encoding[@attr='color']")) == before


def test_map_layers_and_generated_axis_style_bind_virtual_fields():
    editor = fixture()
    editor.configure_worksheet_style("Sales", map_style={"layers": {"admin0-boundary": False, "water": True}},
                                     axis_style={"per_field": [{"field": "Latitude (generated)", "scope": "rows", "display": "false"}]})
    rules = editor.root.findall(".//table/style/style-rule[@element='map-layer']/format")
    assert {node.get("id"): node.get("value") for node in rules} == {"admin0-boundary": "false", "water": "true"}
    assert not editor.root.findall("datasources/datasource/column[@name='[Latitude (generated)]']")
