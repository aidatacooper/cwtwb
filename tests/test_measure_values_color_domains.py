"""Synthetic multi-measure colors retain native marks and independent domains."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def make():
    e = TWBEditor("")
    e.add_calculated_field(
        "Group", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Metric", "1.0")
    e.add_calculated_field("Other", "-2.0")
    e.add_worksheet("Table")
    return e


@pytest.mark.parametrize("mark", ["Square", "Text", "Automatic"])
def test_virtual_color_retains_measure_shelves_and_no_physical_column(mark, tmp_path):
    e = make()
    e.configure_chart(
        "Table",
        mark_type=mark,
        rows=["Group"],
        color="Multiple Values",
        detail="Group",
        measure_values=["SUM(Metric)", "SUM(Other)"],
        separate_measure_domains=True,
    )
    p = e.root.find(".//worksheet/table/panes/pane")
    assert p.find("mark").get("class") == ("Text" if mark == "Automatic" else mark)
    for kind in ["text", "color"]:
        v = p.find("encodings/" + kind)
        assert v.get("column").endswith(".[Multiple Values]")
        assert v.get("separate-domains") == "true"
    assert p.find("encodings/lod") is not None
    assert e.field_registry.parse_expression("Group").instance_name in e.root.findtext(
        ".//worksheet/table/rows"
    )
    assert (
        e.root.find(".//datasources/datasource/column[@caption='Multiple Values']")
        is None
    )
    e.configure_worksheet_style(
        "Table",
        color_style={"field": "SUM(Other)", "palette": "red_black_10_0", "center": 0},
    )
    e.save(str(tmp_path / "synthetic.twb"))


def test_existing_color_and_tooltip_not_discarded_by_measure_values():
    e = make()
    e.configure_chart(
        "Table",
        mark_type="Text",
        rows=["Group"],
        color="Group",
        detail="Group",
        tooltip=["SUM(Metric)"],
        measure_values=["SUM(Metric)"],
    )
    p = e.root.find(".//worksheet/table/panes/pane")
    assert all(
        p.find("encodings/" + kind) is not None
        for kind in ["color", "lod", "tooltip", "text"]
    )
    assert p.find("encodings/text").get("separate-domains") is None


@pytest.mark.parametrize("value", [None, "true", 1])
def test_invalid_domains_fail_without_changing_worksheet(value):
    e = make()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError, match="boolean"):
        e.configure_chart(
            "Table", measure_values=["SUM(Metric)"], separate_measure_domains=value
        )
    assert etree.tostring(e.root) == before


def test_separate_domains_require_virtual_measure_color():
    e = make()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError, match="requires"):
        e.configure_chart(
            "Table",
            mark_type="Text",
            measure_values=["SUM(Metric)"],
            separate_measure_domains=True,
        )
    assert etree.tostring(e.root) == before


def test_layered_virtual_color_and_text_share_independent_domains(tmp_path):
    e = make()
    e.configure_layered_chart(
        "Table",
        rows=["Group"],
        panes=[
            {
                "mark_type": "Square",
                "axis": "Multiple Values",
                "measure_values": ["SUM(Metric)", "SUM(Other)"],
                "color": "Multiple Values",
                "label": "Multiple Values",
                "separate_measure_domains": True,
            }
        ],
    )
    p = e.root.find(".//worksheet/table/panes/pane")
    for kind in ["text", "color"]:
        v = p.find("encodings/" + kind)
        assert v.get("column").endswith(".[Multiple Values]")
        assert v.get("separate-domains") == "true"
    e.save(str(tmp_path / "layered.twb"))


def test_mcp_forwards_domains(monkeypatch):
    from cwtwb.mcp import tools_workbook

    e = make()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    tools_workbook.configure_chart(
        "Table",
        mark_type="Square",
        rows=["Group"],
        color="Multiple Values",
        measure_values=["SUM(Metric)"],
        separate_measure_domains=True,
    )
    assert e.root.find(".//pane/encodings/color").get("separate-domains") == "true"
