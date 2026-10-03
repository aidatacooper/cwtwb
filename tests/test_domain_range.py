"""Native full date range contracts with a synthetic wholly absent day."""

import pytest

from cwtwb import TWBEditor
from cwtwb.mcp import tools_workbook


@pytest.fixture
def editor(tmp_path):
    data = tmp_path / "sales.csv"
    data.write_text("Date,Sales\n2020-01-01,10\n2020-01-03,20\n", encoding="utf-8")
    e = TWBEditor("")
    e.set_csv_connection(str(data))
    e.add_calculated_field(
        "Day", "DATE([Date])", datatype="date", role="dimension", field_type="ordinal"
    )
    e.add_worksheet("Sales")
    e.configure_chart("Sales", mark_type="Line", columns=["[Day]"], rows=["SUM(Sales)"])
    return e


def test_exact_date_full_range_uses_raw_field_and_is_idempotent(editor):
    editor.configure_worksheet_domain_range("Sales", ["[Day]", "[Day]"])
    editor.configure_worksheet_domain_range("Sales", ["[Day]"])
    table = editor._find_worksheet("Sales").find("table")
    columns = table.findall("show-full-range/column")
    assert len(columns) == 1
    assert (
        columns[0].text
        == f"[{editor._datasource.get('name')}].{editor.field_registry.parse_expression('[Day]').column_local_name}"
    )
    assert "none:" not in columns[0].text
    editor.configure_worksheet_domain_range("Sales", [])
    assert table.find("show-full-range") is None


def test_rejects_nondate_month_or_unregistered_view_field_without_mutation(editor):
    for field in ["Sales", "MONTH(Day)"]:
        with pytest.raises(ValueError):
            editor.configure_worksheet_domain_range("Sales", [field])
    editor.add_calculated_field(
        "Other", "DATE([Date])", datatype="date", role="dimension", field_type="ordinal"
    )
    with pytest.raises(ValueError, match="present in"):
        editor.configure_worksheet_domain_range("Sales", ["[Other]"])
    assert editor._find_worksheet("Sales").find("table/show-full-range") is None


def test_mcp_forwards_full_range(editor, monkeypatch):
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    assert "1 fields" in tools_workbook.configure_worksheet_domain_range(
        "Sales", ["[Day]"]
    )
