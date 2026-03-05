---
description: Natural Language Prompt (English) — Fully replicating the Overview dashboard from Overview.twb
---

# Help me create a Superstore Profitability Overview Dashboard

Please create a workbook using the Superstore template and save it to `output/overview_natural_en.twb`.

## Analysis Context

I want to analyze the profitability of our stores across three dimensions: geography, product categories, and customer segments. I also need to perform "What-If" analysis using parameters.

## Three What-If Analysis Parameters

Please add three slider controls for me:
- **Target Profit**: Default $10,000, range from -$30,000 to $100,000, with a step of 10,000.
- **Churn Rate**: Default 0.168, range from 0 to 0.25, with a step of 0.001. Format as `p0.00%`.
- **New Business Growth**: Default 0.599, range from 0 to 1 (no step). Format as `p0%`.

## Six Analytical Metrics

Please create these calculated fields:

- **Profit Ratio** = `SUM([Profit])/SUM([Sales])` (datatype: real)
- **Profit per Customer** = `SUM([Profit])/COUNTD([Customer Name])` (datatype: real)
- **Profit per Order** = `SUM([Profit])/COUNTD([Order ID])` (datatype: real)
- **Order Profitable?** = `{FIXED [Order ID]:SUM([Profit])}>0` (datatype: string, this is an LOD expression that calculates profitability at the order level)
- **Sales estimate** = `[Sales]*(1-[Parameters].[Churn Rate])*(1+[Parameters].[New Business Growth])` (datatype: real)
- **Units estimate** = `ROUND([Quantity]*(1-[Parameters].[Churn Rate])*(1+[Parameters].[New Business Growth]),0)` (datatype: integer)

## Four Visualizations

### 1. Total Sales (KPI Card)

Create a **Text** KPI bar showing seven core metrics using measure_values mode:
`["SUM(Sales)", "SUM(Profit)", "Profit Ratio", "Profit per Order", "Profit per Customer", "AVG(Discount)", "SUM(Quantity)"]`

### 2. SaleMap (Geographic Map)

Create a **Map** chart with `geographic_field` set to `State/Province`.
- **Color** by `Profit Ratio` (this will create an interpolated/continuous color encoding)
- **Size** by `SUM(Sales)`
- **Tooltip**: `SUM(Profit)`

Add these filters to the SaleMap worksheet (all-values, showing all by default):
- `{"column": "Order Date", "type": "quantitative"}` (range filter)
- `{"column": "Region"}` (categorical, all values)
- `{"column": "State/Province"}` (categorical, all values)
- `{"column": "Profit Ratio", "type": "quantitative"}` (range filter)

### 3. SalesbySegment (Monthly Area Chart)

Create an **Area** chart:
- **Columns**: `["MONTH(Order Date)"]`
- **Rows**: `["Segment", "SUM(Sales)"]`
- **Color** by `Order Profitable?`
- **Tooltip**: `SUM(Profit)`

Add these filters (shared from SaleMap, all-values):
- `{"column": "Order Date", "type": "quantitative"}`
- `{"column": "Region"}`
- `{"column": "Profit Ratio", "type": "quantitative"}`

### 4. SalesbyProduct (Monthly Area Chart)

Create an **Area** chart:
- **Columns**: `["MONTH(Order Date)"]`
- **Rows**: `["Category", "SUM(Sales)"]`
- **Color** by `Order Profitable?`
- **Tooltip**: `SUM(Profit)`

Add these filters (shared from SaleMap, all-values):
- `{"column": "Order Date", "type": "quantitative"}`
- `{"column": "Region"}`
- `{"column": "Profit Ratio", "type": "quantitative"}`

## Dashboard Layout (936 × 650)

The dashboard, named "Overview", should have the following structure. Please use the JSON layout tool to create the layout, then pass the file path to generate the dashboard.

The overall layout is **vertical** with three sections stacked from top to bottom:

1. **Top: KPI bar** (fixed_size: 41px) — Contains the "Total Sales" worksheet
2. **Middle + Bottom: Main content area** — Takes remaining space, split **horizontally** into two columns:
   - **Left: Main content** (weight 6, ~84%) — Split **vertically**:
     - **Upper: SaleMap** (weight 55) — The map visualization
     - **Lower: Two area charts side by side** (weight 45) — Split **horizontally**:
       - Left: **SalesbySegment** (weight 1)
       - Right: **SalesbyProduct** (weight 1)
   - **Right: Filter sidebar** (fixed_size: 132px) — A **vertical** container with these controls from top to bottom:
     - `{"type": "filter", "worksheet": "SaleMap", "field": "Order Date", "mode": ""}` (Order Date range filter)
     - `{"type": "filter", "worksheet": "SaleMap", "field": "Region", "mode": "dropdown"}` (Region dropdown)
     - `{"type": "filter", "worksheet": "SaleMap", "field": "State/Province", "mode": "checkdropdown"}` (State multi-select)
     - `{"type": "filter", "worksheet": "SaleMap", "field": "Profit Ratio", "mode": ""}` (Profit Ratio range filter)
     - `{"type": "color", "worksheet": "SaleMap", "field": "Profit Ratio"}` (Profit Ratio color legend)

## Five Interaction Actions

1. **State Filter**: When clicking on the SaleMap, filter **all other sheets on the Overview dashboard** (excluding SaleMap itself) by `State/Province`. (action_type=filter, source=SaleMap, target=each of SalesbyProduct, SalesbySegment, Total Sales, fields=["State/Province"])

2. **Month Highlight**: From SalesbySegment and SalesbyProduct (excluding SaleMap and Total Sales), highlight on `MONTH(Order Date)` across the area charts. (action_type=highlight, fields=["Order Date"])

3. **Monthly Sales Filter**: From SalesbySegment and SalesbyProduct, filter the SaleMap by all fields. (action_type=filter, source=SalesbySegment and SalesbyProduct, target=SaleMap, fields=["State/Province"])

4. **State Highlight (map)**: From all sheets, highlight on `State/Province` across the map. (action_type=highlight, fields=["State/Province"])

Note: Due to tool constraints, implement the primary two actions:
- **State Filter** (filter): source=SaleMap → target=SalesbyProduct, fields=["State/Province"]
- **State Filter** (filter): source=SaleMap → target=SalesbySegment, fields=["State/Province"]
- **State Highlight** (highlight): source=SaleMap → target=SalesbySegment, fields=["State/Province"]
