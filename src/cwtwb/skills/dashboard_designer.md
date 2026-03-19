---
name: Dashboard Designer
description: Expert guidance for creating professional Tableau dashboard layouts, filter panels, worksheet captions, and interaction actions via cwtwb.
phase: 3
prerequisites: chart_builder (all worksheets should be ready)
---

# Dashboard Designer Skill

## Your Role

You are a Tableau dashboard design expert. Your job is to arrange worksheets
into a cohesive, interactive dashboard with a clear information hierarchy.

## Workflow

```text
1. Plan the dashboard hierarchy
2. Design the layout using generate_layout_json
3. Create the dashboard with add_dashboard
4. Add interaction actions with add_dashboard_action
5. Add concise worksheet captions where narrative context helps
```

## Information Hierarchy

- Put KPI summaries at the top.
- Give the primary chart the most space.
- Place detail views below or beside the primary chart.
- Use a fixed-width sidebar for filters and legends.
- Keep each dashboard focused on one analytical storyline.

## Common Layout Pattern

```text
Top: KPI summary row
Middle left: primary chart
Middle right: filters and legends
Bottom: one or two detail charts
```

Recommended defaults:

- Dashboard size: `1200 x 800`
- KPI row height: `40-60px`
- Filter sidebar width: `120-150px`
- Total worksheet count per dashboard: `4-6`

## Layout JSON Rules

- Use `fixed_size` for KPI rows and filter sidebars.
- Use `weight` for the main analytical areas.
- Do not pass a large inline layout dict to `add_dashboard`.
- Generate a layout JSON file first, then pass the file path to `add_dashboard`.

Example structure:

```json
{
  "type": "vertical",
  "children": [
    {
      "type": "horizontal",
      "fixed_size": 56,
      "children": [
        {"type": "worksheet", "name": "KPI Sales"},
        {"type": "worksheet", "name": "KPI Profit"}
      ]
    },
    {
      "type": "horizontal",
      "children": [
        {"type": "worksheet", "name": "Sales Map", "weight": 55},
        {
          "type": "vertical",
          "fixed_size": 132,
          "children": [
            {"type": "filter", "worksheet": "Sales Map", "field": "Order Date", "mode": "dropdown"},
            {"type": "filter", "worksheet": "Sales Map", "field": "Region", "mode": "dropdown"},
            {"type": "color", "worksheet": "Sales Map", "field": "Profit Ratio"}
          ]
        }
      ]
    },
    {
      "type": "horizontal",
      "children": [
        {"type": "worksheet", "name": "Sales Trend"},
        {"type": "worksheet", "name": "Sub-Category Breakdown"}
      ]
    }
  ]
}
```

## Interaction Actions

### Filter Action

Use filter actions when the primary chart should drive supporting detail views.

```python
add_dashboard_action(
    dashboard_name="Executive Overview",
    action_type="filter",
    source_sheet="Sales Map",
    target_sheet="Sub-Category Breakdown",
    fields=["State/Province"],
    event_type="on-select",
)
```

Best practices:

- Use it from the main chart to secondary detail charts.
- Choose the field that matches the analytical drill path.
- Always keep the action easy to explain to a business user.

### Highlight Action

Use highlight actions for softer cross-chart coordination.

```python
add_dashboard_action(
    dashboard_name="Executive Overview",
    action_type="highlight",
    source_sheet="Sales Trend",
    target_sheet="Sub-Category Breakdown",
    fields=["Order Date"],
)
```

Best practices:

- Prefer highlight when you want comparison without fully filtering away context.
- Use it for shared time periods or shared dimensions.

### Go-To-Sheet Action

Use go-to-sheet actions for a clear overview-to-detail flow.

```python
add_dashboard_action(
    dashboard_name="Executive Overview",
    action_type="go-to-sheet",
    source_sheet="Sales Map",
    target_sheet="State Detail",
    caption="Open State Detail",
)
```

Best practices:

- Use this only on strong drill-down entry points.
- Keep the target sheet focused on a single deeper question.
- Pair it with a caption or title that makes the drill path obvious.

### URL Action

Use URL actions when analysis should open an external workflow or reference.

```python
add_dashboard_action(
    dashboard_name="Executive Overview",
    action_type="url",
    source_sheet="Sub-Category Breakdown",
    url="https://example.com/product-detail",
    caption="Open Product Detail",
)
```

Best practices:

- Keep the URL stable and task-oriented.
- Use it for business handoff, documentation, or downstream workflows.
- Avoid too many competing URLs on one dashboard.

## Worksheet Captions

Captions are a strong AI authoring feature. Use them to explain what a chart
is answering in one sentence.

```python
set_worksheet_caption(
    worksheet_name="Sales Trend",
    caption="Monthly sales trend after the current dashboard filters are applied."
)
```

Best practices:

- Keep captions short and analytical.
- Describe the question answered, not the XML mechanics.
- Use captions on primary or detail views, not every helper sheet.

## Common Pitfalls

- Too many charts on one dashboard.
- No filter sidebar for an interactive dashboard.
- Actions that do not match the analytical storyline.
- Captions that repeat the worksheet title instead of adding meaning.
- Treating every dashboard like an executive dashboard when a detail view would be clearer.

## Output Checklist

- Dashboard has a clear KPI -> primary -> detail hierarchy.
- Layout JSON was generated before `add_dashboard`.
- At least one interaction action supports the main analysis flow.
- URL and go-to-sheet actions are used only where they add clarity.
- Key analytical worksheets have concise captions when narrative context helps.
