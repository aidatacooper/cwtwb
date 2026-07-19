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
1. Call list_worksheets and lock the exact worksheet name list
2. Plan the dashboard hierarchy from those names
3. Design the layout using generate_layout_json
4. Create the dashboard with add_dashboard(layout=<json_path>)
5. Add interaction actions with add_dashboard_action
6. Add concise worksheet captions where narrative context helps
```

## Information Hierarchy

- Put KPI summaries at the top.
- Give the primary chart the most space.
- Place detail views below or beside the primary chart.
- Use a fixed-width sidebar for filters and legends.
- Keep each dashboard focused on one analytical storyline.

### Dashboard Storyline

Choose a user and a decision before arranging worksheets. A reliable sequence is
**status -> explanation -> detail**: KPIs establish the current state, a primary
view explains the main change or comparison, and one or two detail views support
follow-up questions. Do not add a chart unless it has a distinct role in that
sequence.

For filters, prefer a consistent order: time first, then geography, then product
or customer detail. Use filter actions for a precise drill path and highlight
actions when preserving the surrounding context matters more than narrowing it.

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

- Always start by calling `list_worksheets` and copy worksheet names exactly.
- Use only the canonical container DSL fields: `type`, `direction`, `children`.
- Never use `zones` as a container child field in layout JSON.
- Never use absolute-position schemas (`x/y/w/h`, `dashboard`, `zone`) as layout input.
- Use `fixed_size` for KPI rows and filter sidebars.
- Use `weight` for the main analytical areas.
- Do not pass a large inline layout dict to `add_dashboard`.
- Generate a layout JSON file first, then pass the file path to `add_dashboard`.
- Prefer filling a small template over free-form structure generation.

Execution order (strict):

```text
list_worksheets
-> generate_layout_json
-> add_dashboard(layout=<generated_json_path>)
```

Minimal stable template:

```json
{
  "type": "container",
  "direction": "vertical",
  "children": [
    {
      "type": "container",
      "direction": "horizontal",
      "fixed_size": 56,
      "children": [
        {"type": "worksheet", "name": "KPI 1"},
        {"type": "worksheet", "name": "KPI 2"}
      ]
    },
    {
      "type": "container",
      "direction": "horizontal",
      "children": [
        {"type": "worksheet", "name": "Primary View", "weight": 2},
        {"type": "worksheet", "name": "Secondary View", "weight": 1}
      ]
    }
  ]
}
```

Example structure:

```json
{
  "type": "container",
  "direction": "vertical",
  "children": [
    {
      "type": "container",
      "direction": "horizontal",
      "fixed_size": 56,
      "children": [
        {"type": "worksheet", "name": "KPI Sales"},
        {"type": "worksheet", "name": "KPI Profit"}
      ]
    },
    {
      "type": "container",
      "direction": "horizontal",
      "children": [
        {"type": "worksheet", "name": "Sales Map", "weight": 55},
        {
          "type": "container",
          "direction": "vertical",
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
      "type": "container",
      "direction": "horizontal",
      "children": [
        {"type": "worksheet", "name": "Sales Trend"},
        {"type": "worksheet", "name": "Sub-Category Breakdown"}
      ]
    }
  ]
}
```

Older generated JSON that uses `{"type": "horizontal"}` or
`{"type": "vertical"}` for containers is still accepted, but prefer the
canonical `{"type": "container", "direction": ...}` shape for new prompts.

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
- Layout JSON uses `zones` instead of `children`.
- Layout JSON references worksheet names not present in `list_worksheets`.
- No filter sidebar for an interactive dashboard.
- Actions that do not match the analytical storyline.
- Captions that repeat the worksheet title instead of adding meaning.
- Treating every dashboard like an executive dashboard when a detail view would be clearer.

## Output Checklist

- `list_worksheets` was called and worksheet names were locked before layout generation.
- Dashboard has a clear KPI -> primary -> detail hierarchy.
- Layout JSON was generated before `add_dashboard`.
- `add_dashboard` consumed a layout JSON file path rather than a large inline dict.
- At least one interaction action supports the main analysis flow.
- URL and go-to-sheet actions are used only where they add clarity.
- Key analytical worksheets have concise captions when narrative context helps.
- [ ] KPI -> primary view -> detail is visible without relying on a caption alone.
- [ ] Filters follow time -> geography -> detail unless the business workflow requires another order.
