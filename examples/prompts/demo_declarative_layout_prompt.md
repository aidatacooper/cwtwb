---
step: 6
level: "⭐⭐ Intermediate"
demonstrates: "8 worksheets (4 bar + 4 KPI text) + 2 dashboards assembled from JSON layout files"
requires: "examples/layouts/layout_executive.json, examples/layouts/layout_c2.json"
---

# Declarative JSON Dashboard Layout - Natural language MCP Prompt

You can use the following conversational prompt with any LLM connected to the `cwtwb` MCP server to achieve the same results without hardcoding long JSON payloads.

## The Prompt

```text
Hi! I want to build an Executive Dashboard related to sales using the cwtwb tool.


First, I need 8 worksheets in total. Four of them are detail charts:
- "Sales By Category", "Profit Map", "Discount Trend", "Daily Highlights"
Please configure all 4 as Bar charts. Put "Ship Mode" on rows and "SUM(Sales)" on columns.

The other four are KPI text summaries (they should use the Text mark_type). Please name them by adding " - KPI" to the end of the previous names.
Set their label values to SUM(Discount), SUM(Profit), SUM(Quantity), and SUM(Sales) respectively.

Once the sheets are ready, create two dashboards:

1. "Executive Summary" (1400x900)
For the layout parameter, please read the file `examples/layouts/layout_executive.json` and pass its content directly as the dictionary. Make sure to include all 8 worksheets in the `worksheet_names` list!

2. "C.2 Layout Replica" (1200x800)
For this one's layout, please read `examples/layouts/layout_c2.json` and pass it. Include the 8 worksheets here too.

Finally, save this workbook to `output`. Thanks!
```
