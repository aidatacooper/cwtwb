---
step: 8
level: "⭐⭐⭐ Advanced"
demonstrates: "Parameters + LOD calculated fields + Map + Area charts + filters + dashboard actions — business executive demo"
description: Natural Language Prompt (Business Executive Demo) — Superstore Overview
---

# Create a Superstore Profitability Overview Dashboard

Please use cwtwb mcp tool create a new Tableau workbook using the Superstore template and save it to output directory. answer me in english.

## The Business Context
I want to build a "Superstore Profitability Overview" dashboard that helps our executives analyze performance across geography, product categories, and customer segments. We also need to run "What-If" scenarios to forecast sales and evaluate different profitability targets.

## What-If Capabilities
To let executives simulate different scenarios, please add three interactive parameter sliders:
1. **Target Profit**: A slider ranging from -$30,000 to $100,000 in $10,000 increments, starting at $10,000.
2. **Churn Rate**: A highly sensitive slider to simulate customer loss. Range it from 0% to 25% (0.000 to 0.250) with tiny increments of 0.001. Default it to 16.8% and format it as a percentage (`p0.00%`).
3. **New Business Growth**: A slider to estimate revenue from new customer acquisition. Range it from 0% to 100% (0 to 1), with no specific steps, defaulted to 59.9% (`p0%`).

## Key Business Metrics
We need to derive some custom metrics from the base data (`Sales`, `Profit`, `Quantity`, `Order ID`, etc.):
- **Profit Ratio**: Simply the ratio of total `Profit` over total `Sales` (real).
- **Profit per Customer**: Total `Profit` divided by the distinct count of `Customer Name`.
- **Profit per Order**: Total `Profit` divided by the distinct count of `Order ID`.
- **Order Profitable?**: An LOD calculation to determine if a specific order was profitable: check if the fixed SUM of `Profit` for a given `Order ID` is greater than 0 (returns a string).
- **Sales estimate**: Apply our What-If parameters to `Sales`—specifically, decrease `Sales` by the `Churn Rate` and increase it by the `New Business Growth`.
- **Units estimate**: Do the exact same "What-If" math on `Quantity` instead of sales, and round it to the nearest whole number (integer). 

## Dashboard Visualizations
I need four main views created for the dashboard:

1. **Total Sales (KPI Header)**
Create a clean text-based KPI summary named "Total Sales". It should naturally display seven key overall metrics: the sum of `Sales`, sum of `Profit`, our new `Profit Ratio`, `Profit per Order`, `Profit per Customer`, the average `Discount`, and the sum of `Quantity`.

2. **SaleMap (Geographical Performance)**
Build a Map chart showing our performance by `State/Province`. 
- Make the size of the points represent total `Sales`.
- Color the points using our continuous `Profit Ratio` metric so we can instantly spot underperforming regions. 
- The tooltip should simply display total `Profit`.
- Add filters for `Order Date` (a range), `Region`, `State/Province`, and `Profit Ratio` (a range) and show them on the worksheet.

3. **SalesbySegment (Trend by Customer Segment)**
We need a monthly Area chart showing `Segment` vs total `Sales`. 
- The columns should track the exact month of `Order Date`.
- Use our "Order Profitable?" calculated metric for the colors to distinguish healthy sales.
- Show `Profit` in the tooltip.
- Ensure this chart shares the exact same filters as the map (Order Date, Region, Profit Ratio).

4. **SalesbyProduct (Trend by Category)**
Create another Area chart just like the Segment one above, but this time plot `Category` vs total `Sales` across the months. It should use the identical color encoding ("Order Profitable?"), tooltips, and shared filters.

## Dashboard Layout & Flow
Please place these charts onto a dashboard named "Overview" (size: 1200 width by 1050 height). Please use your JSON layout generation capabilities to assemble this.

- Put the **Total Sales KPI** as a narrow container strip (about 120px tall) running across the very top.
- Below the KPI strip, divide the remaining space into a main content area (left side, taking up the vast majority, about a weight of 6) and a narrow filter sidebar (right side, fixed at 132px).
- In the **main content area (left)**, stack the **SaleMap** on top (taking up slightly over half the vertical space, weight 55) and put the two area charts (**SalesbySegment** and **SalesbyProduct**) side-by-side on the bottom half with equal width.
- In the **filter sidebar (right)**, line up the interactive controls strictly from top to bottom: the `Order Date` range filter, the `Region` dropdown, a multi-select dropdown for `State/Province`, the `Profit Ratio` filter, and finally the `Profit Ratio` color legend. Do NOT include any of the parameter sliders (Target Profit, Churn Rate, New Business Growth) in the layout json.

## Interactivity (Dashboard Actions)
To make the dashboard feel alive and interactive for the executives, please add an action so that when someone clicks on a state in the **SaleMap**, it automatically performs a **filter operation** on the two Area charts (`SalesbySegment` and `SalesbyProduct`) to only show data for that specific `State/Province`.
