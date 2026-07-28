"""Case-level tests for hierarchy, densification, and average subtotals."""

from pathlib import Path

import pytest

from cwtwb.mcp import tools_workbook
from cwtwb.twb_editor import TWBEditor


@pytest.fixture
def editor():
    template = (
        Path(__file__).parents[1]
        / "src"
        / "cwtwb"
        / "references"
        / "superstore.twb"
    )
    return TWBEditor(template)


def _configure_null_average_view(editor: TWBEditor) -> None:
    editor.add_calculated_field(
        "#Orders in Date Range",
        "ZN(COUNTD([Order ID]))",
        datatype="integer",
        internal_name="[Calculation_OrdersInDateRange]",
    )
    editor.add_worksheet("Null Average")
    editor.configure_chart(
        "Null Average",
        mark_type="Square",
        columns=["WEEKDAY(Order Date)"],
        rows=["Category", "Sub-Category"],
        label="#Orders in Date Range",
        color="#Orders in Date Range",
    )


def test_add_hierarchy_writes_ordered_drill_path(editor):
    result = editor.add_hierarchy(
        "Category Hierarchy",
        ["Region", "State/Province", "City"],
    )

    drill_path = editor._datasource.find(
        "drill-paths/drill-path[@name='Category Hierarchy']"
    )
    assert "3 levels" in result
    assert [field.text for field in drill_path.findall("field")] == [
        "[Region (Orders)]",
        "[State/Province]",
        "[City (Orders)]",
    ]


def test_hierarchy_rejects_derived_and_duplicate_fields(editor):
    with pytest.raises(ValueError, match="bare dimension"):
        editor.add_hierarchy("Bad", ["YEAR(Order Date)", "Category"])
    with pytest.raises(ValueError, match="duplicated"):
        editor.add_hierarchy("Bad", ["Category", "Category"])


def test_enable_domain_completion_adds_index_to_detail(editor):
    _configure_null_average_view(editor)
    result = editor.enable_domain_completion("Null Average")

    worksheet = editor._find_worksheet("Null Average")
    column = editor._datasource.find(
        "column[@caption='Domain Completion Index']/calculation"
    )
    instance = worksheet.find(
        ".//column-instance[@column='[Calculation_DomainCompletionIndex]']"
    )
    lod = worksheet.find(".//pane/encodings/lod")

    assert "Enabled domain completion" in result
    assert column.get("formula") == "INDEX()"
    assert column.find("table-calc").attrib == {"ordering-type": "Rows"}
    assert instance.find("table-calc").attrib == {"ordering-type": "Rows"}
    assert lod is not None
    assert lod.get("column", "").endswith(
        ".[usr:Calculation_DomainCompletionIndex:qk]"
    )


def test_configure_average_subtotals_matches_donna_metadata(editor):
    _configure_null_average_view(editor)
    result = editor.configure_subtotals(
        "Null Average",
        measure_fields=["#Orders in Date Range"],
        aggregation="Average",
        subtotal_fields=["Sub-Category"],
        label="Avg.",
    )

    worksheet = editor._find_worksheet("Null Average")
    calculation = editor._datasource.find(
        "column[@caption='#Orders in Date Range']"
    )
    local_name = calculation.get("name")
    instance = worksheet.find(
        f".//column-instance[@column='{local_name}']"
    )
    label = worksheet.find(
        ".//style-rule[@element='header']/format"
        "[@attr='total-label'][@data-class='subtotal']"
    )

    assert "Average subtotals" in result
    assert instance.get("visual-totals") == "Avg"
    assert label.get("value") == "Avg."
    assert "Sub-Category" in label.get("field")


def test_case_c_features_survive_twbx_save(editor, tmp_path):
    editor.add_hierarchy(
        "Category Hierarchy",
        ["Region", "State/Province", "City"],
    )
    _configure_null_average_view(editor)
    editor.enable_domain_completion("Null Average")
    editor.configure_subtotals(
        "Null Average",
        measure_fields=["#Orders in Date Range"],
        aggregation="Average",
        subtotal_fields=["Sub-Category"],
    )

    output = tmp_path / "case-c-features.twbx"
    editor.save(output)
    reopened = TWBEditor.open_existing(output)

    assert reopened._datasource.find(
        "drill-paths/drill-path[@name='Category Hierarchy']"
    ) is not None
    worksheet = reopened._find_worksheet("Null Average")
    assert worksheet.find(".//column-instance[@visual-totals='Avg']") is not None
    assert worksheet.find(".//pane/encodings/lod") is not None


def test_mcp_surface_exposes_case_c_features(editor, monkeypatch):
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    assert "Added hierarchy" in tools_workbook.add_hierarchy(
        "Category Hierarchy",
        ["Category", "Sub-Category"],
    )
    _configure_null_average_view(editor)
    assert "Enabled domain completion" in tools_workbook.enable_domain_completion(
        "Null Average"
    )
    assert "Average subtotals" in tools_workbook.configure_subtotals(
        "Null Average",
        ["#Orders in Date Range"],
        subtotal_fields=["Sub-Category"],
    )
