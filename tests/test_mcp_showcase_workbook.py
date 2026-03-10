from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cwtwb.server import (  # noqa: E402
    add_calculated_field,
    add_worksheet,
    configure_chart,
    configure_chart_recipe,
    configure_dual_axis,
    create_workbook,
    save_workbook,
)


def test_add_calculated_field_infers_aggregated_nominal_measure(tmp_path: Path) -> None:
    template = Path("templates/twb/superstore.twb")
    output = tmp_path / "aggregated_nominal_calc.twb"

    create_workbook(str(template), "Calc Semantics")
    add_calculated_field(
        "Sales Over 400",
        'IF SUM([Sales]) > 500 THEN "Yes" ELSE "No" END',
        "string",
    )
    save_workbook(str(output))

    root = ET.parse(output).getroot()
    calc = root.find(".//datasource/column[@caption='Sales Over 400']")
    assert calc is not None
    assert calc.get("role") == "measure"
    assert calc.get("type") == "nominal"


def test_configure_dual_axis_exposes_recipe_controls(tmp_path: Path) -> None:
    template = Path("templates/twb/superstore.twb")
    output = tmp_path / "dual_axis_controls.twb"

    create_workbook(str(template), "Dual Axis Controls")
    add_worksheet("Lollipop")
    configure_dual_axis(
        worksheet_name="Lollipop",
        mark_type_1="Bar",
        mark_type_2="Circle",
        columns=["SUM(Sales)", "SUM(Sales)"],
        rows=["Category"],
        dual_axis_shelf="columns",
        synchronized=True,
        show_labels=False,
        mark_sizing_off=True,
        size_value_1="0.2",
        size_value_2="3.4",
        hide_axes=True,
    )
    save_workbook(str(output))

    root = ET.parse(output).getroot()
    worksheet = root.find(".//worksheet[@name='Lollipop']")
    assert worksheet is not None

    panes = worksheet.findall(".//pane")
    assert len(panes) >= 3
    first_mark_rule = panes[1].find("./style/style-rule[@element='mark']")
    second_mark_rule = panes[2].find("./style/style-rule[@element='mark']")
    assert first_mark_rule is not None
    assert second_mark_rule is not None
    assert _format_value(first_mark_rule, "mark-labels-show") == "false"
    assert _format_value(second_mark_rule, "mark-labels-show") == "false"
    assert float(_format_value(first_mark_rule, "size")) < float(_format_value(second_mark_rule, "size"))

    axis_rule = worksheet.find("./table/style/style-rule[@element='axis']")
    assert axis_rule is not None
    encodings = axis_rule.findall("encoding")
    assert len(encodings) == 1
    assert encodings[0].get("synchronized") == "true"


def test_configure_chart_recipe_rejects_unknown_recipe(tmp_path: Path) -> None:
    template = Path("templates/twb/superstore.twb")

    create_workbook(str(template), "Recipe Validation")
    add_worksheet("Unknown Recipe")

    try:
        configure_chart_recipe("Unknown Recipe", "waterfall")
    except ValueError as exc:
        assert str(exc) == "Unknown chart recipe 'waterfall'. Supported recipes: butterfly, calendar, donut, lollipop"
    else:
        raise AssertionError("Expected configure_chart_recipe to reject unknown recipe names")


def test_configure_chart_recipe_requires_required_args(tmp_path: Path) -> None:
    template = Path("templates/twb/superstore.twb")

    create_workbook(str(template), "Recipe Validation")
    add_worksheet("Broken Recipe")

    try:
        configure_chart_recipe("Broken Recipe", "donut", {"category": "Category"})
    except ValueError as exc:
        assert str(exc) == "Chart recipe 'donut' is missing required args: measure"
    else:
        raise AssertionError("Expected configure_chart_recipe to reject incomplete recipe args")


def test_configure_chart_recipe_auto_ensures_prerequisites(tmp_path: Path) -> None:
    template = Path("templates/twb/superstore.twb")
    output = tmp_path / "recipe_prereqs.twb"

    create_workbook(str(template), "Recipe Prereqs")
    add_worksheet("Donut")
    add_worksheet("Calendar")

    configure_chart_recipe("Donut", "donut", {"category": "Category", "measure": "SUM(Sales)"})
    configure_chart_recipe("Calendar", "calendar")
    save_workbook(str(output))

    root = ET.parse(output).getroot()

    donut_calc = root.find(".//datasource/column[@caption='min 0']")
    assert donut_calc is not None
    assert donut_calc.find("calculation").get("formula") == "MIN(0)"
    assert donut_calc.get("role") == "measure"
    assert donut_calc.get("type") == "quantitative"

    calendar_calc = root.find(".//datasource/column[@caption='Sales Over 400']")
    assert calendar_calc is not None
    assert 'THEN "Yes" ELSE "No" END' in calendar_calc.find("calculation").get("formula")
    assert calendar_calc.get("role") == "measure"
    assert calendar_calc.get("type") == "nominal"

    calendar = _worksheet(root, "Calendar")
    calendar_filter = calendar.find(".//filter/groupfilter")
    assert calendar_filter is not None
    assert calendar_filter.get("member") == "202208"


def test_mcp_tools_can_recreate_all_supported_charts_showcase(tmp_path: Path) -> None:
    template = Path("templates/twb/superstore.twb")
    output = tmp_path / "all_supported_charts_from_mcp.twb"

    create_workbook(str(template), "All Supported Charts From MCP")

    for name in [
        "Bar Chart",
        "Line Chart",
        "Pie Chart",
        "Map Chart",
        "Scatterplot",
        "Heatmap",
        "Tree Map",
        "Bubble Chart",
        "Area Chart",
        "Text Table",
        "Dual Combo",
        "Lollipop Chart",
        "Donut Chart",
        "Butterfly Chart",
        "Calendar Chart",
    ]:
        add_worksheet(name)

    configure_chart("Bar Chart", mark_type="Bar", rows=["Category"], columns=["SUM(Sales)"], color="Region")
    configure_chart("Line Chart", mark_type="Line", columns=["YEAR(Order Date)"], rows=["SUM(Sales)"])
    configure_chart("Pie Chart", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)")
    configure_chart(
        "Map Chart",
        mark_type="Map",
        geographic_field="State/Province",
        color="SUM(Profit)",
        size="SUM(Sales)",
    )
    configure_chart(
        "Scatterplot",
        mark_type="Scatterplot",
        columns=["SUM(Sales)"],
        rows=["SUM(Profit)"],
        color="Category",
        detail="Product Name",
    )
    configure_chart("Heatmap", mark_type="Heatmap", columns=["Region"], rows=["Category"], color="SUM(Sales)")
    configure_chart("Tree Map", mark_type="Tree Map", color="SUM(Profit)", size="SUM(Sales)", label="Category")
    configure_chart("Bubble Chart", mark_type="Bubble Chart", color="Region", size="SUM(Sales)", label="State/Province")
    configure_chart("Area Chart", mark_type="Area", columns=["MONTH(Order Date)"], rows=["SUM(Sales)"], color="Category")
    configure_chart(
        "Text Table",
        mark_type="Text",
        rows=["Category", "Sub-Category"],
        columns=["YEAR(Order Date)"],
        label="SUM(Sales)",
    )
    configure_dual_axis(
        "Dual Combo",
        mark_type_1="Bar",
        mark_type_2="Line",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Sales)", "SUM(Profit)"],
        dual_axis_shelf="rows",
        color_1="Category",
        synchronized=True,
    )

    configure_chart_recipe(
        "Lollipop Chart",
        "lollipop",
        {"dimension": "State/Province", "measure": "SUM(Sales)"},
    )
    configure_chart_recipe(
        "Donut Chart",
        "donut",
        {"category": "Category", "measure": "SUM(Sales)"},
    )
    configure_chart_recipe(
        "Butterfly Chart",
        "butterfly",
        {
            "dimension": "Region",
            "left_measure": "SUM(Sales)",
            "right_measure": "SUM(Quantity)",
        },
    )
    configure_chart_recipe(
        "Calendar Chart",
        "calendar",
    )

    save_workbook(str(output))
    assert output.exists()

    root = ET.parse(output).getroot()

    lollipop = _worksheet(root, "Lollipop Chart")
    assert lollipop.find("./table/style/style-rule[@element='axis']/encoding").get("synchronized") == "true"
    lollipop_panes = lollipop.findall(".//pane")
    lollipop_bar = lollipop_panes[1].find("./style/style-rule[@element='mark']")
    lollipop_circle = lollipop_panes[2].find("./style/style-rule[@element='mark']")
    assert _format_value(lollipop_bar, "mark-labels-show") == "false"
    assert _format_value(lollipop_circle, "mark-labels-show") == "false"
    assert float(_format_value(lollipop_bar, "size")) < float(_format_value(lollipop_circle, "size"))
    assert lollipop_panes[1].get("x-axis-name") == lollipop_panes[2].get("x-axis-name")
    assert lollipop_panes[2].get("x-index") == "1"

    donut = _worksheet(root, "Donut Chart")
    donut_panes = donut.findall(".//pane")
    assert donut_panes[1].get("y-axis-name") == donut_panes[2].get("y-axis-name")
    donut_text = donut_panes[2].find(".//encodings/text")
    assert donut_text is not None
    assert "sum:Sales" in donut_text.get("column", "")
    donut_mark_rule = donut_panes[2].find("./style/style-rule[@element='mark']")
    assert donut_mark_rule is not None
    assert _format_value(donut_mark_rule, "mark-color") == "#ffffff"

    butterfly = _worksheet(root, "Butterfly Chart")
    butterfly_axis_rule = butterfly.find("./table/style/style-rule[@element='axis']")
    reverse_encoding = butterfly_axis_rule.find("./encoding[@class='0']")
    assert reverse_encoding is not None
    assert reverse_encoding.get("reverse") == "true"
    assert reverse_encoding.get("field") == butterfly.find(".//pane[@id='1']").get("x-axis-name")

    calendar = _worksheet(root, "Calendar Chart")
    assert "wk:Order Date" in (calendar.findtext("./table/rows") or "")
    assert "wd:Order Date" in (calendar.findtext("./table/cols") or "")
    calendar_filter = calendar.find(".//filter/groupfilter")
    assert calendar_filter is not None
    assert calendar_filter.get("member") == "202208"
    calc = root.find(".//datasource/column[@caption='Sales Over 400']")
    assert calc is not None
    assert calc.get("role") == "measure"
    assert calc.get("type") == "nominal"


def _worksheet(root: ET.Element, name: str) -> ET.Element:
    worksheet = root.find(f".//worksheet[@name='{name}']")
    assert worksheet is not None
    return worksheet


def _format_value(style_rule: ET.Element | None, attr: str) -> str | None:
    if style_rule is None:
        return None
    for fmt in style_rule.findall("format"):
        if fmt.get("attr") == attr:
            return fmt.get("value")
    return None
