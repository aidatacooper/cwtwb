from datetime import date, datetime, timezone

import pytest

from cwtwb import TWBEditor


def editor_with_date(datatype="datetime"):
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Event Date",
        "#2020-01-01#",
        datatype=datatype,
        role="dimension",
        field_type="ordinal",
    )
    return editor


@pytest.mark.parametrize(
    "member,expected",
    [
        (datetime(2020, 2, 3, 4, 5, 6), "#2020-02-03 04:05:06#"),
        (date(2020, 2, 3), "#2020-02-03 00:00:00#"),
        ("2020-02-03T04:05:06", "#2020-02-03 04:05:06#"),
        ("2020-02-03", "#2020-02-03 00:00:00#"),
    ],
)
def test_datetime_members_use_native_date_literals(member, expected):
    editor = editor_with_date()
    editor.add_set("Picked", "Event Date", members=[member])
    assert (
        editor.root.find(".//group[@name='[Picked]']/groupfilter").get("member")
        == expected
    )


@pytest.mark.parametrize("member", [date(2020, 2, 3), "2020-02-03"])
def test_date_members_use_native_date_literals(member):
    editor = editor_with_date("date")
    editor.add_set("Picked", "Event Date", members=[member])
    assert (
        editor.root.find(".//group[@name='[Picked]']/groupfilter").get("member")
        == "#2020-02-03#"
    )


@pytest.mark.parametrize(
    "member",
    ["not-a-date", "2020-02-31", 42, True, datetime(2020, 1, 1, tzinfo=timezone.utc)],
)
def test_invalid_date_members_leave_datasource_unchanged(member):
    editor = editor_with_date()
    from lxml import etree

    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.add_set("Picked", "Event Date", members=[member])
    assert etree.tostring(editor.root) == before


def test_multiple_dates_preserve_union_and_datetime_precision():
    editor = editor_with_date()
    editor.add_set(
        "Picked",
        "Event Date",
        members=["2020-01-01", datetime(2020, 1, 2, 3, 4, 5, 6000)],
    )
    members = editor.root.findall(
        ".//group[@name='[Picked]']/groupfilter[@function='union']/groupfilter"
    )
    assert [m.get("member") for m in members] == [
        "#2020-01-01 00:00:00#",
        "#2020-01-02 03:04:05.006000#",
    ]


@pytest.mark.parametrize("alignment", ["left", "right"])
def test_native_axis_unit_bar_alignment(alignment):
    editor = TWBEditor("")
    editor.add_worksheet("Bars")
    editor.configure_layered_chart(
        "Bars",
        columns=["EXACTDATE(Order Date)"],
        panes=[
            {
                "axis": "SUM(Sales)",
                "mark_type": "Bar",
                "mark_sizing": {
                    "mark-sizing-setting": "marks-scaling-on",
                    "mark-alignment": "mark-alignment-" + alignment,
                    "use-custom-mark-size": True,
                    "custom-mark-size-in-axis-units": 4.0,
                },
            }
        ],
    )
    node = editor.root.find(".//worksheet[@name='Bars']//mark-sizing")
    assert node.get("mark-alignment") == "mark-alignment-" + alignment
    assert node.get("custom-mark-size-in-axis-units") == "4.0"


def test_automatic_subtotals_restore_native_aggregate_context():
    editor = TWBEditor("")
    editor.add_calculated_field("Ratio", "SUM([Profit])/SUM([Sales])")
    editor.add_worksheet("Summary")
    editor.configure_chart(
        "Summary", mark_type="Text", rows=["Category"], label="Ratio"
    )
    editor.configure_subtotals(
        "Summary",
        measure_fields=["Ratio"],
        subtotal_fields=["Category"],
        aggregation="Average",
    )
    editor.configure_subtotals(
        "Summary",
        measure_fields=["Ratio"],
        subtotal_fields=["Category"],
        aggregation="Automatic",
    )
    worksheet = editor.root.find(".//worksheet[@name='Summary']")
    local_name = editor.field_registry._find_field("Ratio").local_name
    instance = worksheet.find(f".//column-instance[@column='{local_name}']")
    assert instance.get("visual-totals") is None
    assert ":vt" not in instance.get("name")
    assert len(worksheet.findall("table/subtotals/column")) == 1
    assert "vtavg" not in str(worksheet.find("table/rows").text)
