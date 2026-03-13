"""Demo: Multi-Dashboard Assembly from JSON Layout Files

Step 4 / 5  |  Level: ⭐⭐⭐ Advanced
Demonstrates: Creating 8 worksheets (KPI text cards + bar charts) and
assembling 3 dashboards using external JSON layout files loaded from
examples/layouts/. Shows how to reuse a layout schema across dashboards.

Usage:
    python examples/scripts/demo_declarative_layout.py
"""
import sys
import os
import json
from pathlib import Path

# Add src to path so we can import local cwtwb
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from cwtwb.twb_editor import TWBEditor

def main():
    print("=== Demo: Declarative JSON Dashboard Layout ===")

    output_path = Path(__file__).parent.parent.parent / "output" / "demo_declarative_dash.twb"

    print("1. Loading template...")
    editor = TWBEditor("")  # uses built-in default template from references/
    editor.clear_worksheets()

    print("2. Generating some mock worksheets...")
    # Creating some simple charts to fill the layout
    # Define the 4 details charts and 4 KPI metrics
    charts = ["Sales By Category", "Profit Map", "Discount Trend", "Daily Highlights"]
    kpi_measures = [
        ("Sales By Category - KPI", "SUM(Discount)"),
        ("Profit Map - KPI", "SUM(Profit)"),
        ("Discount Trend - KPI", "SUM(Quantity)"),
        ("Daily Highlights - KPI", "SUM(Sales)"),
    ]
    charts_kpi = [name for name, _ in kpi_measures]
    
    # Configure KPIs as Text Mark types
    for name, measure in kpi_measures:
        editor.add_worksheet(name)
        editor.configure_chart(name, mark_type="Text", label=measure)
        print(f"   - Added KPI Worksheet: {name} ({measure})")

    # Configure detailed charts as Bar charts
    for i, name in enumerate(charts):
        editor.add_worksheet(name)
        editor.configure_chart(name, mark_type="Bar", rows=["Ship Mode"], columns=["SUM(Sales)"])
        print(f"   - Added Details Worksheet: {name}")

    print("3. Loading external layouts from examples/layouts/...")
    layouts_dir = Path(__file__).parent.parent / "layouts"
    exec_path = layouts_dir / "layout_executive.json"
    c1_path = layouts_dir / "layout_c1.json"
    c2_path = layouts_dir / "layout_c2.json"

    print("4. Applying the 'Executive Summary' layout to Dashboard Canvas...")
    if exec_path.exists():
        with open(exec_path, 'r', encoding='utf-8') as f:
            exec_schema = json.load(f)
        editor.add_dashboard(
            dashboard_name="Executive Summary",
            width=1400,
            height=900,
            layout=exec_schema,
            worksheet_names=charts # Needed for internal registry tracking
        )
        print("   - Added Dashboard: Executive Summary")

    if c1_path.exists():
        with open(c1_path, 'r', encoding='utf-8') as f:
            c1_schema = json.load(f)
        editor.add_dashboard(
            dashboard_name="C.1 Layout Replica",
            width=1200,
            height=800,
            layout=c1_schema,
            worksheet_names=charts
        )
        print("   - Added Dashboard: C.1 Layout Replica")

    if c2_path.exists():
        with open(c2_path, 'r', encoding='utf-8') as f:
            c2_schema = json.load(f)
        editor.add_dashboard(
            dashboard_name="C.2 Layout Replica",
            width=1200,
            height=800,
            layout=c2_schema,
            worksheet_names=charts + charts_kpi
        )
        print("   - Added Dashboard: C.2 Layout Replica")


    print(f"6. Saving workbook to: {output_path}")
    editor.save(output_path)
    
    print("\nSuccess! Open the file above in Tableau Desktop.")
    print("   You should see 3 new carefully crafted dashboards:")
    print("   1. 'Executive Summary' (Inline dict demo)")
    print("   2. 'C.1 Layout Replica' (Loaded from json)")
    print("   3. 'C.2 Layout Replica' (Loaded from json)")

if __name__ == "__main__":
    main()
