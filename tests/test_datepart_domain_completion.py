"""Complete source date domains when native datepart shelves are present."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


@pytest.fixture
def editor(tmp_path):
    data = tmp_path / "facts.csv"
    data.write_text("Date,Profit\n2020-01-01,10\n2020-01-03,-3\n", encoding="utf-8")
    e = TWBEditor("")
    e.set_csv_connection(str(data))
    e.add_calculated_field(
        "Day", "DATE([Date])", datatype="date", role="dimension", field_type="ordinal"
    )
    e.add_worksheet("Chart")
    return e


@pytest.mark.parametrize(
    "date_expression",
    [
        "YEAR(Day)",
        "QUARTER(Day)",
        "MONTH(Day)",
        "DAY(Day)",
        "DAYTRUNC(Day)",
        "ATTR(Day)",
    ],
)
def test_complete_used_datepart_source_domain(editor, date_expression):
    editor.configure_chart(
        "Chart", mark_type="GanttBar", columns=[date_expression], rows=["SUM(Profit)"]
    )
    source_before = etree.tostring(editor._datasource)
    editor.configure_worksheet_domain_range("Chart", ["[Day]", "[Day]"])
    editor.configure_worksheet_domain_range("Chart", ["[Day]"])
    table = editor._find_worksheet("Chart").find("table")
    columns = table.findall("show-full-range/column")
    assert len(columns) == 1
    assert columns[0].text.endswith(
        editor.field_registry.parse_expression("[Day]").column_local_name
    )
    assert "none:" not in columns[0].text
    assert etree.tostring(editor._datasource) == source_before
    editor.configure_worksheet_domain_range("Chart", [])
    assert table.find("show-full-range") is None


def test_reject_unused_date_and_nondate_without_mutation(editor):
    editor.configure_chart("Chart", mark_type="Bar", columns=["SUM(Profit)"])
    table = editor._find_worksheet("Chart").find("table")
    before = etree.tostring(table)
    for expression in ["[Day]", "Profit", "MONTH(Day)"]:
        with pytest.raises(ValueError):
            editor.configure_worksheet_domain_range("Chart", [expression])
        assert etree.tostring(table) == before


def test_numeric_date_aggregation_does_not_complete_domain(editor):
    editor.configure_chart(
        "Chart", mark_type="Bar", columns=["MIN(Day)"], rows=["SUM(Profit)"]
    )
    with pytest.raises(ValueError, match="present in"):
        editor.configure_worksheet_domain_range("Chart", ["[Day]"])
