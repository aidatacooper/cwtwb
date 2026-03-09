from pathlib import Path

from cwtwb.twb_analyzer import analyze_workbook
from cwtwb.twb_editor import TWBEditor
from cwtwb.server import diff_template_gap



def test_analyze_generated_workbook_detects_core_and_advanced():
    editor = TWBEditor("")

    editor.add_worksheet("Sales")
    editor.configure_chart(
        "Sales",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
        filters=[{"column": "Category"}],
    )

    editor.add_worksheet("Trend")
    editor.configure_chart(
        "Trend",
        mark_type="Line",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Sales)"],
    )

    editor.add_parameter(
        name="Target Profit",
        datatype="real",
        default_value="10000",
        domain_type="range",
        min_value="0",
        max_value="100000",
        granularity="5000",
    )

    layout = {
        "type": "container",
        "direction": "horizontal",
        "children": [
            {
                "type": "container",
                "direction": "vertical",
                "children": [
                    {"type": "worksheet", "name": "Sales"},
                    {"type": "worksheet", "name": "Trend"},
                ],
            },
            {
                "type": "container",
                "direction": "vertical",
                "fixed_size": 220,
                "children": [
                    {"type": "filter", "worksheet": "Sales", "field": "Category", "mode": "dropdown"},
                    {"type": "paramctrl", "parameter": "Target Profit", "mode": "slider"},
                ],
            },
        ],
    }
    editor.add_dashboard("Overview", worksheet_names=["Sales", "Trend"], layout=layout)
    editor.add_dashboard_action(
        dashboard_name="Overview",
        action_type="filter",
        source_sheet="Sales",
        target_sheet="Trend",
        fields=["Category"],
    )

    out_file = Path("output/analysis_workbook.twb")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    editor.save(out_file)

    report = analyze_workbook(out_file)

    detected = {(item.kind, item.canonical) for item in report.detected}
    assert ("chart", "Bar") in detected
    assert ("chart", "Line") in detected
    assert ("dashboard_zone", "Filter") in detected
    assert ("dashboard_zone", "ParamCtrl") in detected
    assert ("action", "Filter Action") in detected
    assert ("connection", "excel-direct") in detected
    assert report.fit_level == "advanced-fit"



def test_analyze_advent_calendar_detects_recipe_patterns():
    path = Path("templates/viz/Tableau Advent Calendar.twb")
    report = analyze_workbook(path)

    detected = {(item.kind, item.canonical) for item in report.detected}
    assert ("chart", "Donut") in detected
    assert ("chart", "Lollipop") in detected
    assert ("chart", "Bullet") in detected
    assert report.fit_level == "recipe-heavy"



def test_gap_summary_highlights_non_core_items():
    path = Path("templates/viz/Tableau Advent Calendar.twb")
    report = analyze_workbook(path)
    gap_text = report.to_gap_text()

    assert "Capability gap:" in gap_text
    assert "Template fit: recipe-heavy" in gap_text
    assert "[recipe-only]" in gap_text
    assert "Donut" in gap_text
    assert "Recommendation:" in gap_text



def test_diff_template_gap_tool_returns_gap_summary():
    path = Path("templates/viz/Tableau Advent Calendar.twb")
    result = diff_template_gap(str(path))

    assert "Capability gap:" in result
    assert "Template fit: recipe-heavy" in result
    assert "recipe-only" in result
