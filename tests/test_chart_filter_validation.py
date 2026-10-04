"""Misspelled filter keys must never silently remove requested filtering."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


@pytest.mark.parametrize(
    "method", ["configure_chart", "configure_dual_axis", "configure_layered_chart"]
)
@pytest.mark.parametrize(
    "filters",
    [
        [{"field": "Category", "values": ["A"]}],
        [{}],
        [{"column": ""}],
        [None],
        "Category",
    ],
)
def test_invalid_filters_preserve_existing_worksheet(method, filters):
    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Value", "1.0")
    e.add_worksheet("Plot")
    e.configure_chart(
        "Plot", mark_type="Bar", rows=["Category"], columns=["SUM(Value)"]
    )
    before = etree.tostring(e.root)
    with pytest.raises(ValueError, match="filter"):
        getattr(e, method)("Plot", filters=filters)
    assert etree.tostring(e.root) == before


def test_valid_filter_is_rendered_and_mcp_rejects_misspelled_key(monkeypatch):
    from cwtwb.mcp import tools_workbook

    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_worksheet("Plot")
    e.configure_chart(
        "Plot", rows=["Category"], filters=[{"column": "Category", "values": ["A"]}]
    )
    assert (
        e.root.find("worksheets/worksheet/table/view/filter/groupfilter").get("member")
        == '"A"'
    )
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    with pytest.raises(ValueError, match="column"):
        tools_workbook.configure_chart(
            "Plot", filters=[{"field": "Category", "values": ["A"]}]
        )
