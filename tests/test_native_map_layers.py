"""Author-free synthetic native geographic layer contracts."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def make():
    editor = TWBEditor("")
    for name, formula in (
        ("All Areas", "IF 1=1 THEN 'France' END"),
        ("Chosen Area", "IF 1=0 THEN 'France' END"),
    ):
        editor.add_calculated_field(
            name, formula, datatype="string", role="dimension", field_type="nominal"
        )
    editor.add_worksheet("Map")
    return editor


def layers():
    return [
        {
            "mark_type": "Multipolygon",
            "detail": ["All Areas", "Measure Names"],
            "geometry": "Geometry (generated)",
        },
        {"mark_type": "Multipolygon", "detail": "Chosen Area"},
        {
            "mark_type": "Pie",
            "detail": "Chosen Area",
            "color": "Measure Names",
            "wedge_size": "Multiple Values",
            "measure_values": ["SUM(Sales)", "SUM(Profit)"],
            "inert": True,
            "mark_size_value": 12,
            "has_stroke": True,
            "stroke_color": "#ffffff",
        },
        {"mark_type": "Automatic", "detail": "Chosen Area", "label": "SUM(Sales)"},
    ]


def configure(editor, **options):
    return editor.configure_chart(
        "Map",
        "Map",
        geographic_field="Country/Region",
        map_layers=layers(),
        map_layer_mode="native",
        **options,
    )


def test_native_single_canvas_and_independent_null_geography():
    editor = make()
    configure(editor)
    table = editor.root.find(".//worksheet/table")
    panes = table.find("panes")
    assert panes.get("customization-axis") == "layer"
    assert len(panes) == 5
    assert table.findtext("cols").count("Longitude (generated)") == 1
    assert table.findtext("rows").count("Latitude (generated)") == 1
    assert not panes.xpath("pane[@x-index or @x-axis-name]")
    assert not panes[0].findall("encodings/lod")
    all_ref = panes[1].find("encodings/lod").get("column")
    selected_ref = panes[2].find("encodings/lod").get("column")
    assert all_ref != selected_ref
    assert [p.find("encodings/lod").get("column") for p in list(panes)[2:]] == [
        selected_ref
    ] * 3
    assert panes[3].find("encodings/geometry") is None
    assert panes[4].find("encodings/geometry") is None
    assert editor.root.find("document-format-change-manifest/Layers") is not None


def test_pie_virtual_encodings_dependencies_and_measure_filter():
    editor = make()
    configure(editor)
    table = editor.root.find(".//worksheet/table")
    pie = table.find("panes/pane[@id='3']")
    assert pie.get("inert") == "true"
    assert pie.find("encodings/color").get("column").endswith(".[:Measure Names]")
    assert pie.find("encodings/wedge-size").get("column").endswith(".[Multiple Values]")
    filters = table.findall("view/filter")
    mn = [f for f in filters if f.get("column").endswith(".[:Measure Names]")]
    assert len(mn) == 1
    assert len(mn[0].findall("groupfilter/groupfilter")) == 2
    assert (
        len(
            table.findall(
                "view/datasource-dependencies/column-instance[@derivation='Sum']"
            )
        )
        >= 2
    )
    assert not editor.root.xpath(
        ".//datasource/column[@caption='Measure Names' or @caption='Multiple Values']"
    )
    assert (
        pie.find("style/style-rule/format[@attr='has-stroke']").get("value") == "true"
    )


def test_upsert_does_not_duplicate_layers_or_measure_filter():
    editor = make()
    configure(editor)
    configure(editor)
    assert len(editor.root.findall(".//worksheet/table/panes")) == 1
    assert len(editor.root.findall(".//worksheet/table/panes/pane")) == 5
    assert (
        len(
            editor.root.xpath(
                ".//worksheet/table/view/filter[contains(@column, ':Measure Names')]"
            )
        )
        == 1
    )
    editor.set_measure_name_aliases(
        "Map", {"SUM(Sales)": "Revenue", "SUM(Profit)": "Margin"}
    )
    assert editor.root.xpath(".//alias[@value='Revenue']")


def test_default_overlay_still_repeats_longitude_axes():
    editor = make()
    editor.configure_chart(
        "Map",
        "Map",
        geographic_field="Country/Region",
        map_layers=[{"mark_type": "Circle"}, {"mark_type": "Circle"}],
    )
    table = editor.root.find(".//worksheet/table")
    assert table.find("panes").get("customization-axis") is None
    assert table.findtext("cols").count("Longitude (generated)") == 2
    assert table.find("panes/pane[@x-index='1']") is not None


@pytest.mark.parametrize(
    "options",
    [
        {"map_layer_mode": "bad"},
        {"map_layer_mode": "native", "map_layers": []},
        {"map_layer_mode": "native", "map_partition": "Region"},
        {"map_layers": [{"wedge_size": "Multiple Values"}]},
        {"map_layers": [{"measure_values": "SUM(Sales)"}]},
        {"map_layers": [{"inert": 1}]},
    ],
)
def test_invalid_options_do_not_mutate(options):
    editor = make()
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.configure_chart(
            "Map", "Map", geographic_field="Country/Region", **options
        )
    assert etree.tostring(editor.root) == before


def test_mcp_and_run_spec_forward_native_mode(monkeypatch):
    from cwtwb.commands.run_spec import _apply_worksheets
    from cwtwb.mcp import tools_workbook

    editor = make()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_chart(
        "Map",
        "Map",
        geographic_field="Country/Region",
        map_layers=layers(),
        map_layer_mode="native",
    )
    assert editor.root.find(".//panes").get("customization-axis") == "layer"
    _apply_worksheets(
        editor,
        {
            "worksheets": [
                {
                    "name": "Map",
                    "mark": "Map",
                    "geographic_field": "Country/Region",
                    "map_layers": layers(),
                    "map_layer_mode": "native",
                }
            ]
        },
    )
    assert len(editor.root.findall(".//worksheet/table/panes/pane")) == 5


def test_measure_name_palette_resolves_public_expressions():
    editor = make()
    specs = layers()
    specs[2]["color_map"] = {"SUM(Sales)": "#d3d3d3", "SUM(Profit)": "#767f8b"}
    editor.configure_chart(
        "Map",
        "Map",
        geographic_field="Country/Region",
        map_layers=specs,
        map_layer_mode="native",
    )
    buckets = editor.root.xpath(
        ".//datasource/style/style-rule/encoding[@field='[:Measure Names]']/map/bucket"
    )
    assert len(buckets) == 2
    assert all("[sum:" in bucket.text for bucket in buckets)
    assert {
        mapping.get("to")
        for mapping in editor.root.xpath(
            ".//datasource/style/style-rule/encoding[@field='[:Measure Names]']/map"
        )
    } == {"#d3d3d3", "#767f8b"}


def test_native_schema_adds_no_errors_to_empty_baseline():
    from cwtwb.validator import validate_against_schema

    editor = make()
    baseline = validate_against_schema(editor.root)
    if not baseline.schema_available:
        pytest.skip("Vendored Tableau schema unavailable")
    configure(editor)
    assert validate_against_schema(editor.root).errors == baseline.errors
