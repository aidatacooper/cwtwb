import pytest
from lxml import etree

from cwtwb import TWBEditor


def test_phone_layout_is_automatic_and_derived_from_default_objects():
    editor = TWBEditor("")
    for name in ("First", "Second"):
        editor.add_worksheet(name)
        editor.configure_chart(name, mark_type="Text", label="SUM(Sales)")
    editor.add_dashboard(
        "Dashboard",
        width=1200,
        height=800,
        layout={
            "type": "container",
            "direction": "vertical",
            "children": [
                {"type": "text", "text": "Heading", "fixed_size": 40},
                {
                    "type": "container",
                    "direction": "horizontal",
                    "children": [
                        {"type": "worksheet", "name": "First"},
                        {"type": "worksheet", "name": "Second"},
                    ],
                },
            ],
        },
    )
    dashboard = editor.root.find(".//dashboard[@name='Dashboard']")
    before = etree.tostring(dashboard.find("zones"))
    editor.enable_automatic_phone_layout("Dashboard")
    editor.enable_automatic_phone_layout("Dashboard")
    phone = dashboard.find("devicelayouts/devicelayout")
    assert phone.get("auto-generated") == "true"
    assert phone.find("size").get("sizing-mode") == "vscroll"
    assert len(dashboard.findall("devicelayouts/devicelayout")) == 1
    assert etree.tostring(dashboard.find("zones")) == before
    leaves = phone.findall("zones/zone/zone/zone")
    assert [node.get("name") for node in leaves] == [None, "First", "Second"]
    assert [node.get("fixed-size") for node in leaves] == ["40", "280", "280"]
    assert [node.get("id") for node in leaves] == [
        node.get("id")
        for node in dashboard.findall("zones//zone")
        if node.find("zone") is None
    ]


@pytest.mark.parametrize("height", [True, 0, -1, "280"])
def test_phone_layout_rejects_invalid_height(height):
    with pytest.raises(ValueError):
        TWBEditor("").enable_automatic_phone_layout("Missing", height)


def test_combined_set_uses_native_dynamic_union():
    editor = TWBEditor("")
    editor.add_set("Top", "Category", basis_field="Sales", top_n=1)
    editor.add_set("Bottom", "Category", basis_field="Sales", top_n=1, direction="ASC")
    bottom = editor.root.find(
        ".//group[@name='[Bottom]']//groupfilter[@function='end']"
    )
    assert bottom.get("end") == "bottom"
    assert bottom.find("groupfilter[@function='order']").get("direction") == "DESC"
    editor.add_combined_set("Both", ["Top", "Bottom"])
    group = editor.root.find(".//group[@name='[Both]']")
    assert [
        node.get("field")
        for node in group.findall(
            "groupfilter[@function='union']/groupfilter[@function='reference']"
        )
    ] == ["[Top]", "[Bottom]"]
    editor.add_worksheet("Union")
    editor.configure_chart(
        "Union",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
        filters=[{"column": "Both", "values": [True]}],
    )
    assert editor.root.find(".//worksheet[@name='Union']//filter") is not None


def test_combined_set_rejects_different_grains_without_mutation():
    editor = TWBEditor("")
    editor.add_set("Categories", "Category", members=["Technology"])
    editor.add_set("Regions", "Region", members=["East"])
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.add_combined_set("Both", ["Categories", "Regions"])
    assert etree.tostring(editor.root) == before


def test_reference_line_can_bind_virtual_measure_values_axis():
    editor = TWBEditor("")
    editor.add_worksheet("Stack")
    editor.configure_layered_chart(
        "Stack",
        rows=["Category"],
        panes=[
            {
                "axis": "Multiple Values",
                "mark_type": "Bar",
                "measure_values": ["SUM(Sales)", "SUM(Profit)"],
            }
        ],
    )
    editor.add_reference_line(
        "Stack", axis_field="Multiple Values", value_field="SUM(Sales)"
    )
    line = editor.root.find(".//worksheet[@name='Stack']//reference-line")
    assert "[Multiple Values]" in line.get("axis-column")
    assert not editor.root.xpath("//column-instance[@name='[Multiple Values]']")
