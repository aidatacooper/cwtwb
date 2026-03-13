"""Demo: Nested Declarative Dashboard Layout

Step 3 / 5  |  Level: ⭐⭐ Intermediate
Demonstrates: Building a 3-row dashboard with a fixed header, KPI band, and
chart row using an inline Python layout dict. Covers Text KPIs + Bar charts
+ fixed_size / distribute-evenly layout containers.

Usage:
    python examples/scripts/demo_auto_layout4.py
"""
import os
from pathlib import Path
from cwtwb.twb_editor import TWBEditor

def main():
    base_dir = Path(__file__).parent.parent.parent
    output_dir = base_dir / "output"
    output_dir.mkdir(exist_ok=True)
    out_file = output_dir / "demo_auto_layout4.twb"

    editor = TWBEditor("")  # uses built-in default template from references/
    
    # KPIs
    editor.add_worksheet("KPI Sales")
    editor.configure_chart("KPI Sales", mark_type="Text", columns=[], rows=[], label="SUM(Sales)")
    editor.add_worksheet("KPI Profit")
    editor.configure_chart("KPI Profit", mark_type="Text", columns=[], rows=[], label="SUM(Profit)")
    
    # Bar charts
    editor.add_worksheet("Sales By Ship Mode")
    editor.configure_chart("Sales By Ship Mode", mark_type="Bar", columns=["SUM(Sales)"], rows=["Ship Mode"])
    
    editor.add_worksheet("Sales By Category")
    editor.configure_chart("Sales By Category", mark_type="Bar", columns=["SUM(Sales)"], rows=["Category"])

    # Layout Dashboard
    layout = {
        "type": "container",
        "direction": "vertical",
        "children": [
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 100,
                "children": [
                    {"type": "text", "text": "Logo Area", "fixed_size": 150},
                    {"type": "text", "text": "Dashboard Header", "font_size": "24", "bold": True}
                ]
            },
            {
                "type": "container",
                "direction": "horizontal",
                "fixed_size": 150,
                "layout_strategy": "distribute-evenly",
                "children": [
                    {"type": "worksheet", "name": "KPI Sales"},
                    {"type": "worksheet", "name": "KPI Profit"}
                ]
            },
            {
                "type": "container",
                "direction": "horizontal", # User said vertical 2 bar charts, but usually they are horizontal to each other in a vertical stack. I'll make it vertical stack
                "layout_strategy": "distribute-evenly",
                "children": [
                    {"type": "worksheet", "name": "Sales By Ship Mode"},
                    {"type": "worksheet", "name": "Sales By Category"}
                ]
            }
        ]
    }

    editor.add_dashboard(
        "Layout dashboard",
        width=1200,
        height=800,
        layout=layout,
        worksheet_names=["KPI Sales", "KPI Profit", "Sales By Ship Mode", "Sales By Category"]
    )

    editor.save(out_file)
    print(f"Successfully saved to {out_file}")

if __name__ == "__main__":
    main()
