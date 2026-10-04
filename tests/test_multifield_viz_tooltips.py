"""Compound viz-in-tooltip filters retain the identity of every dimension."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def setup_editor():
    e = TWBEditor("")
    for name, formula, datatype in [
        ("Country", "'A'", "string"),
        ("Year", "2020", "integer"),
    ]:
        e.add_calculated_field(
            name, formula, datatype=datatype, role="dimension", field_type="nominal"
        )
    e.add_parameter("Multiplier", default_value="1")
    e.add_calculated_field("Value", "1.0 * [Parameters].[Multiplier]")
    for name in ("Source", "Detail"):
        e.add_worksheet(name)
        e.configure_chart(
            name, mark_type="Text", rows=["Country", "Year"], label="SUM(Value)"
        )
    return e


def test_two_dimensions_are_crossjoined_and_context_is_preserved(tmp_path):
    e = setup_editor()
    spec = {
        "name": "Detail",
        "filter_fields": ["Country", "Year"],
        "filter_context": True,
    }
    e.configure_custom_tooltip("Source", [{"sheet": spec}])
    e.configure_custom_tooltip("Source", [{"sheet": spec}])
    target = e.root.find("worksheets/worksheet[@name='Detail']/table/view")
    filters = target.findall("filter")
    assert len(filters) == 1 and filters[0].get("context") == "true"
    crossjoin = filters[0].find("groupfilter")
    assert crossjoin.get("function") == "crossjoin"
    expected = [e.field_registry._find_field(n).local_name for n in ("Country", "Year")]
    assert [g.get("level") for g in crossjoin] == expected
    assert all(g.get("function") == "level-members" for g in crossjoin)
    group = e.root.find("datasources/datasource/group[@hidden='true']")
    assert [g.get("level") for g in group.find("groupfilter")] == expected
    assert (
        crossjoin.get("{http://www.tableausoftware.com/xml/user}ui-action-filter")
        == "[Action - Detail]"
    )
    embed = e.root.find(
        "worksheets/worksheet[@name='Source']/table/panes/pane/customized-tooltip/formatted-text/run"
    ).text
    assert embed.count("<[") == 2
    children = list(target)
    assert all(
        children.index(d) < children.index(filters[0])
        for d in target.findall("datasource-dependencies")
    )
    path = tmp_path / "compound-tooltip.twb"
    e.save(str(path))
    assert (
        etree.parse(str(path)).find(".//filter/groupfilter[@function='crossjoin']")
        is not None
    )
    spec["filter_context"] = False
    e.configure_custom_tooltip("Source", [{"sheet": spec}])
    assert filters[0].get("context") is None


@pytest.mark.parametrize("context", ["true", 1, None])
def test_context_option_must_be_boolean(context):
    e = setup_editor()
    with pytest.raises(ValueError, match="filter_context"):
        e.configure_custom_tooltip(
            "Source",
            [
                {
                    "sheet": {
                        "name": "Detail",
                        "filter_fields": ["Country", "Year"],
                        "filter_context": context,
                    }
                }
            ],
        )


def test_mcp_forwards_compound_sheet_spec(monkeypatch):
    from cwtwb.mcp import tools_workbook

    e = setup_editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    tools_workbook.configure_custom_tooltip(
        "Source", [{"sheet": {"name": "Detail", "filter_fields": ["Country", "Year"]}}]
    )
    assert len(e.root.findall(".//filter/groupfilter/groupfilter")) == 2
