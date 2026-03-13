---
step: 4
level: "⭐⭐ Intermediate"
demonstrates: "KPI text cards + bar charts + 3-row layout (header / KPI band / charts) with fixed_size"
---

# Demo Auto Layout 4 Prompt

This prompt can be directly sent to an AI with `cwtwb` MCP tool access (like Cline, Cursor, or Gemini) to demonstrate the latest Declarative layout features and the fixed Dashboard sizing behavior.

## Prompt

```text
Use cwtwb MCP to build a sales dashboard for me. Call `create_workbook` with no template path to use the built-in Superstore dataset.

1. Create 2 KPIs: the measures are sales and profit, aggregate with sum, mark type is text.
   Then create 2 Bar charts: "Sales By Ship Mode", "Sales By Category". Sales is the measure.

2. Layout: Put all charts into a new dashboard named "Layout dashboard" (size: 1200x800). 
   Please use  JSON layout: 
   The root is a vertical container containing 3 rows:
   - Row 1 (Horizontal, fixed size 100): Contains a Text area for "Logo Area", and a large Text header for the dashboard title.
   - Row 2 (Horizontal, distribute evenly, fixed size  150): Contains the 2 KPI worksheets.
   - Row 3 (Horizontal, distribute evenly): Contains the 2 Bar chart worksheets side by side.

3. Save the final workbook to `output/demo_auto_layout4.twb`.
```

## Expected Results

- The generated code will call `create_workbook` with no template path, using the built-in Superstore dataset.
- 4 Worksheets will be created and configured via `configure_chart`.
- A complex JSON layout tree will be built to generate the Dashboard.
- The resulting `demo_auto_layout4.twb` will have its size strictly fixed at 1200x800 pixels (`sizing-mode="fixed"` now handled correctly) in Tableau, with the header and KPI rows maintaining their absolute pixel heights.
