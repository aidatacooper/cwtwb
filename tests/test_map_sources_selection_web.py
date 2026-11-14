"""Synthetic native map/source/viewpoint and Web Page contracts; no author assets."""

import asyncio

import pytest
from lxml import etree

from cwtwb import TWBEditor
from cwtwb.capability_registry import get_capability


def make_map():
    editor = TWBEditor("")
    editor.add_calculated_field("Point", "MAKEPOINT(1, 2)", datatype="spatial")
    editor.add_worksheet("Map")
    editor.configure_chart("Map", "Map", geographic_field="Point")
    return editor


def add_source(editor, name, caption):
    """Author a tiny independent synthetic source, with colliding field captions."""
    source = etree.SubElement(editor.root.find("datasources"), "datasource",
                              name=name, caption=caption, version="18.1", inline="true")
    for field, datatype, role, kind in (
        ("Point", "spatial", "measure", "nominal"),
        ("ID", "integer", "dimension", "ordinal"),
        ("Name", "string", "dimension", "nominal"),
        ("Amount", "real", "measure", "quantitative"),
    ):
        column = etree.SubElement(source, "column", name=f"[{field}]", datatype=datatype,
                                  role=role, type=kind)
        if field == "Point":
            etree.SubElement(column, "calculation", {"class": "tableau", "formula": "MAKEPOINT(3, 4)"})
    return source


def test_independent_layers_resolve_colliding_fields_and_tooltips(tmp_path):
    editor = make_map()
    primary = editor._datasource
    registry = editor.field_registry
    add_source(editor, "source.a", "Locations A")
    add_source(editor, "source.b", "Locations B")
    specs = [
        {"geometry": "Point", "name": "Primary"},
        {"datasource": "Locations A", "geometry": "Point", "detail": "ID",
         "color": "SUM(Amount)", "tooltip": ["Name"], "name": "A"},
        {"datasource": "source.b", "geometry": "Point", "detail": "ID",
         "color": "SUM(Amount)", "tooltip": ["Name"], "name": "B", "inert": True},
        {"datasource": "source.a", "geometry": "Point", "label": "SUM(Amount)", "name": "A again"},
    ]
    editor.configure_chart("Map", "Map", geographic_field="Point",
                           map_layers=specs, map_layer_mode="native")
    assert editor._datasource is primary and editor.field_registry is registry
    view = editor.root.find("worksheets/worksheet/table/view")
    assert len(view.findall("datasources/datasource")) == 3
    assert len(view.findall("datasource-dependencies")) == 3
    assert not editor.root.findall(".//join-lod-include-overrides")
    assert editor.root.find("document-format-change-manifest/LayersPerPaneSpecPrimaryDS") is not None
    for source, pane_name in (("source.a", "A"), ("source.b", "B")):
        pane = editor.root.xpath("//pane[@generated-title=$name]", name=pane_name)[0]
        assert pane.find("encodings/geometry").get("column") == f"[{source}].[clct:Point:nk]"
        assert pane.find("encodings/tooltip").get("column") == f"[{source}].[attr:Name:nk]"
        deps = view.xpath("datasource-dependencies[@datasource=$name]", name=source)[0]
        assert deps.find("column-instance[@name='[attr:Name:nk]']") is not None
        assert deps.find("column-instance[@name='[sum:Amount:qk]']") is not None
    assert view.find("datasource-dependencies").get("datasource") == primary.get("name")
    output = tmp_path / "independent.twb"
    editor.save(str(output))
    assert len(etree.parse(str(output)).findall(".//pane[@generated-title]")) == 4
    # Reconfiguration replaces the source dependency set, avoiding stale layers.
    editor.configure_chart("Map", "Map", geographic_field="Point",
                           map_layers=specs[:2], map_layer_mode="native")
    assert view.find("datasource-dependencies[@datasource='source.b']") is None
    assert view.find("datasources/datasource[@name='source.b']") is None
    editor.configure_chart("Map", "Map", geographic_field="Point")
    assert len(view.findall("datasources/datasource")) == 1


@pytest.mark.parametrize("spec,mode", [
    ({"datasource": "missing", "geometry": "Point"}, "native"),
    ({"datasource": "", "geometry": "Point"}, "native"),
    ({"datasource": "source.a", "geometry": "Point"}, "overlay"),
    ({"datasource": "source.a", "geometry": "Missing"}, "native"),
    ({"datasource": "Parameters", "geometry": "Point"}, "native"),
])
def test_invalid_source_bindings_do_not_change_xml(spec, mode):
    editor = make_map()
    add_source(editor, "source.a", "A")
    before = etree.tostring(editor.root)
    registry = editor.field_registry
    with pytest.raises((ValueError, KeyError)):
        editor.configure_chart("Map", "Map", geographic_field="Point",
                               map_layers=[spec], map_layer_mode=mode)
    assert etree.tostring(editor.root) == before
    assert editor.field_registry is registry


def test_drive_time_inherits_and_updates_dashboard_viewpoints(tmp_path):
    editor = make_map()
    layout = {"type": "worksheet", "name": "Map", "fit": "entire"}
    editor.add_dashboard("Before", layout=layout)
    editor.configure_map_selection("Map")
    editor.add_dashboard("After", layout=layout)
    for window in editor.root.findall("windows/window"):
        viewpoint = window.find("viewpoint") if window.get("class") == "worksheet" else window.find("viewpoints/viewpoint")
        assert viewpoint.find("default-map-tool-selection").get("tool") == "32"
        assert viewpoint.find("floating-toolbar-visibility").get("value") == "1"
        if window.get("class") == "dashboard":
            assert viewpoint.find("zoom").get("type") == "entire-view"
    editor.configure_map_selection("Map", show_toolbar=False)
    editor.configure_map_selection("Map", show_toolbar=False)
    assert len(editor.root.findall(".//default-map-tool-selection")) == 3
    assert all(n.get("value") == "0" for n in editor.root.findall(".//floating-toolbar-visibility"))
    output = tmp_path / "selection.twb"
    editor.save(str(output))
    assert len(etree.parse(str(output)).findall(".//default-map-tool-selection[@tool='32']")) == 3


@pytest.mark.parametrize("options", [{"tool": "unknown"}, {"show_toolbar": 1}])
def test_invalid_selection_options_do_not_mutate(options):
    editor = make_map()
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.configure_map_selection("Map", **options)
    assert etree.tostring(editor.root) == before


def test_selection_requires_map():
    editor = TWBEditor("")
    editor.add_worksheet("Text")
    with pytest.raises(ValueError, match="configured map"):
        editor.configure_map_selection("Text")


def test_web_zone_url_layout_and_round_trip(tmp_path):
    editor = make_map()
    url = "https://example.org/view?a=1&b=two#part"
    editor.add_dashboard("Portal", layout={"type": "container", "children": [
        {"type": "worksheet", "name": "Map"},
        {"type": "web", "url": url, "fixed_size": 300, "style": {"margin": 4}},
    ]})
    zone = editor.root.find(".//zone[@type-v2='web']")
    assert zone.get("param") == url
    assert zone.get("forceUpdate") == ""
    assert zone.find("zone-style/format[@attr='margin']").get("value") == "4"
    assert int(zone.get("h")) > 0 and int(zone.get("w")) > 0
    output = tmp_path / "portal.twb"
    editor.save(str(output))
    assert etree.parse(str(output)).find(".//zone[@type-v2='web']").get("param") == url


@pytest.mark.parametrize("url", [None, "", "javascript:alert(1)", "file:///tmp/x", "https://", "https://user:pass@example.org", "https://example.org/a b"])
def test_invalid_web_urls(url):
    editor = make_map()
    editor.add_dashboard("Portal", layout={"type": "worksheet", "name": "Map"})
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError, match="HTTP"):
        editor.add_dashboard("Portal", layout={"type": "web", "url": url})
    assert etree.tostring(editor.root) == before


def test_mcp_and_capability_public_surface(monkeypatch):
    from cwtwb.mcp import tools_workbook as tools
    from cwtwb.mcp.app import server

    editor = make_map()
    add_source(editor, "source.a", "A")
    monkeypatch.setattr(tools, "get_editor", lambda: editor)
    tools.configure_chart("Map", "Map", geographic_field="Point",
                          map_layer_mode="native",
                          map_layers=[{"datasource": "A", "geometry": "Point"}])
    tools.configure_map_selection("Map")
    tools.add_dashboard("Portal", worksheet_names=[], layout={"type": "web", "url": "https://example.org"})
    names = {tool.name for tool in asyncio.run(server.list_tools())}
    assert "configure_map_selection" in names
    for kind, key in (("feature", "drive-time-selection"),
                      ("feature", "independent-map-datasources"),
                      ("dashboard_zone", "web")):
        assert get_capability(kind, key).level != "unsupported"


def test_ambiguous_datasource_caption_rejected():
    editor = make_map()
    add_source(editor, "source.a", "Duplicate")
    add_source(editor, "source.b", "Duplicate")
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError, match="unambiguous"):
        editor.configure_chart("Map", "Map", geographic_field="Point",
                               map_layer_mode="native",
                               map_layers=[{"datasource": "Duplicate", "geometry": "Point"}])
    assert etree.tostring(editor.root) == before


def test_parameter_calculations_and_independent_measure_names():
    editor = make_map()
    editor.add_parameter("Mode", datatype="integer", default_value="1")
    for name in ("source.a", "source.b"):
        add_source(editor, name, name)
        editor.select_datasource(name)
        editor.add_calculated_field("Visible Point", "IF [Mode] = 1 THEN [Point] END",
                                    datatype="spatial")
    editor.select_datasource("source.a")
    specs = [
        {"datasource": name, "geometry": "Visible Point", "mark_type": "Pie",
         "color": "Measure Names", "wedge_size": "Multiple Values",
         "measure_values": ["SUM(Amount)"],
         "color_map": {"SUM(Amount)": color}}
        for name, color in (("source.a", "#ff0000"), ("source.b", "#0000ff"))
    ]
    editor.configure_chart("Map", "Map", geographic_field="Visible Point",
                           map_layer_mode="native", map_layers=specs)
    view = editor.root.find("worksheets/worksheet/table/view")
    assert len(view.findall("datasource-dependencies[@datasource='Parameters']")) == 1
    assert len(view.findall("datasources/datasource[@name='Parameters']")) == 1
    for name in ("source.a", "source.b"):
        deps = view.xpath("datasource-dependencies[@datasource=$name]", name=name)[0]
        assert deps.find("column[@name='[Point]']") is not None
        assert deps.find("column[@name='[Mode]']") is None
        assert view.xpath("filter[@column=$column]", column=f"[{name}].[:Measure Names]")
        palette = editor.root.xpath("datasources/datasource[@name=$name]/style", name=name)[0]
        assert f"[{name}].[sum:Amount:qk]" in etree.tostring(palette).decode()


def test_native_features_validate_against_current_xsd(tmp_path):
    from cwtwb.validator import validate_against_schema

    editor = make_map()
    add_source(editor, "source.a", "A")
    editor.configure_chart("Map", "Map", geographic_field="Point",
                           map_layer_mode="native", map_layers=[
                               {"geometry": "Point"},
                               {"datasource": "A", "geometry": "Point", "detail": "ID"},
                           ])
    editor.configure_map_selection("Map")
    editor.add_dashboard("Portal", layout={"type": "container", "children": [
        {"type": "worksheet", "name": "Map", "fit": "entire"},
        {"type": "web", "url": "https://example.org"},
    ]})
    path = tmp_path / "native.twb"
    editor.save(str(path))
    root = etree.parse(str(path)).getroot()
    root.set("version", "26.2")
    result = validate_against_schema(root)
    assert result.schema_available
    assert result.schema_version == "2026.2"
    assert result.errors == []


def test_independent_generated_geometry_and_floating_web_zone():
    editor = make_map()
    source = add_source(editor, "source.a", "A")
    column = etree.SubElement(source, "column", name="[Country]", datatype="string",
                              role="dimension", type="nominal")
    column.set("semantic-role", "[Country].[Name]")
    editor.configure_chart("Map", "Map", geographic_field="Point",
                           map_layer_mode="native", map_layers=[
                               {"geometry": "Point"},
                               {"datasource": "A", "mark_type": "Map", "detail": "Country",
                                "geometry": "Geometry (generated)", "inert": True},
                           ])
    pane = editor.root.find(".//pane[@inert='true']")
    assert pane.find("encodings/geometry").get("column") == "[source.a].[Geometry (generated)]"
    assert pane.find("encodings/lod").get("column") == "[source.a].[none:Country:nk]"
    editor.add_dashboard("Portal", layout={"type": "floating", "children": [
        {"type": "web", "url": "https://example.org",
         "absolute": {"x": 1000, "y": 2000, "w": 30000, "h": 40000}},
    ]})
    zone = editor.root.find(".//zone[@type-v2='web']")
    assert [zone.get(key) for key in ("x", "y", "w", "h")] == ["1000", "2000", "30000", "40000"]
