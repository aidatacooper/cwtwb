from cwtwb.capability_registry import get_capability
from cwtwb.mcp import tools_workbook
from cwtwb.twb_analyzer import TWBAnalyzer


def test_add_reference_line_authors_gantt_reference_line(editor):
    editor.add_calculated_field(
        "Monthly Average",
        "SUM([Sales]) / COUNTD([Order Date])",
        datatype="real",
    )
    editor.add_calculated_field(
        "Overall Average",
        "{ FIXED : SUM([Sales]) } / { FIXED : COUNTD([Order Date]) }",
        datatype="real",
    )
    editor.add_calculated_field(
        "Difference",
        "[Monthly Average] - [Overall Average]",
        datatype="real",
    )
    editor.add_worksheet("Higher Orders")
    editor.configure_chart(
        "Higher Orders",
        mark_type="GanttBar",
        columns=["MONTH(Order Date)"],
        rows=["Monthly Average"],
        size="Difference",
    )

    result = editor.add_reference_line(
        "Higher Orders",
        axis_field="Monthly Average",
        value_field="Overall Average",
        tooltip="Overall average = <Value>",
    )

    assert "Added reference line" in result
    worksheet = editor._find_worksheet("Higher Orders")
    reference_line = worksheet.find(".//reference-line")
    assert reference_line is not None
    assert "usr:" in reference_line.get("axis-column")
    assert "usr:" in reference_line.get("value-column")
    assert reference_line.get("scope") == "per-pane"
    assert reference_line.get("tooltip") == "Overall average = <Value>"
    value_instance = reference_line.get("value-column").rsplit(".", 1)[-1]
    assert worksheet.find(
        f".//column-instance[@name='{value_instance}']"
    ) is not None


def test_loaded_calculation_formula_and_agg_expression_are_preserved(
    editor, tmp_path
):
    editor.add_calculated_field(
        "Aggregate Calculation",
        "SUM([Sales]) / COUNTD([Order Date])",
        datatype="real",
    )
    template = tmp_path / "aggregate-calculation.twb"
    editor.save(template, validate=False)
    reopened = type(editor).open_existing(template)
    field = reopened.field_registry._find_field("Aggregate Calculation")
    assert "SUM(" in field.formula
    assert "COUNTD(" in field.formula
    instance = reopened.field_registry.parse_expression(
        "AGG(Aggregate Calculation)"
    )
    assert instance.derivation == "User"
    assert instance.instance_name.startswith("[usr:")


def test_reference_line_mcp_and_capability_analysis(editor, tmp_path, monkeypatch):
    editor.add_worksheet("Higher Orders")
    editor.configure_chart(
        "Higher Orders",
        mark_type="GanttBar",
        rows=["SUM(Sales)"],
    )
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    result = tools_workbook.add_reference_line(
        "Higher Orders",
        axis_field="SUM(Sales)",
        value_field="SUM(Sales)",
    )
    assert "Added reference line" in result

    output = tmp_path / "reference-line.twb"
    editor.save(output, validate=False)
    report = TWBAnalyzer().analyze(output)
    detected = {(item.kind, item.canonical, item.level) for item in report.detected}
    assert ("chart", "GanttBar", "advanced") in detected
    assert ("feature", "Reference Line", "advanced") in detected
    assert report.summary["unsupported"] == 0
    assert get_capability("chart", "GanttBar").level == "advanced"
    assert get_capability("feature", "reference-line").level == "advanced"
