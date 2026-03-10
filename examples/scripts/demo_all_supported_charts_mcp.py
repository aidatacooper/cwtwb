"""Recreate the all_supported_charts showcase through the exported MCP tools."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from cwtwb.server import (  # noqa: E402
    add_worksheet,
    configure_chart,
    configure_chart_recipe,
    configure_dual_axis,
    create_workbook,
    save_workbook,
)


def main() -> None:
    project_root = Path(__file__).resolve().parents[2]
    template = project_root / "templates" / "twb" / "superstore.twb"
    output = project_root / "output" / "all_supported_charts_from_mcp.twb"
    output.parent.mkdir(parents=True, exist_ok=True)

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

    print(save_workbook(str(output)))
    print(f"Saved showcase workbook to {output}")


if __name__ == "__main__":
    main()
