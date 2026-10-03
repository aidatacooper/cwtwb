"""Native legend regression without case data or author templates."""
import pytest
from cwtwb import TWBEditor
from cwtwb.layout import FlexNode


def test_color_and_size_legends_bind_same_field_with_distinct_native_types():
    editor = TWBEditor("")
    editor.add_calculated_field("Distance", "1")
    editor.add_worksheet("Plot")
    editor.configure_chart("Plot", mark_type="Circle", columns=["SUM(Distance)"], color="SUM(Distance)", size="SUM(Distance)")
    editor.add_dashboard("Legend", width=700, height=700, layout={"type": "container", "children": [
        {"type": "worksheet", "name": "Plot"},
        *[{"type": kind, "worksheet": "Plot", "field": "SUM(Distance)", "caption": "Distance (m)", "pane_index": 1} for kind in ("color", "size")],
    ]})
    legends = editor.root.xpath("//dashboard[@name='Legend']//zone[@type-v2='size' or @type-v2='color']")
    assert {zone.get("type-v2") for zone in legends} == {"color", "size"}
    assert len({zone.get("param") for zone in legends}) == 1
    for zone in legends:
        assert zone.get("name") == "Plot"
        assert zone.get("pane-specification-id") == "1"
        assert zone.get("custom-title") == "true"
        assert zone.find("formatted-text/run").text == "Distance (m)"


@pytest.mark.parametrize("pane", [0, -1, True, "1", 1.5])
def test_invalid_legend_pane_identity_rejected(pane):
    with pytest.raises(ValueError, match="pane_index"):
        FlexNode({"type": "size", "pane_index": pane})


def test_legend_style_upserts_fonts_and_preserves_table_background():
    editor = TWBEditor("")
    editor.add_worksheet("Plot")
    editor.configure_worksheet_style("Plot", background_color="#f5f5f5", legend_style={"font_size": 8, "font-color": "#333333"})
    editor.configure_worksheet_style("Plot", legend_style={"font-size": 9})
    nodes = editor.root.xpath("//worksheet[@name='Plot']/table/style/style-rule[@element='legend']/format")
    assert {node.get("attr"): node.get("value") for node in nodes} == {"font-size": "9", "font-color": "#333333"}
    assert len(nodes) == 2
    assert editor.root.xpath("//worksheet[@name='Plot']/table/style/style-rule[@element='table']/format[@attr='background-color']/@value") == ["#f5f5f5"]

@pytest.mark.parametrize("invalid", ["bad", [], {"": 8}, {1: 8}, {"font-size": None}, {"font-size": [8]}, {"font-size": {"value": 8}}])
def test_legend_style_invalid_rejected_before_mutation(invalid):
    editor = TWBEditor("")
    editor.add_worksheet("Plot")
    with pytest.raises(ValueError, match="legend_style"):
        editor.configure_worksheet_style("Plot", legend_style=invalid)
    assert not editor.root.xpath("//worksheet[@name='Plot']/table/style/style-rule[@element='legend']")

def test_legend_style_mcp_signature_and_forwarding(monkeypatch):
    import inspect
    from cwtwb.mcp import tools_workbook
    editor = TWBEditor("")
    editor.add_worksheet("Plot")
    assert inspect.signature(TWBEditor.configure_worksheet_style).parameters["legend_style"].default is None
    assert inspect.signature(tools_workbook.configure_worksheet_style).parameters["legend_style"].default is None
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_worksheet_style("Plot", legend_style={"font-size": 8})
    assert editor.root.xpath("//worksheet[@name='Plot']/table/style/style-rule[@element='legend']/format[@attr='font-size']/@value") == ["8"]


@pytest.mark.parametrize("direction", ["floating", "vertical"])
def test_absolute_flow_container_is_dashboard_peer_only_under_floating_parent(direction):
    editor = TWBEditor("")
    editor.add_calculated_field("Distance", "1")
    editor.add_worksheet("Plot")
    editor.configure_chart("Plot", mark_type="Circle", columns=["SUM(Distance)"], size="SUM(Distance)")
    editor.add_dashboard("Floating", width=700, height=700, layout={
        "type": "container", "direction": direction, "children": [
            {"type": "worksheet", "name": "Plot"},
            {"type": "container", "direction": "vertical", "absolute": {"x": 1000, "y": 60000, "w": 24000, "h": 35000}, "children": [
                {"type": "text", "text": "Distance", "fixed_size": 16},
                {"type": "size", "worksheet": "Plot", "field": "SUM(Distance)", "pane_index": 1, "fixed_size": 176},
            ]},
        ],
    })
    zones = editor.root.find("dashboards/dashboard[@name='Floating']/zones")
    flow = zones.find(".//zone[@type-v2='layout-flow'][@x='1000']")
    assert flow is not None
    assert (flow.getparent() is zones) is (direction == "floating")
    assert flow.get("param") == "vert" and flow.get("h") == "35000"
    assert [child.get("type-v2") for child in flow.findall("zone")] == ["text", "size"]
    size = flow.find("zone[@type-v2='size']")
    assert size.get("fixed-size") == "176" and size.get("pane-specification-id") == "1"
    assert size.getparent() is flow


def test_nonabsolute_flow_container_remains_nested_in_floating_root():
    editor = TWBEditor("")
    editor.add_dashboard("Nested", width=700, height=700, layout={"type": "container", "direction": "floating", "children": [
        {"type": "container", "direction": "vertical", "children": [{"type": "text", "text": "Tiled"}]},
    ]})
    zones = editor.root.find("dashboards/dashboard[@name='Nested']/zones")
    assert len(zones.findall("zone")) == 1
    root = zones.find("zone")
    assert root.get("type-v2") == "layout-basic"
    flow = root.find("zone")
    assert flow.get("type-v2") == "layout-flow" and flow.find("zone/formatted-text/run").text == "Tiled"


def test_toggle_still_rejects_tiled_root_flow_container():
    editor = TWBEditor("")
    editor.add_worksheet("Plot")
    editor.add_dashboard("Tiled", width=700, height=700, layout={"type": "container", "direction": "vertical", "children": [{"type": "worksheet", "name": "Plot"}]})
    with pytest.raises(ValueError, match="dedicated floating"):
        editor.add_dashboard_toggle_button("Tiled", ["Plot"])
