---
name: Chart Builder
description: Expert guidance for choosing chart types, configuring encodings, and building effective visualizations via cwtwb.
phase: 2
prerequisites: calculation_builder (parameters and calculated fields should be ready)
---

# Chart Builder Skill

## Your Role

You are a **data visualization expert**. Your job is to select the right chart type for each analytical question, configure the correct field encodings, and ensure the charts communicate insights clearly.

## Workflow

```
1. Identify the analytical questions each chart should answer
2. Select the best chart type for each question
3. Create worksheets (add_worksheet)
4. Configure charts with proper encodings (configure_chart)
5. Add appropriate filters to each chart
```

## Chart Type Selection Guide

### When to Use Each Chart Type

| Analytical Question | Best Chart Type | mark_type |
|---|---|---|
| How much? What's the total? | KPI Card | `Text` (with `measure_values`) |
| Compare categories | Horizontal Bar | `Bar` (dimension in rows, measure in columns) |
| Trend over time | Line Chart | `Line` (date in columns, measure in rows) |
| Composition/parts of whole | Pie Chart | `Pie` (color=dimension, wedge_size=measure) |
| Geographic distribution | Map | `Map` (geographic_field + color/size) |
| Trend + breakdown | Area Chart | `Area` (date in columns, [dimension, measure] in rows) |
| Volume/correlation | Scatterplot | `Scatterplot` (measures in both columns and rows) |
| Multi-categorical volume | Bubble Chart | `Bubble Chart` (color=dimension, size=measure) |
| Metric intersections | Heatmap | `Heatmap` (dimensions in columns/rows, color/label=measure) |
| Hierarchical parts of whole | Tree Map | `Tree Map` (size=measure, color=measure, label=dimension) |
| At-a-glance KPI summary | Text Table | `Text` (with `measure_values`) |

### Anti-Patterns — DON'T Do This

| ❌ Wrong Choice | Why | ✅ Better Choice |
|---|---|---|
| Pie chart with 10+ slices | Impossible to read | Horizontal bar chart |
| 3D charts | Distort perception | Any 2D equivalent |
| Dual-axis without clear reason | Confuses readers | Two separate charts |
| Bar chart for time series | Bars don't convey continuity | Line chart |

## Encoding Guide

### KPI Cards (measure_values mode)

For executive summaries showing multiple metrics at a glance:

```python
configure_chart("Total Sales", mark_type="Text",
    measure_values=["SUM(Sales)", "SUM(Profit)", "Profit Ratio",
                    "AVG(Discount)", "SUM(Quantity)"])
```

**Best practices:**
- 5-8 metrics maximum per KPI card
- Lead with the most important metric
- Mix absolute values (Sales) with ratios (Profit Ratio)

### Bar Charts

For comparing categories:

```python
# Horizontal bar — best for category names
configure_chart("Sales by Category", mark_type="Bar",
    rows=["Category"],
    columns=["SUM(Sales)"],
    color="Category",         # Optional: adds visual clarity
    label="SUM(Sales)",       # Show values on bars
    sort_descending="SUM(Sales)")  # Sort by value
```

**Best practices:**
- Horizontal bars for long category names
- Always sort descending by the measure — unsorted bars waste cognitive effort
- Color by the same dimension for visual consistency, or use a highlight color
- Add label encoding to show exact values

### Line / Area Charts

For trends over time:

```python
# Monthly sales trend by segment
configure_chart("Sales Trend", mark_type="Area",
    columns=["MONTH(Order Date)"],
    rows=["Segment", "SUM(Sales)"],  # Segment creates multiple panels
    color="Order Profitable?",       # Color by a dimension
    tooltip="SUM(Profit)")
```

**Best practices:**
- Use `MONTH()` for seasonal patterns, `YEAR()` for long-term trends
- Area charts work well with color-filled breakdowns (e.g., profitable vs not)
- Put the dimension before the measure in rows to create small-multiple panels
- Always add tooltip with a complementary measure

### Map Charts

For geographic data:

```python
configure_chart("Sales Map", mark_type="Map",
    geographic_field="State/Province",
    color="Profit Ratio",     # Continuous measure → gradient color
    size="SUM(Sales)",        # Size by volume
    tooltip="SUM(Profit)",
    map_fields=["Country/Region"])
```

**Best practices:**
- Use continuous color (a measure) for maps — it creates intuitive heat maps
- Size encoding shows volume/magnitude 
- Set `map_fields` to include parent geographic levels
- Always add tooltip for detail-on-demand

### Pie Charts

For composition/parts of whole:

```python
configure_chart("Market Share", mark_type="Pie",
    color="Segment",           # Slices
    wedge_size="SUM(Sales)",   # Slice size
    label="SUM(Sales)")        # Values on slices
```

**Best practices:**
- **Maximum 5-6 slices** — beyond that, use a bar chart
- Leave columns and rows empty for Pie charts
- Always add label to show values

## Advanced Patterns (configure_chart / configure_dual_axis)

### KPI Difference Badge (MIN(1) dummy axis + fixed range + color_map + customized_label)

Used for "vs PY" KPI comparison cards where you want a tiny coloured pill showing a percentage difference:

```python
configure_chart(
    "Sales KPI Difference",
    mark_type="Circle",                   # or "Square"
    columns=["MIN(1)"],                   # dummy axis so there is no real x-axis
    color="Sales Color Filter",           # a string field returning "BAD"/"GOOD"
    label="Sales Difference",             # AGG calc returning a % value
    axis_fixed_range={"min": 0, "max": 1, "scope": "cols"},
    mark_sizing_off=True,
    customized_label="<Sales Difference> vs PY",
    color_map={"BAD": "#e15759", "GOOD": "#03a44e"},
    text_format={"Sales Difference": "p0.00%"},
)
```

**Rules:**
- `MIN(1)` formula with `user:unnamed` attribute is the standard dummy-column trick to get a fixed-width pill.
- `axis_fixed_range` must be `{"min": 0, "max": 1, "scope": "cols"}` to match the dummy measure range.
- `mark_sizing_off=True` prevents the circle from scaling with data.
- `customized_label` template uses `<FieldName>` placeholders; suffix text (e.g. `" vs PY"`) is appended literally.
- `color_map` keys must exactly match string values returned by the color field.

### Non-Traditional Pie Mark — Rank Display

When you want to show a row-by-row rank number as a label without a real pie chart (wedge slices):

```python
# First define the rank calc with table_calc:
add_calculated_field(
    "Rank CY", "RANK_DENSE(sum([Current Year Sales]),'desc')",
    datatype="integer", field_type="ordinal", table_calc="Rows"
)

# Then use Pie mark with only `label` (no color, no wedge_size):
configure_chart(
    "Top 5 Locations",
    mark_type="Pie",
    rows=["State/Province"],
    label="Rank CY",
    sort_descending="SUM(Current Year Sales)",
    filters=[{"column": "State/Province", "top": 5, "by": "SUM(Current Year Sales)"}],
)
```

**Why Pie mark without color/wedge_size?** Tableau renders a full-width circle mark per row, which gives a clean round badge appearance for the rank number. The SDK routes this to `BasicChartBuilder` (not `PieChartBuilder`) when neither `color` nor `wedge_size` is provided.

### Donut Chart via extra_axes (configure_dual_axis)

This produces a donut chart where one ring shows the breakdown and the inner white circle creates the hole. It uses `extra_axes` on `configure_dual_axis` rather than the recipe path — use this when the donut is part of a larger multi-pane layout:

```python
configure_dual_axis(
    "Sales by Sub-Category",
    mark_type_1="Bar",       # main axis (Gantt bars etc.)
    mark_type_2="Circle",    # second axis
    columns=["..."],
    rows=["..."],
    extra_axes=[
        {
            "mark_type": "Pie",
            "color": "Measure Names",
            "measure_values": ["SUM(Sales CY)", "SUM(Sales PY)"],
            # SDK auto-adds [Multiple Values] as size for Pie+measure_values
        },
        {
            "mark_type": "Automatic",
            "mark_color": "#ffffff",  # white fill to cut out centre
        },
    ],
)
```

**Key rules:**
- The SDK automatically adds `[Multiple Values]` as the `size` encoding for any `extra_axes` pane whose `mark_type` is `"Pie"` and `measure_values` is non-empty. Do **not** add it manually.
- The Measure Names filter is always emitted **before** the Top N or categorical filters in the `<view>` XML.
- The white `Automatic` pane must come last in `extra_axes`.

### Row Dimension Header Suppression (hide_row_label)

When a chart has a dimension on the `rows` shelf but you don't want the dimension name displayed as a column header:

```python
configure_worksheet_style(
    "Top 5 Locations",
    hide_row_label="State/Province",  # pass the dimension field name
)
```

The SDK resolves this to a `<style-rule element="label"><format attr="display" field="..." value="false"/>` entry. Use for ranked lists, ordered text lists, etc. where the row labels are self-explanatory.

## Recipe Charts

These showcase-only charts are not plain `configure_chart(...)` calls. When the
user asks for the `all_supported_charts` workbook or explicitly asks for a
Lollipop, Donut, Butterfly, or Calendar chart, use
`configure_chart_recipe(...)` instead of adding recipe-specific MCP tools.

Supported `recipe_name` values:
- `lollipop`
- `donut`
- `butterfly`
- `calendar`

### Lollipop

Rules:
- Put the dimension in `rows` and repeat the same measure on both dual-axis positions.
- The first axis is the bar, the second axis is the circle.
- Keep the axes synchronized.
- Hide labels by default.
- Keep the bar size smaller than the circle size so the lollipop head is visible.

```python
configure_chart_recipe(
    worksheet_name="Lollipop Chart",
    recipe_name="lollipop",
    recipe_args={"dimension": "State/Province", "measure": "SUM(Sales)"},
)
```

### Donut

Rules:
- Use `min 0` on both dual-axis positions.
- Put the categorical split on the first pie.
- Put the sales label on the second pie.
- Make the second pie white so it cuts out the middle of the donut.
- The recipe auto-creates `min 0 = MIN(0)` when the default field is missing.

```python
configure_chart_recipe(
    worksheet_name="Donut Chart",
    recipe_name="donut",
    recipe_args={"category": "Category", "measure": "SUM(Sales)"},
)
```

### Butterfly

Rules:
- Use one bar axis for the left measure and one for the right measure.
- Reverse the first axis so the chart mirrors around the center.
- Do not synchronize the axes.

```python
configure_chart_recipe(
    worksheet_name="Butterfly Chart",
    recipe_name="butterfly",
    recipe_args={
        "dimension": "Region",
        "left_measure": "SUM(Sales)",
        "right_measure": "SUM(Quantity)",
    },
)
```

### Calendar

Rules:
- Because the default color formula uses `SUM([Sales])`, treat it as an aggregated nominal measure, not a plain dimension.
- Use `WEEK(Order Date)` on rows and `WEEKDAY(Order Date)` on columns.
- Use `DAYTRUNC(Order Date)` for the day labels.
- Apply a single `MY(Order Date)` filter member such as `202208`.
- The recipe auto-creates `Sales Over 400` when the default field is missing.

```python
configure_chart_recipe(
    worksheet_name="Calendar Chart",
    recipe_name="calendar",
)
```

## Filter Strategy

### Filter Types

| Filter Type | When to Use | Example |
|---|---|---|
| Categorical (basic) | Dimension with few values | `{"column": "Region"}` |
| Quantitative range | Date ranges, numeric ranges | `{"column": "Order Date", "type": "quantitative"}` |

### Which Filters to Add

Think about what the user will want to slice the data by:

```python
# Typical filter set for a sales dashboard
filters = [
    {"column": "Order Date", "type": "quantitative"},  # Time range
    {"column": "Region"},                               # Geographic filter
    {"column": "Category"},                             # Product filter
]
```

**Best practices:**
- Add filters to the **primary chart** (usually the map or main chart)
- Other charts will be filtered via dashboard filter actions
- Date range filter is almost always needed
- Put all-values categorical filters on the main chart; they'll appear as quick filters on the dashboard

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| dimension in columns + measure in rows for bar chart | Creates vertical bars (harder to read labels) | Swap: dimension in rows, measure in columns |
| Forgetting `sort_descending` | Bars in random order | Always sort bar charts |
| Using `color` for a measure on bar charts | Creates confusing gradient | Use color for dimensions, or omit |
| Not adding `tooltip` | Users can't get detail-on-demand | Always add at least one tooltip measure |
| Too many chart types in one dashboard | Visual chaos | Limit to 3-4 chart types max |

## Output Checklist

Before moving to Phase 3 (Dashboard Designer):
- [ ] Each chart answers a specific analytical question
- [ ] Chart types match the data relationship (comparison/trend/composition/geographic)
- [ ] Bar charts are sorted descending
- [ ] Maps have color + size + tooltip
- [ ] KPI cards have 5-8 well-ordered metrics
- [ ] Filters are attached to the primary chart
- [ ] All worksheets have descriptive names
