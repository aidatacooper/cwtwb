"""Author-free regressions for dynamic domains and native visual encodings."""

import json

import pytest
from lxml import etree

from cwtwb import TWBEditor


def editor():
    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field(
        "Other", "'B'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Value", "7")
    e.add_calculated_field(
        "Positive",
        "SUM([Value])>0",
        datatype="boolean",
        role="dimension",
        field_type="nominal",
    )
    e.add_worksheet("Plot")
    e.configure_chart(
        "Plot", mark_type="Bar", columns=["SUM(Value)"], rows=["Category"]
    )
    return e


def palette(e, **changes):
    options = {
        "fields": ["Measure Names", "AGG(Positive)"],
        "mappings": [
            {"values": ["SUM(Value)", True], "color": "#123456"},
            {"values": ["SUM(Value)", False], "color": "#ffffff"},
        ],
    }
    options.update(changes)
    return e.set_compound_color_palette(**options)


def test_all_members_is_dynamic_registered_and_saveable(tmp_path):
    e = editor()
    e.add_parameter(
        "Choose",
        datatype="string",
        default_value="Category",
        domain_type="list",
        allowed_values=["Category", "Other"],
    )
    e.add_calculated_field(
        "Dynamic",
        "IF [Choose]='Category' THEN [Category] ELSE [Other] END",
        datatype="string",
        role="dimension",
        field_type="nominal",
    )
    assert "all-members" in e.add_set("Selected", "Dynamic", use_all=True)
    gf = e.root.find("datasources/datasource/group[@caption='Selected']/groupfilter")
    assert gf.get("function") == "level-members"
    assert gf.get("level") == e.field_registry._find_field("Dynamic").local_name
    assert gf.get("{http://www.tableausoftware.com/xml/user}ui-enumeration") == "all"
    assert len(gf) == 0
    e.add_calculated_field("Selected Value", "IF [Selected] THEN [Value] ELSE 0 END")
    e.configure_chart("Plot", columns=["SUM(Selected Value)"], rows=["Dynamic"])
    e.add_dashboard(
        "Dashboard",
        worksheet_names=["Plot"],
        layout={
            "type": "vertical",
            "children": [
                {"type": "worksheet", "name": "Plot"},
                {"type": "set_control", "field": "Selected", "worksheet": "Plot"},
            ],
        },
    )
    e.save(str(tmp_path / "all-members.twb"))
    assert e.root.find(".//zone[@type-v2='setMembership']") is not None


@pytest.mark.parametrize(
    "options",
    [
        {"use_all": 1},
        {"use_all": "true"},
        {"use_all": True, "members": []},
        {"use_all": True, "top_n": 2},
        {"use_all": True, "basis_field": "Value"},
    ],
)
def test_invalid_all_members_preserves_workbook(options):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        e.add_set("Invalid", "Category", **options)
    assert etree.tostring(e.root) == before


def test_compound_palette_preserves_field_order_types_and_other_palettes(tmp_path):
    e = editor()
    e.set_datasource_color_palette("Category", {"A": "#000000"})
    palette(e)
    palette(e)
    encodings = e.root.findall("datasources/datasource/style/style-rule/encoding")
    compound = [node for node in encodings if "\n" in node.get("field", "")]
    assert len(compound) == 1 and len(encodings) == 2
    encoding = compound[0]
    assert encoding.get("field").splitlines()[0] == "[:Measure Names]"
    assert len(encoding.findall("map")) == 2
    buckets = encoding.find("map/multibucket").findall("bucket")
    ci = e.field_registry.parse_expression("SUM(Value)")
    assert json.loads(buckets[0].text) == e.field_registry.resolve_full_reference(
        ci.instance_name
    )
    assert buckets[1].text == "true"
    assert encoding.findall("map")[1].findall("multibucket/bucket")[1].text == "false"
    e.save(str(tmp_path / "compound.twb"))


def test_compound_palette_handles_strings_and_numeric_members():
    e = editor()
    e.set_compound_color_palette(
        ["Category", "SUM(Value)"],
        [{"values": ['A "quoted"', 2.5], "color": "#11223344"}],
    )
    buckets = e.root.findall(".//multibucket/bucket")
    assert json.loads(buckets[0].text) == 'A "quoted"'
    assert buckets[1].text == "2.5"


@pytest.mark.parametrize(
    "changes",
    [
        {"fields": ["Category"]},
        {"fields": ["Category", "Category"]},
        {"mappings": []},
        {"mappings": [{"values": ["SUM(Value)"], "color": "#112233"}]},
        {"mappings": [{"values": ["SUM(Value)", "true"], "color": "#112233"}]},
        {"mappings": [{"values": ["SUM(Value)", True], "color": "bad"}]},
        {
            "mappings": [
                {"values": ["SUM(Value)", True], "color": "#112233"},
                {"values": ["SUM(Value)", True], "color": "#334455"},
            ]
        },
    ],
)
def test_invalid_compound_palette_preserves_workbook(changes):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        palette(e, **changes)
    assert etree.tostring(e.root) == before


def band(e, **changes):
    options = {
        "axis_field": "SUM(Value)",
        "lower_value": 2,
        "upper_value": 9,
        "upper_label": "High",
    }
    options.update(changes)
    return e.add_reference_band("Plot", **options)


def test_paired_band_is_native_unique_and_saveable(tmp_path):
    e = editor()
    e.add_reference_line("Plot", axis_field="SUM(Value)", value_field="SUM(Value)")
    band(e)
    band(e, lower_value=10, upper_value=20)
    lines = e.root.findall(".//reference-line")
    assert len(lines) == 5 and len({line.get("id") for line in lines}) == 5
    first, second = lines[1:3]
    assert first.get("paired-id") == second.get("id")
    assert second.get("paired-id") == first.get("id")
    assert first.get("value") == "2" and second.get("value") == "9"
    assert first.get("formula") == "constant"
    assert second.get("label") == "High" and second.get("label-type") == "custom"
    fill = e.root.find(".//style-rule[@element='refband']/format")
    assert fill.get("id") == first.get("id") and fill.get("value") == "#f5f5f5"
    e.save(str(tmp_path / "band.twb"))


@pytest.mark.parametrize(
    "changes",
    [
        {"lower_value": 9},
        {"upper_value": float("inf")},
        {"lower_value": True},
        {"scope": "invalid"},
        {"pane_index": 8},
        {"pane_index": True},
        {"fill_color": "gray"},
        {"axis_field": "Category"},
    ],
)
def test_invalid_band_preserves_workbook(changes):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        band(e, **changes)
    assert etree.tostring(e.root) == before


def test_mcp_forwards_all_three_features(monkeypatch):
    from cwtwb.mcp import tools_workbook

    e = editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    tools_workbook.add_set("All", "Category", use_all=True)
    tools_workbook.set_compound_color_palette(
        ["Category", "Other"], [{"values": ["A", "B"], "color": "#112233"}]
    )
    tools_workbook.add_reference_band("Plot", "SUM(Value)", 1, 3)
    assert (
        e.root.find(".//group[@caption='All']/groupfilter").get("function")
        == "level-members"
    )
    assert e.root.find(".//multibucket") is not None
    assert len(e.root.findall(".//reference-line")) == 2


def test_run_spec_forwards_all_three_features():
    from cwtwb.commands.run_spec import (
        _apply_field_properties,
        _apply_sets,
        _apply_worksheets,
    )

    e = editor()
    _apply_sets(
        e,
        {"sets": [{"set_name": "All", "dimension_field": "Category", "use_all": True}]},
    )
    _apply_field_properties(
        e,
        {
            "compound_color_palettes": [
                {
                    "fields": ["Category", "Other"],
                    "mappings": [{"values": ["A", "B"], "color": "#112233"}],
                }
            ]
        },
    )
    _apply_worksheets(
        e,
        {
            "worksheets": [
                {
                    "name": "Plot",
                    "mark_type": "Bar",
                    "columns": ["SUM(Value)"],
                    "rows": ["Category"],
                    "reference_bands": [
                        {"axis_field": "SUM(Value)", "lower_value": 1, "upper_value": 3}
                    ],
                }
            ]
        },
    )
    assert len(e.root.findall(".//reference-line")) == 2


def test_categorical_size_preserves_virtual_measure_names_and_order(tmp_path):
    e = editor()
    e.configure_layered_chart(
        "Plot",
        columns=["Multiple Values"],
        rows=["Category"],
        panes=[
            {
                "axis": "Multiple Values",
                "mark_type": "Circle",
                "measure_values": ["SUM(Value)"],
                "size": "Measure Names",
            }
        ],
    )
    e.configure_worksheet_style(
        "Plot",
        size_style={
            "type": "catsize",
            "field": "Measure Names",
            "min_size": 0.8,
            "max_size": 1,
        },
    )
    e.configure_worksheet_style(
        "Plot",
        size_style={
            "type": "catsize",
            "field": "Measure Names",
            "min_size": 0.9,
            "max_size": 1,
        },
    )
    sizes = e.root.findall(".//table/style/style-rule/encoding[@attr='size']")
    assert len(sizes) == 1
    assert sizes[0].get("type") == "catsize" and sizes[0].get("field-type") == "nominal"
    assert sizes[0].get("field").endswith(".[:Measure Names]")
    assert sizes[0].get("min-size") == "0.9"
    assert e.root.find(".//pane/encodings/size").get("column") == sizes[0].get("field")
    e.save(str(tmp_path / "categorical-size.twb"))


@pytest.mark.parametrize(
    "changes",
    [
        {"type": "bad"},
        {"min_size": -1},
        {"min_size": 2},
        {"max_size": float("inf")},
        {"min": 0},
        {"field": "SUM(Value)"},
        {"reverse": 1},
    ],
)
def test_invalid_categorical_size_fails_before_other_style_changes(changes):
    e = editor()
    options = {"type": "catsize", "field": "Category", "min_size": 0.8, "max_size": 1}
    options.update(changes)
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        e.configure_worksheet_style(
            "Plot", background_color="#abcdef", size_style=options
        )
    assert etree.tostring(e.root) == before
