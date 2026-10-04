"""Label range fields must refer to native worksheet instances, not captions."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


@pytest.mark.parametrize("per_pane", [False, "list", "mapping"])
@pytest.mark.parametrize(
    "attribute", ["mark-labels-range-field", "mark_labels_range_field"]
)
def test_range_label_field_resolves_calculated_aggregate(per_pane, attribute, tmp_path):
    e = TWBEditor("")
    e.add_calculated_field("Amount", "1.0")
    e.add_calculated_field("Display Measure", "SUM([Amount])")
    e.add_worksheet("Line")
    e.configure_layered_chart(
        "Line", panes=[{"axis": "AGG(Display Measure)", "mark_type": "Line"}]
    )
    style = {attribute: "AGG(Display Measure)", "mark-labels-mode": "minmax"}
    kwargs = {"pane_mark_style": style}
    if per_pane == "list":
        kwargs = {"panes_style": [{"mark_style": style}]}
    elif per_pane == "mapping":
        kwargs = {"panes_style": {"0": {"mark_style": style}}}
    e.configure_worksheet_style("Line", **kwargs)
    e.configure_worksheet_style("Line", **kwargs)
    formats = e.root.xpath(
        "//panes/pane/style/style-rule[@element='mark']/format[@attr='mark-labels-range-field']"
    )
    assert len(formats) == 1
    expected = e.field_registry.resolve_full_reference(
        e.field_registry.parse_expression("AGG(Display Measure)").instance_name
    )
    assert formats[0].get("value") == expected
    assert style[attribute] == "AGG(Display Measure)"
    e.save(str(tmp_path / "labels.twb"))


def test_unknown_range_label_field_leaves_style_unchanged():
    e = TWBEditor("")
    e.add_calculated_field("Amount", "1.0")
    e.add_worksheet("Line")
    e.configure_chart("Line", mark_type="Line", rows=["SUM(Amount)"])
    before = etree.tostring(e.root)
    with pytest.raises(KeyError, match="Unknown field"):
        e.configure_worksheet_style(
            "Line", pane_mark_style={"mark-labels-range-field": "Unknown Measure"}
        )
    assert etree.tostring(e.root) == before


@pytest.mark.parametrize(
    "attribute", ["mark-labels-range-field", "mark_labels_range_field"]
)
def test_layered_pane_style_resolves_range_field_and_declares_dependency(
    attribute, tmp_path
):
    e = TWBEditor("")
    e.add_calculated_field("Amount", "1.0")
    e.add_calculated_field("Display Measure", "SUM([Amount])")
    e.add_worksheet("Line")
    e.configure_layered_chart(
        "Line",
        panes=[
            {
                "axis": "SUM(Amount)",
                "mark_type": "Line",
                "mark_style": {attribute: "AGG(Display Measure)"},
            }
        ],
    )
    ci = e.field_registry.parse_expression("AGG(Display Measure)")
    assert e.root.xpath(
        "//panes/pane/style/style-rule/format[@attr='mark-labels-range-field']"
    )[0].get("value") == e.field_registry.resolve_full_reference(ci.instance_name)
    assert (
        e.root.find(
            f".//datasource-dependencies/column-instance[@name='{ci.instance_name}']"
        )
        is not None
    )
    e.save(str(tmp_path / "layered-labels.twb"))


def test_mcp_forwards_public_label_range_expression(monkeypatch):
    from cwtwb.mcp import tools_workbook

    e = TWBEditor("")
    e.add_calculated_field("Amount", "1.0")
    e.add_worksheet("Line")
    e.configure_chart("Line", mark_type="Line", rows=["SUM(Amount)"])
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    tools_workbook.configure_worksheet_style(
        "Line", pane_mark_style={"mark-labels-range-field": "SUM(Amount)"}
    )
    ci = e.field_registry.parse_expression("SUM(Amount)")
    assert e.root.xpath("//format[@attr='mark-labels-range-field']")[0].get(
        "value"
    ) == e.field_registry.resolve_full_reference(ci.instance_name)
