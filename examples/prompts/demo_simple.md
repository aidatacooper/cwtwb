---
step: 1
level: "⭐ Beginner"
demonstrates: "2 KPI text cards + 2 bar charts + generate_layout_json + vertical dashboard"
---

Build a sales dashboard for me. Call `create_workbook` with no template path to use the built-in Superstore dataset. Please execute the following sequence:

1. Create 2 Text worksheets for KPIs: Name them "Total Sales" and "Total Profit". Aggregate their values using SUM.
2. Create 2 Bar chart worksheets: Name them "Sales By Ship Mode" and "Sales By Category". Put the dimension on Rows and SUM(Sales) on Columns.
3. Once all worksheets are ready, please layout a new dashboard called "Auto Layout Demo" (1200x800).
4. LAYOUT REQUIREMENT: The structure is a vertical container holding 3 horizontal rows.
   - Row 1: Left is a Logo, right is a large Header.
   - Row 2: Hold the 2 KPIs.
   - Row 3: Hold the 2 Bar charts.
5. EXTREMELY IMPORTANT STEP: 
   - DO NOT pass the dictionary directly into `add_dashboard`.
   - You MUST first call the `generate_layout_json` tool. Create the nested dict and a helpful human-readable `ascii_preview` of the layout, and save it to `output/demo_auto_layout3_layout.json`.
   - Then, call `add_dashboard` by passing only the absolute file path of that JSON file into the `layout` parameter.
6. Finally, save the workbook to `output/demo_auto_layout3.twb`.