"""Synthetic date/date-time fiscal metadata on active datasource dependencies."""

import pytest
from lxml import etree

from cwtwb import TWBEditor
from cwtwb.field_date_properties import set_field_fiscal_year_start


def test_fiscal_property_updates_current_and_future_date_dependencies():
    e = TWBEditor("")
    e.add_calculated_field(
        "Day", "#2020-10-01#", datatype="date", role="dimension", field_type="ordinal"
    )
    e.add_worksheet("Before")
    e.configure_chart("Before", columns=["YEAR(Day)"], rows=["SUM(Sales)"])
    set_field_fiscal_year_start(e, "Day", 10)
    e.add_worksheet("After")
    e.configure_chart("After", columns=["MONTH(Day)"], rows=["SUM(Sales)"])
    local = e.field_registry._find_field("Day").local_name
    columns = e.root.xpath("//column[@name=$name]", name=local)
    assert len(columns) == 3 and all(
        c.get("fiscal-year-start") == "10" for c in columns
    )
    set_field_fiscal_year_start(e, "Day", 1)
    assert all(c.get("fiscal-year-start") == "1" for c in columns)


def test_rejects_months_and_non_date_without_xml_changes():
    e = TWBEditor("")
    e.add_calculated_field(
        "Stamp", "NOW()", datatype="datetime", role="dimension", field_type="ordinal"
    )
    before = etree.tostring(e.root)
    for month in [True, False, 0, 13, 1.5, "10"]:
        with pytest.raises(ValueError):
            set_field_fiscal_year_start(e, "Stamp", month)
        assert etree.tostring(e.root) == before
    with pytest.raises(ValueError, match="date or datetime"):
        set_field_fiscal_year_start(e, "Sales", 10)
    assert etree.tostring(e.root) == before
    set_field_fiscal_year_start(e, "Stamp", 10)
    assert e._datasource.xpath("column[@fiscal-year-start='10']")


def test_physical_date_property_survives_future_layered_chart(tmp_path):
    source = tmp_path / "dates.csv"
    source.write_text("Date,Revenue\n2020-10-01,12\n", encoding="utf-8")
    editor = TWBEditor("")
    editor.set_csv_connection(
        str(source),
        fields=[
            {"name": "Date", "datatype": "date"},
            {"name": "Revenue", "datatype": "real"},
        ],
    )
    editor.set_field_fiscal_year_start("Date", 10)
    editor.add_worksheet("Fiscal Trend")
    editor.configure_layered_chart(
        "Fiscal Trend",
        columns=["MONTH(Date)"],
        panes=[{"mark_type": "Line", "axis": "SUM(Revenue)", "detail": "YEAR(Date)"}],
    )
    local = editor.field_registry._find_field("Date").local_name
    copies = editor.root.xpath("//column[@name=$name]", name=local)
    assert len(copies) == 2
    assert all(column.get("fiscal-year-start") == "10" for column in copies)
