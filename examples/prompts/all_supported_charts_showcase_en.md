Use the cwtwb MCP tools to recreate the `all_supported_charts` worksheet showcase from the Superstore template.

First read `cwtwb://skills/chart_builder`.

Do not create a dashboard.

Create these worksheets:
Bar Chart, Line Chart, Pie Chart, Map Chart, Scatterplot, Heatmap, Tree Map, Bubble Chart, Area Chart, Text Table, Dual Combo, Lollipop Chart, Donut Chart, Butterfly Chart, Calendar Chart.

Use standard chart tools for:
- Bar Chart: Category, SUM(Sales), Region
- Line Chart: YEAR(Order Date), SUM(Sales)
- Pie Chart: Segment, SUM(Sales)
- Map Chart: State/Province, SUM(Profit), SUM(Sales)
- Scatterplot: SUM(Sales), SUM(Profit), Category, Product Name
- Heatmap: Region, Category, SUM(Sales)
- Tree Map: SUM(Sales), SUM(Profit), Category
- Bubble Chart: SUM(Sales), Region, State/Province
- Area Chart: MONTH(Order Date), SUM(Sales), Category
- Text Table: Category, Sub-Category, YEAR(Order Date), SUM(Sales)
- Dual Combo: MONTH(Order Date), SUM(Sales), SUM(Profit), Category

For showcase-only charts, use `configure_chart_recipe`:
- `lollipop` with `dimension=State/Province` and `measure=SUM(Sales)`
- `donut` with `category=Category` and `measure=SUM(Sales)`
- `butterfly` with `dimension=Region`, `left_measure=SUM(Sales)`, and `right_measure=SUM(Quantity)`
- `calendar` with the default `Order Date` / `Sales Over 400` setup

Do not create `min 0` or `Sales Over 400` manually unless you are intentionally overriding the recipe defaults.

Save the workbook to the current folder.
