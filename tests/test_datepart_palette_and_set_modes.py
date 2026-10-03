"""Synthetic regressions for numeric temporal palettes and native set modes."""

import pytest
from cwtwb import TWBEditor


def test_set_tooltip_keeps_native_membership_instance():
    editor = TWBEditor("")
    editor.add_set("Selected Regions", "Region", members=["East"])
    editor.add_worksheet("Membership")
    editor.configure_chart(
        "Membership",
        mark_type="Bar",
        rows=["Region"],
        columns=["SUM(Sales)"],
        tooltip=["Selected Regions"],
    )
    worksheet = editor.root.find(".//worksheet[@name='Membership']")
    encoding = worksheet.find(".//encodings/tooltip")
    assert "[io:Selected Regions:nk]" in encoding.get("column")
    assert not worksheet.xpath(
        ".//column-instance[@derivation='Attribute'][@column='[Selected Regions]']"
    )


@pytest.mark.parametrize(
    "expression,values",
    [
        ("YEAR(Order Date)", [2018, 2019]),
        ("QUARTER(Order Date)", [1]),
        ("MONTH(Order Date)", [2, 3]),
        ("DAY(Order Date)", [10]),
        ("WEEK(Order Date)", [4]),
        ("WEEKDAY(Order Date)", [2]),
    ],
)
def test_discrete_datepart_filter_members_are_numeric(expression, values):
    editor = TWBEditor("")
    editor.add_worksheet("Dates")
    editor.configure_layered_chart(
        "Dates",
        columns=[expression],
        panes=[
            {
                "mark_type": "Bar",
                "axis": "SUM(Sales)",
                "color": expression,
                "color_map": {str(values[0]): "#123456"},
            }
        ],
        filters=[{"column": expression, "type": "categorical", "values": values}],
    )
    worksheet = editor.root.find(".//worksheet[@name='Dates']")
    assert [
        node.get("member")
        for node in worksheet.findall(".//filter//groupfilter[@function='member']")
    ] == [str(value) for value in values]
    assert editor.root.find(".//encoding[@attr='color']/map/bucket").text == str(
        values[0]
    )


@pytest.mark.parametrize(
    "expression,value",
    [
        ("YEAR(Event Date)", 2020),
        ("QUARTER(Event Date)", 2),
        ("MONTH(Event Date)", 6),
        ("DAY(Event Date)", 3),
        ("WEEK(Event Date)", 23),
        ("WEEKDAY(Event Date)", 4),
    ],
)
def test_datepart_palette_uses_numeric_member(expression, value):
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Event Date",
        "MAKEDATE(2020,6,3)",
        datatype="date",
        role="dimension",
        field_type="ordinal",
    )
    editor.set_datasource_color_palette(expression, {str(value): "#123456"})
    instance = editor.field_registry.parse_expression(expression)
    bucket = editor.root.find(
        "datasources/datasource/style/style-rule/encoding/map/bucket"
    )
    assert bucket.text == str(value)
    assert bucket.getparent().getparent().get("field") == instance.instance_name


def test_full_date_and_string_palette_members_remain_quoted():
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Event Date",
        "MAKEDATE(2020,6,3)",
        datatype="date",
        role="dimension",
        field_type="ordinal",
    )
    editor.add_calculated_field("Status", "'2020'", datatype="string", role="dimension")
    editor.set_datasource_color_palette("Event Date", {"2020-06-03": "#123456"})
    editor.set_datasource_color_palette("Status", {"2020": "#abcdef"})
    assert [
        b.text
        for b in editor.root.findall(
            "datasources/datasource/style/style-rule/encoding/map/bucket"
        )
    ] == ['"2020-06-03"', '"2020"']


@pytest.mark.parametrize("mode", ["assign", "add", "remove"])
def test_set_selection_mode_is_native_direct_element(mode):
    editor = TWBEditor("")
    editor.add_calculated_field("Category", "'a'", datatype="string", role="dimension")
    editor.add_set("Selection", "Category", members=[])
    editor.add_worksheet("Marks")
    editor.configure_chart("Marks", mark_type="Text", rows=["Category"])
    editor.add_dashboard("Dashboard", worksheet_names=["Marks"])
    editor.add_dashboard_set_action(
        "Dashboard",
        "Marks",
        "Selection",
        event_type="on-select",
        single_select=True,
        selection_mode=mode,
    )
    action = editor.root.find("actions/edit-group-action")
    if mode == "assign":
        assert action.find("add-or-remove-marks") is None
        assert (
            action.find("params/param[@name='add-or-remove-marks']").get("value")
            == mode
        )
        assert (
            editor.root.find("document-format-change-manifest/SetMembershipControl")
            is None
        )
    else:
        assert action.find("add-or-remove-marks").get("value") == mode
        assert action.find("params/param[@name='add-or-remove-marks']") is None
        assert list(action).index(action.find("add-or-remove-marks")) < list(
            action
        ).index(action.find("params"))
        assert (
            editor.root.find("document-format-change-manifest/SetMembershipControl")
            is not None
        )
    assert action.find("single-select").get("value") == "true"
    assert (
        action.find("params/param[@name='selection-clear-set-option']").get("value")
        == "exclude-all"
    )
