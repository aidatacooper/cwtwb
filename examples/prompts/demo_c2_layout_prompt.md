---
step: 5
level: "⭐⭐ Intermediate"
demonstrates: "8 worksheets (4 bar + 4 KPI text) + load C.2 JSON layout file → single dashboard"
requires: "examples/layouts/layout_c2.json"
---

# C.2 Layout Server Prompt

```text
Hi, let's build the "C.2 Layout Replica" dashboard using the cwtwb MCP server.

1. Call `create_workbook` with no template path to use the built-in Superstore dataset.
2. I need exactly 8 charts. Four are regular Bar charts showing Sales automatically broken down by Ship Mode. Please name them:
   - "Sales By Category", "Profit Map", "Discount Trend", "Daily Highlights"
3. The other four are just Text cards showing their respective totals: SUM(Discount), SUM(Profit), SUM(Quantity), and SUM(Sales). Please name them by adding " - KPI" to the original 4 names above.
4. Finally, put all 8 charts into a new dashboard named "C.2 Layout Replica" (1200x800). Please directly use the layout file `examples/layouts/layout_c2.json` to arrange them.
5. Save the workbook as `output/demo_C2_only.twb`.
```
