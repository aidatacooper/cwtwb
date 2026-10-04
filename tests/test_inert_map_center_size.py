"""Synthetic independent map interaction and centered size settings."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def editor():
    e = TWBEditor("")
    e.add_calculated_field(
        "State",
        "'California'",
        datatype="string",
        role="dimension",
        field_type="nominal",
    )
    e.add_worksheet("Map")
    return e


def layers():
    return [
        {"mark_type": "Map", "color": "SUM(Profit)", "inert": True},
        {
            "mark_type": "Circle",
            "color": "SUM(Profit)",
            "size": "SUM(Profit)",
            "inert": False,
            "tooltip": ["SUM(Profit)"],
        },
    ]


def test_each_map_layer_has_independent_native_interaction():
    e = editor()
    e.configure_chart("Map", "Map", geographic_field="State", map_layers=layers())
    panes = e.root.findall("worksheets/worksheet/table/panes/pane")
    assert [p.get("inert") for p in panes if p.get("id") in {"1", "2"}] == [
        "true",
        "false",
    ]
    assert panes[-1].find("encodings/tooltip") is not None
    assert e.root.find("worksheets/worksheet/table/tooltip-style") is None
    e.configure_worksheet_style(
        "Map",
        size_style={
            "type": "centersize",
            "field": "SUM(Profit)",
            "min": -10,
            "max": 100,
            "min_size": 0,
            "max_size": 1,
        },
    )
    encoding = e.root.find(".//encoding[@attr='size'][@type='centersize']")
    assert encoding.get("min") == "-10" and encoding.get("field-type") == "quantitative"


@pytest.mark.parametrize("value", ["true", 1, None])
def test_invalid_inert_does_not_change_worksheet(value):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError, match="inert"):
        e.configure_chart(
            "Map",
            "Map",
            geographic_field="State",
            map_layers=[{**layers()[0], "inert": value}],
        )
    assert etree.tostring(e.root) == before
