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
