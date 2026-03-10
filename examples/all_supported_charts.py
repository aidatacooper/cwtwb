"""Generate a mixed workbook covering core, advanced, and recipe-heavy chart examples.

This script is intentionally broader than the SDK's stable support promise. It is
useful as a showcase and regression script, but it should not be read as a claim
that every chart in this workbook is a first-class cwtwb primitive.
"""

import sys
from pathlib import Path

# Add src to sys.path to easily import the local cwtwb package
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from cwtwb.charts.showcase_recipes import configure_chart_recipe
from cwtwb.twb_editor import TWBEditor


def generate_all_charts():
    # Setup Paths
    template_path = project_root / "templates" / "twb" / "superstore.twb"
    output_path = project_root / "output" / "all_supported_charts.twb"

    # Ensure output dir exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("Initializing Editor...")
    editor = TWBEditor(str(template_path))

    print("Using built-in Excel connection from template...")

    # 1. Bar Chart
    print("Configuring: Bar Chart")
    editor.add_worksheet("Bar Chart")
    editor.configure_chart("Bar Chart", mark_type="Bar", rows=["Category"], columns=["SUM(Sales)"], color="Region")

    # 2. Line Chart
    print("Configuring: Line Chart")
    editor.add_worksheet("Line Chart")
    editor.configure_chart("Line Chart", mark_type="Line", columns=["YEAR(Order Date)"], rows=["SUM(Sales)"])

    # 3. Pie Chart
    print("Configuring: Pie Chart")
    editor.add_worksheet("Pie Chart")
    editor.configure_chart("Pie Chart", mark_type="Pie", color="Segment", wedge_size="SUM(Sales)")

    # 4. Map Chart
    print("Configuring: Map Chart")
    editor.add_worksheet("Map Chart")
    editor.configure_chart("Map Chart", mark_type="Map", geographic_field="State/Province", color="SUM(Profit)", size="SUM(Sales)")

    # 5. Scatterplot
    print("Configuring: Scatterplot")
    editor.add_worksheet("Scatterplot")
    editor.configure_chart("Scatterplot", mark_type="Scatterplot", columns=["SUM(Sales)"], rows=["SUM(Profit)"], color="Category", detail="Product Name")

    # 6. Heatmap
    print("Configuring: Heatmap")
    editor.add_worksheet("Heatmap")
    editor.configure_chart("Heatmap", mark_type="Heatmap", columns=["Region"], rows=["Category"], color="SUM(Sales)")

    # 7. Tree Map
    print("Configuring: Tree Map")
    editor.add_worksheet("Tree Map")
    editor.configure_chart("Tree Map", mark_type="Tree Map", color="SUM(Profit)", size="SUM(Sales)", label="Category")

    # 8. Bubble Chart
    print("Configuring: Bubble Chart")
    editor.add_worksheet("Bubble Chart")
    editor.configure_chart("Bubble Chart", mark_type="Bubble Chart", color="Region", size="SUM(Sales)", label="State/Province")

    # 9. Area Chart
    print("Configuring: Area Chart")
    editor.add_worksheet("Area Chart")
    editor.configure_chart("Area Chart", mark_type="Area", columns=["MONTH(Order Date)"], rows=["SUM(Sales)"], color="Category")

    # 10. Text Table
    print("Configuring: Text Table")
    editor.add_worksheet("Text Table")
    editor.configure_chart("Text Table", mark_type="Text", rows=["Category", "Sub-Category"], columns=["YEAR(Order Date)"], label="SUM(Sales)")

    # 11. Dual Axis (Combo Chart)
    print("Configuring: Dual Combo")
    editor.add_worksheet("Dual Combo")
    editor.configure_dual_axis(
        "Dual Combo",
        mark_type_1="Bar",
        mark_type_2="Line",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Sales)", "SUM(Profit)"],
        dual_axis_shelf="rows",
        color_1="Category",
        synchronized=True,
    )

    # 12. Lollipop Chart
    print("Configuring: Lollipop Chart")
    editor.add_worksheet("Lollipop Chart")
    configure_chart_recipe(
        editor,
        "Lollipop Chart",
        "lollipop",
        {"dimension": "State/Province", "measure": "SUM(Sales)"},
    )

    # 13. Donut Chart
    print("Configuring: Donut Chart")
    editor.add_worksheet("Donut Chart")
    configure_chart_recipe(
        editor,
        "Donut Chart",
        "donut",
        {"category": "Category", "measure": "SUM(Sales)"},
    )

    # 14. Butterfly Chart (reversed first axis)
    print("Configuring: Butterfly Chart")
    editor.add_worksheet("Butterfly Chart")
    configure_chart_recipe(
        editor,
        "Butterfly Chart",
        "butterfly",
        {
            "dimension": "Region",
            "left_measure": "SUM(Sales)",
            "right_measure": "SUM(Quantity)",
        },
    )

    # 15. Calendar Chart
    print("Configuring: Calendar Chart")
    editor.add_worksheet("Calendar Chart")
    configure_chart_recipe(
        editor,
        "Calendar Chart",
        "calendar",
    )

    print(f"Saving to {output_path}...")
    editor.save(str(output_path))
    print("Success!")

if __name__ == "__main__":
    generate_all_charts()
