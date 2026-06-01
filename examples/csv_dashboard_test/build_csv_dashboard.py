"""
CSV Dashboard Test — SDK Test Script

Tests CSV connection + dashboard generation with packaged TWBX output.

Run:
    cd <project_root>
    python examples/csv_dashboard_test/build_csv_dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cwtwb.twb_editor import TWBEditor

CSV_PATH = str(Path(__file__).resolve().parent / "sample_data.csv")
OUTPUT_PATH = str(Path(__file__).resolve().parent / "csv_dashboard.twbx")


def main() -> None:
    print("=== Building CSV Dashboard (TWBX) ===\n")

    # 1. Create blank workbook
    print("1. Creating workbook...")
    editor = TWBEditor("")

    # 2. Set CSV connection
    print("2. Setting CSV connection...")
    editor.set_csv_connection(filepath=CSV_PATH)

    # 3. Add calculated fields
    print("3. Adding calculated fields...")
    editor.add_calculated_field(
        "Profit Margin",
        "[Profit] / [Sales]",
        datatype="real",
        default_format="p1%",
    )
    editor.add_calculated_field(
        "Avg Order Value",
        "[Sales] / [Quantity]",
        datatype="real",
        default_format='c"$"#,##0.00',
    )

    # 4. Create worksheets
    print("4. Creating worksheets...")

    # Sales by Category (Bar chart)
    editor.add_worksheet("Sales by Category")
    editor.configure_chart(
        "Sales by Category",
        mark_type="Bar",
        columns=["SUM(Sales)"],
        rows=["Category"],
        color="Category",
        sort_descending="SUM(Sales)",
    )
    editor.configure_worksheet_style(
        "Sales by Category",
        hide_gridlines=True,
        hide_borders=True,
        hide_band_color=True,
    )

    # Profit by Region (Pie chart)
    editor.add_worksheet("Profit by Region")
    editor.configure_chart(
        "Profit by Region",
        mark_type="Pie",
        rows=["Region"],
        label="SUM(Profit)",
        sort_descending="SUM(Profit)",
    )
    editor.configure_worksheet_style(
        "Profit by Region",
        background_color="#00000000",
        hide_axes=True,
        hide_gridlines=True,
        hide_zeroline=True,
        hide_borders=True,
        hide_band_color=True,
        pane_datalabel_style={
            "color-mode": "user",
            "font-family": "Tableau Bold",
            "color": "#5a6dff",
            "font-size": "14",
        },
    )

    # Sales Trend (Line chart)
    editor.add_worksheet("Sales Trend")
    editor.configure_chart(
        "Sales Trend",
        mark_type="Line",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Sales)"],
        color="Region",
    )
    editor.configure_worksheet_style(
        "Sales Trend",
        hide_gridlines=True,
        hide_borders=True,
        hide_band_color=True,
    )

    # Profit Margin by Sub-Category (Horizontal Bar)
    editor.add_worksheet("Profit Margin by Sub-Category")
    editor.configure_chart(
        "Profit Margin by Sub-Category",
        mark_type="Bar",
        columns=["AVG(Profit Margin)"],
        rows=["Sub-Category"],
        color="Category",
        sort_descending="AVG(Profit Margin)",
    )
    editor.configure_worksheet_style(
        "Profit Margin by Sub-Category",
        hide_gridlines=True,
        hide_borders=True,
        hide_band_color=True,
    )

    # KPI Summary (Text)
    editor.add_worksheet("KPI Summary")
    editor.configure_chart(
        "KPI Summary",
        mark_type="Text",
        label="SUM(Sales)",
        label_runs=[
            {"text": "Total Sales", "fontname": "Tableau Regular", "fontsize": 10, "fontalignment": "2"},
            {"text": "\n"},
            {"field": "SUM(Sales)", "fontname": "Tableau Bold", "fontsize": 16,
             "fontcolor": "#5a6dff", "bold": True, "fontalignment": "2"},
        ],
    )
    editor.configure_worksheet_style(
        "KPI Summary",
        background_color="#00000000",
        hide_axes=True,
        hide_gridlines=True,
        hide_zeroline=True,
        hide_borders=True,
        hide_band_color=True,
        pane_cell_style={"text-align": "center", "vertical-align": "center"},
    )

    # 5. Create dashboard
    print("5. Creating dashboard...")
    layout = {
        "type": "container",
        "direction": "vertical",
        "children": [
            # Title
            {"type": "text", "text": "Sales Dashboard", "font_size": "20",
             "bold": True, "font_color": "#2c2f4a", "fixed_size": 50},
            # KPI + Charts row
            {"type": "container", "direction": "horizontal", "fixed_size": 150,
             "children": [
                 {"type": "worksheet", "name": "KPI Summary",
                  "fixed_size": 200,
                  "style": {"background-color": "#ffffff", "border-color": "#898989",
                            "border-style": "solid", "border-width": "1", "margin": "4"}},
                 {"type": "worksheet", "name": "Sales by Category",
                  "style": {"background-color": "#ffffff", "border-color": "#898989",
                            "border-style": "solid", "border-width": "1", "margin": "4"}},
             ]},
            # Bottom row
            {"type": "container", "direction": "horizontal",
             "children": [
                 {"type": "worksheet", "name": "Profit by Region",
                  "fixed_size": 300,
                  "style": {"background-color": "#ffffff", "border-color": "#898989",
                            "border-style": "solid", "border-width": "1", "margin": "4"}},
                 {"type": "worksheet", "name": "Sales Trend",
                  "style": {"background-color": "#ffffff", "border-color": "#898989",
                            "border-style": "solid", "border-width": "1", "margin": "4"}},
                 {"type": "worksheet", "name": "Profit Margin by Sub-Category",
                  "style": {"background-color": "#ffffff", "border-color": "#898989",
                            "border-style": "solid", "border-width": "1", "margin": "4"}},
             ]},
        ],
    }

    editor.add_dashboard(
        dashboard_name="Sales Dashboard",
        width=1200,
        height=800,
        layout=layout,
        worksheet_names=[
            "Sales by Category", "Profit by Region", "Sales Trend",
            "Profit Margin by Sub-Category", "KPI Summary",
        ],
    )

    # 6. Save as TWBX (packaged with CSV)
    print(f"6. Saving to {OUTPUT_PATH}...")
    editor.save(OUTPUT_PATH, validate=True)

    print(f"\nDone! Output: {OUTPUT_PATH}")
    print("This is a packaged TWBX file that includes the CSV data.")


if __name__ == "__main__":
    main()
