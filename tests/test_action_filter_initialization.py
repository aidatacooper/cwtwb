"""Synthetic native action initial-selection contracts without author workbooks."""

import pytest
from lxml import etree

from cwtwb import TWBEditor
from cwtwb.action_filter_initialization import initialize_dashboard_filter_action


def editor():
    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'Alpha'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Value", "1.0")
    for sheet in ["Selector", "Target", "Other"]:
        e.add_worksheet(sheet)
        e.configure_chart(
            sheet, mark_type="Text", rows=["Category"], label="SUM(Value)"
        )
    e.add_dashboard("Dashboard", worksheet_names=["Selector", "Target", "Other"])
    e.add_dashboard_action(
        "Dashboard",
        "filter",
        source_sheet="Selector",
        target_sheet="Target",
        fields=["Category"],
        caption="Choose Category",
    )
    return e


def test_initial_members_bind_real_action_and_only_target():
    e = editor()
    initialize_dashboard_filter_action(
        e, "Dashboard", "Choose Category", {"Category": ["Alpha", "Beta"]}
    )
    action = e.root.find("actions/action")
    group = e.root.find("datasources/datasource/group")
    assert group.get("name") == "[Action (Category)]"
    assert (
        group.find("groupfilter/groupfilter").get("level")
        == e.field_registry._find_field("Category").local_name
    )
    target = e.root.find('worksheets/worksheet[@name="Target"]/table/view')
    f = target.find("filter")
    selection = f.find("groupfilter")
    assert selection.get(
        "{http://www.tableausoftware.com/xml/user}ui-action-filter"
    ) == action.get("name")
    assert {m.get("member") for m in selection.findall("groupfilter")} == {
        '"Alpha"',
        '"Beta"',
    }
    assert not e.root.find('worksheets/worksheet[@name="Other"]/table/view').findall(
        "filter"
    )
    initialize_dashboard_filter_action(
        e, "Dashboard", action.get("name"), {"Category": ["Beta"]}
    )
    assert len(target.findall("filter")) == 1
    assert target.find("filter/groupfilter").get("member") == '"Beta"'
    assert len(e.root.findall("datasources/datasource/group")) == 1


@pytest.mark.parametrize(
    "members",
    [
        {},
        {"Category": []},
        {"Category": [1]},
        {"Category": ["Alpha", "Alpha"]},
        {"Unknown": ["Alpha"]},
    ],
)
def test_invalid_members_leave_xml_unchanged(members):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises((ValueError, TypeError)):
        initialize_dashboard_filter_action(e, "Dashboard", "Choose Category", members)
    assert etree.tostring(e.root) == before


def test_mapped_target_and_multiple_dimensions():
    e = editor()
    e.add_calculated_field(
        "Other Category",
        "'North'",
        datatype="string",
        role="dimension",
        field_type="nominal",
    )
    e.add_calculated_field(
        "Enabled", "TRUE", datatype="boolean", role="dimension", field_type="nominal"
    )
    e.configure_chart(
        "Target",
        mark_type="Text",
        rows=["Other Category", "Enabled"],
        label="SUM(Value)",
    )
    e.add_dashboard_action(
        "Dashboard",
        "filter",
        source_sheet="Selector",
        target_sheet="Target",
        field_mappings={"Category": "Other Category", "Enabled": "Enabled"},
        caption="Mapped",
    )
    initialize_dashboard_filter_action(
        e, "Dashboard", "Mapped", {"Other Category": ["North"], "Enabled": [True]}
    )
    target = e.root.find('worksheets/worksheet[@name="Target"]/table/view')
    selection = target.find("filter/groupfilter")
    assert selection.get("function") == "crossjoin"
    assert len(selection.findall("groupfilter")) == 2
    assert selection.get(
        "{http://www.tableausoftware.com/xml/user}ui-action-filter"
    ) == e.root.findall("actions/action")[-1].get("name")


def test_non_filter_action_rejected_without_mutation():
    e = editor()
    e.add_dashboard_action(
        "Dashboard",
        "highlight",
        source_sheet="Selector",
        target_sheet="Target",
        fields=["Category"],
        caption="Highlight",
    )
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        initialize_dashboard_filter_action(
            e, "Dashboard", "Highlight", {"Category": ["Alpha"]}
        )
    assert etree.tostring(e.root) == before


def test_parameter_dependencies_precede_initialized_filter():
    e = editor()
    e.add_parameter("Threshold", datatype="integer", default_value="1")
    e.add_calculated_field("Adjusted Value", "[Value] + [Parameters].[Threshold]")
    e.configure_chart(
        "Target", mark_type="Text", rows=["Category"], label="SUM(Adjusted Value)"
    )
    e.initialize_dashboard_filter_action(
        "Dashboard", "Choose Category", {"Category": ["Alpha"]}
    )
    view = e.root.find('worksheets/worksheet[@name="Target"]/table/view')
    children = list(view)
    assert len(view.findall("datasource-dependencies")) == 2
    assert all(
        children.index(dep) < children.index(view.find("filter"))
        for dep in view.findall("datasource-dependencies")
    )
