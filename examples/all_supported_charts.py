"""Test generating all supported charts into a single workbook."""

import sys
from pathlib import Path

# Add src to sys.path to easily import the local cwtwb package
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from lxml import etree
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
    editor.configure_dual_axis(
        "Lollipop Chart",
        mark_type_1="Bar",
        mark_type_2="Circle",
        columns=["SUM(Sales)", "SUM(Sales)"],
        rows=["State/Province"],
        dual_axis_shelf="columns",
        show_labels=False,
        mark_sizing_off=True,
        size_value_1="0.98850828409194946",
        size_value_2="1.5492265224456787",
        hide_axes=True,
    )
    
    # 13. Donut Chart
    print("Configuring: Donut Chart")
    editor.add_calculated_field("min 0", "MIN(0)", datatype="integer")
    editor.add_worksheet("Donut Chart")
    editor.configure_dual_axis(
        "Donut Chart",
        mark_type_1="Pie",
        mark_type_2="Pie",
        columns=[],
        rows=["min 0", "min 0"],
        dual_axis_shelf="rows",
        color_1="Category",
        wedge_size_1="SUM(Sales)",
        label_2="SUM(Sales)",
        show_labels=True,
        hide_axes=True,
        hide_zeroline=True,
        mark_sizing_off=True,
        size_value_1="1.8",
        size_value_2="1.2193922996520996",
        mark_color_2="#ffffff",
    )

    # 14. Butterfly Chart (reversed first axis)
    print("Configuring: Butterfly Chart")
    editor.add_worksheet("Butterfly Chart")
    editor.configure_dual_axis(
        "Butterfly Chart",
        mark_type_1="Bar",
        mark_type_2="Bar",
        columns=["SUM(Sales)", "SUM(Quantity)"],
        rows=["Region"],
        dual_axis_shelf="columns",
        show_labels=True,
        hide_zeroline=True,
        synchronized=False,
        reverse_axis_1=True,
    )

    # 15. Calendar Chart
    print("Configuring: Calendar Chart")
    editor.add_calculated_field("Sales Over 400", 'IF SUM([Sales]) > 500 THEN "Yes" ELSE "No" END', datatype="string")
    editor.add_worksheet("Calendar Chart")
    editor.configure_chart(
        "Calendar Chart",
        mark_type="Square",
        rows=["WEEK(Order Date)"],
        columns=["WEEKDAY(Order Date)"],
        color="Sales Over 400",
        label="DAYTRUNC(Order Date)",
    )
    # Post-configure: add MY filter, text-format, mark-sizing, and pane styles
    _apply_calendar_styles(editor)

    print(f"Saving to {output_path}...")
    editor.save(str(output_path))
    print("Success!")


def _apply_calendar_styles(editor):
    """Apply Calendar Chart specific XML — filter, text-format, mark-sizing, pane styles."""
    ws = editor._find_worksheet("Calendar Chart")
    table = ws.find("table")
    view = table.find("view")
    ds_name = editor._datasource.get("name", "")

    # 1. Add MY(Order Date) filter to show only one month
    my_ci = editor.field_registry.parse_expression("MY(Order Date)")
    my_ref = editor.field_registry.resolve_full_reference(my_ci.instance_name)
    
    # Add MY column + column-instance to datasource-dependencies
    deps = view.find("datasource-dependencies")
    if deps is not None:
        ci_el = etree.SubElement(deps, "column-instance")
        ci_el.set("column", my_ci.column_local_name)  # already has brackets
        ci_el.set("derivation", "MY")
        ci_el.set("name", my_ci.instance_name)
        ci_el.set("pivot", "key")
        ci_el.set("type", "ordinal")
    
    # Add filter element — must come before slices and aggregation per DTD
    agg = view.find("aggregation")
    
    filt = etree.Element("filter")
    filt.set("class", "categorical")
    filt.set("column", my_ref)
    gf = etree.SubElement(filt, "groupfilter")
    gf.set("function", "member")
    gf.set("level", my_ci.instance_name)
    gf.set("member", "202208")  # Aug 2022
    gf.set("{http://www.tableausoftware.com/xml/user}ui-domain", "database")
    gf.set("{http://www.tableausoftware.com/xml/user}ui-enumeration", "inclusive")
    gf.set("{http://www.tableausoftware.com/xml/user}ui-marker", "enumerate")
    
    if agg is not None:
        agg.addprevious(filt)
    else:
        view.append(filt)
    
    # Add slices — must come before aggregation
    slices = etree.Element("slices")
    col_el = etree.SubElement(slices, "column")
    col_el.text = my_ref
    
    if agg is not None:
        agg.addprevious(slices)
    else:
        view.append(slices)
    
    # 2. Add table-level style with text-format for day field
    tdy_ci = editor.field_registry.parse_expression("DAYTRUNC(Order Date)")
    tdy_ref = editor.field_registry.resolve_full_reference(tdy_ci.instance_name)
    wk_ci = editor.field_registry.parse_expression("WEEK(Order Date)")
    wk_ref = editor.field_registry.resolve_full_reference(wk_ci.instance_name)
    
    old_style = table.find("style")
    if old_style is not None:
        table.remove(old_style)
    
    style = etree.Element("style")
    cell_rule = etree.SubElement(style, "style-rule", {"element": "cell"})
    fmt_tf = etree.SubElement(cell_rule, "format")
    fmt_tf.set("attr", "text-format")
    fmt_tf.set("field", tdy_ref)
    fmt_tf.set("value", "*d")
    fmt_h = etree.SubElement(cell_rule, "format")
    fmt_h.set("attr", "height")
    fmt_h.set("field", wk_ref)
    fmt_h.set("value", "38")
    
    # Insert style before panes
    panes = table.find("panes")
    if panes is not None:
        panes.addprevious(style)
    else:
        table.append(style)
    
    # 3. Add mark-sizing and pane styles to the pane
    pane = table.find(".//pane")
    if pane is not None:
        pane.set("selection-relaxation-option", "selection-relaxation-disallow")
        
        # Insert mark-sizing after mark
        mark_el = pane.find("mark")
        if mark_el is not None:
            ms = etree.Element("mark-sizing")
            ms.set("mark-sizing-setting", "marks-scaling-off")
            mark_el.addnext(ms)
        
        # Add pane-level style
        pane_style = pane.find("style")
        if pane_style is None:
            pane_style = etree.SubElement(pane, "style")
        
        # Cell alignment
        cell_sr = etree.SubElement(pane_style, "style-rule", {"element": "cell"})
        etree.SubElement(cell_sr, "format", {"attr": "text-align", "value": "center"})
        etree.SubElement(cell_sr, "format", {"attr": "vertical-align", "value": "center"})
        
        # Mark size
        for sr in pane_style.findall("style-rule"):
            if sr.get("element") == "mark":
                etree.SubElement(sr, "format", {"attr": "size", "value": "1.5272375345230103"})
                break
        
        # Pane height
        pane_sr = etree.SubElement(pane_style, "style-rule", {"element": "pane"})
        etree.SubElement(pane_sr, "format", {"attr": "minheight", "value": "-1"})
        etree.SubElement(pane_sr, "format", {"attr": "maxheight", "value": "-1"})


if __name__ == "__main__":
    generate_all_charts()
