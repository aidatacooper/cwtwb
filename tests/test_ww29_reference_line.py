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
    assert "Calculation_" in reference_line.get("value-column")
    assert reference_line.get("value-column").endswith(":qk]")
    assert reference_line.get("scope") == "per-pane"
    # Tableau Desktop's current workbook schema rejects both ``tooltip`` and
    # ``tooltip-type`` on a reference-line.  The public API retains the
    # argument for compatibility, but authors a portable minimal element.
    assert reference_line.get("tooltip") is None
    assert reference_line.get("tooltip-type") is None
    assert reference_line.get("z-order") == "1"
    lod_columns = {
        item.get("column") for item in worksheet.findall(".//pane/encodings/lod")
    }
    assert reference_line.get("value-column") in lod_columns
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


def test_reference_lines_increment_z_order(editor):
    editor.add_worksheet("Multiple reference lines")
    editor.configure_chart(
        "Multiple reference lines", mark_type="Line", rows=["SUM(Sales)"]
    )
    for _ in range(3):
        editor.add_reference_line(
            "Multiple reference lines",
            axis_field="SUM(Sales)",
            value_field="SUM(Sales)",
        )

    lines = editor._find_worksheet("Multiple reference lines").findall(
        ".//reference-line"
    )
    assert [line.get("id") for line in lines] == ["refline0", "refline1", "refline2"]
    assert [line.get("z-order") for line in lines] == ["1", "2", "3"]
    lod_columns = editor._find_worksheet("Multiple reference lines").findall(
        ".//pane/encodings/lod"
    )
    assert len(lod_columns) == 1


def test_configure_custom_tooltip_authors_rich_field_runs(editor):
    editor.add_worksheet("Tooltip")
    editor.configure_chart(
        "Tooltip", mark_type="Circle", columns=["MONTH(Order Date)"],
        tooltip=["SUM(Sales)"],
    )
    editor.configure_custom_tooltip(
        "Tooltip",
        [
            {"field": "MONTH(Order Date)", "bold": True, "fontsize": 9},
            {"text": "\n"},
            {"text": "Sales:\t", "fontcolor": "#666666", "fontsize": 9},
            {"field": "SUM(Sales)", "bold": True, "fontcolor": "#666666", "fontsize": 9},
        ],
    )

    tooltip = editor._find_worksheet("Tooltip").find(
        ".//pane/customized-tooltip/formatted-text"
    )
    runs = tooltip.findall("run")
    assert len(runs) == 4
    assert runs[0].get("bold") == "true"
    assert runs[1].text == "\u00c6\n"
    assert "sum:Sales" in runs[3].text


def test_configure_reference_line_style_authors_dotted_teal_line(editor):
    editor.add_worksheet("Styled reference line")
    editor.configure_chart(
        "Styled reference line", mark_type="Line", rows=["SUM(Sales)"]
    )
    editor.add_reference_line(
        "Styled reference line", axis_field="SUM(Sales)",
        value_field="SUM(Sales)", probability=None,
    )
    editor.configure_reference_line_style(
        "Styled reference line", "refline0",
        {"line-pattern-only": "dotted", "stroke-color": "#499894"},
    )

    formats = {
        item.get("attr"): item.get("value")
        for item in editor._find_worksheet("Styled reference line").findall(
            ".//style-rule[@element='refline']/format[@id='refline0']"
        )
    }
    assert formats == {
        "line-pattern-only": "dotted", "stroke-color": "#499894"
    }
