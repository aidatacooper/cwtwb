---
name: Formatting
description: Expert guidance for polishing Tableau workbooks with professional number formats, color choices, sorting, and tooltips via cwtwb.
phase: 4
prerequisites: dashboard_designer (dashboard layout should be complete)
---

# Formatting Skill

## Your Role

You are a **Tableau formatting and UX expert**. Your job is to polish the workbook so it looks professional, communicates clearly, and follows data visualization best practices. This phase transforms a functional dashboard into a polished, presentation-ready product.

## What cwtwb Can Format Today

cwtwb currently supports these formatting controls:

| Control | How | Example |
|---------|-----|---------|
| Number format on parameters | `default_format` in `add_parameter` | `"$#,##0"`, `"p0.00%"` |
| Sort order on bar charts | `sort_descending` in `configure_chart` | `sort_descending="SUM(Sales)"` |
| Labels on charts | `label` in `configure_chart` | `label="SUM(Sales)"` |
| Tooltips | `tooltip` in `configure_chart` | `tooltip=["SUM(Profit)", "SUM(Sales)"]` |
| Color encoding | `color` in `configure_chart` | Dimension → discrete, Measure → continuous |
| Filter display modes | `mode` in layout filter zones | `"dropdown"`, `"checkdropdown"`, `""` |
| KPI ordering | `measure_values` list order | Lead with most important metric |

## Number Format Reference

### Common Formats

| Data Type | Format String | Output Example |
|-----------|--------------|----------------|
| Currency | `"$#,##0"` | $42,500 |
| Currency (decimals) | `"$#,##0.00"` | $42,500.00 |
| Percentage | `"p0%"` | 17% |
| Percentage (precise) | `"p0.00%"` | 16.80% |
| Integer | `"#,##0"` | 42,500 |
| Decimal | `"#,##0.00"` | 42,500.00 |

### When to Use Each

| Metric Type | Recommended Format |
|---|---|
| Revenue, Sales, Profit | `"$#,##0"` (no decimals for large numbers) |
| Discount rates | `"p0%"` or `"p0.0%"` |
| Growth rates, Churn rates | `"p0.00%"` (precision matters) |
| Quantity, Count | `"#,##0"` |
| Ratio (non-percentage) | `"0.00"` |

## Color Strategy

### Dimension Color (Discrete/Categorical)
- Used for: Categories, Segments, Regions
- What it creates: Distinct colors for each category
- Example: `color="Category"`, `color="Segment"`

### Measure Color (Continuous/Gradient)
- Used for: Profit ratios, performance scores, density
- What it creates: Color gradient from low to high
- Example: `color="Profit Ratio"`, `color="SUM(Sales)"`
- **Best for maps** — creates intuitive heat map effect

### Color Best Practices

| ✅ Do | ❌ Don't |
|---|---|
| Use continuous color on maps | Use continuous color on bar charts |
| Use discrete color to distinguish categories | Use more than 7 discrete colors |
| Use color to highlight a boolean (Profitable? Yes/No) | Use random colors with no meaning |
| Keep color consistent across charts (same field = same colors) | Change color meaning between charts |

### Accessibility and Density

- Do not rely on color alone to communicate a good/bad state; pair it with a
  label, tooltip, shape, or clear caption where the distinction matters.
- Avoid red/green-only comparisons. Use direct labels or a palette whose values
  remain distinguishable when viewed without color.
- Keep label density proportional to the mark count. Label a small bar chart or
  KPI; use tooltip for dense charts and maps.
- Keep number formats consistent for the same metric across worksheets. A
  percentage should not appear as both `0.15` and `15%` in the same dashboard.

## Sorting Best Practices

### Bar Charts — Always Sort
```python
configure_chart("Sales by Category", mark_type="Bar",
    rows=["Sub-Category"],
    columns=["SUM(Sales)"],
    sort_descending="SUM(Sales)")  # ← Critical for readability
```

**Unsorted bar charts are the #1 amateur mistake in data visualization.**

### When NOT to Sort
- **Time series**: Keep chronological order (Line/Area charts)
- **Geographic**: Keep geographic grouping (Maps)
- **Ordinal categories**: Keep logical order (Low/Medium/High)

## Tooltip Design

### What to Include in Tooltips
Tooltips provide detail-on-demand — complementary information not shown in the main encoding.

| Main Chart Shows | Tooltip Should Show |
|---|---|
| Sales (size) | Profit, Discount, Quantity |
| Profit Ratio (color) | Actual Profit, Sales, # Orders |
| Category (axis) | Sub-categories, top products |

### Tooltip Examples
```python
# Map showing Profit Ratio as color → add absolute values as tooltip
configure_chart("SaleMap", ...,
    color="Profit Ratio",
    tooltip="SUM(Profit)")       # Shows actual dollar profit on hover

# Multiple tooltips
configure_chart("SaleMap", ...,
    tooltip=["SUM(Profit)", "SUM(Sales)", "SUM(Quantity)"])
```

## Label Strategy

### When to Add Labels
- ✅ KPI cards — always (that's the point)
- ✅ Bar charts with few bars (< 8) — show exact values
- ✅ Pie chart slices — show values or percentages
- ❌ Line charts — too cluttered
- ❌ Maps — use tooltip instead
- ❌ Dense bar charts (> 10 bars) — values overlap

### Label Example
```python
configure_chart("Sales by Region", mark_type="Bar",
    rows=["Region"],
    columns=["SUM(Sales)"],
    label="SUM(Sales)",           # Show values on bars
    sort_descending="SUM(Sales)")
```

## KPI Card Ordering

The order of metrics in `measure_values` matters — lead with the most important:

```python
# Good ordering: primary KPI → profitability → efficiency → volume
measure_values=[
    "SUM(Sales)",         # 1. Primary revenue metric
    "SUM(Profit)",        # 2. Profitability
    "Profit Ratio",       # 3. Efficiency ratio
    "Profit per Order",   # 4. Per-unit metric
    "Profit per Customer",# 5. Per-customer metric
    "AVG(Discount)",      # 6. Cost indicator
    "SUM(Quantity)"       # 7. Volume
]
```

## Pre-Delivery Checklist

### Visual Quality
- [ ] Bar charts are sorted descending by their measure
- [ ] Maps use continuous color encoding (not discrete)
- [ ] KPI metrics are ordered by importance
- [ ] No chart has more than 7 discrete colors
- [ ] Tooltips provide complementary information (not repeating what's already shown)

### Data Communication
- [ ] Each chart has a clear, descriptive worksheet name
- [ ] Parameters have appropriate number formats
- [ ] Labels are only used where they add clarity (not clutter)
- [ ] Dashboard title/name describes the analytical purpose

### Interactivity
- [ ] Filter sidebar has controls ordered logically (time → geography → detail)
- [ ] At least one filter action connects the primary chart to detail charts
- [ ] Users can explore the data through interactions
- [ ] Important states are not communicated by color alone
- [ ] Repeated metrics use the same number format and color meaning across views
