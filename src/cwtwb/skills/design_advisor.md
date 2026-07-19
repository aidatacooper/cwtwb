---
name: Design Advisor
description: Turn workbook fields and business questions into a reviewable Tableau dashboard plan before cwtwb mutations begin.
phase: 0.5
prerequisites: governance, create_workbook or open_workbook, list_fields
---

# Design Advisor Skill

## Your Role

You are a dashboard planning advisor. Before creating worksheets, turn the
available fields and business questions into a small, reviewable plan. Recommend
only cwtwb capabilities that are known to exist; this skill produces a plan and
does not mutate the workbook.

This skill is informed by the design-spec workflow in Adam Mico's
[Tableau Dashboard Blueprint](https://github.com/adammico-lab/Tableau-Dashboard-Blueprint-BETA).
It independently adapts that workflow for cwtwb: the output must be directly
translatable into explicit cwtwb tool calls, not a generic dashboard brief.

## Workflow

```text
1. Read governance and create or open the workbook.
2. Call list_fields and use the displayed field names exactly.
3. Record the audience, decision, business questions, and chosen style.
4. Select 3-6 worksheets with one analytical question each.
5. Choose chart type, encodings, filters, and any required calculations.
6. Draft a canonical layout tree using the exact planned worksheet names.
7. Present the plan and assumptions for review before tool calls create worksheets.
```

## Input Checklist

- Available fields with datatype, role, and geographic/date signals when known.
- One to three business questions, ranked by importance.
- Audience and style: `executive`, `operational`, or `analytical`.
- Required time grain, comparison period, filters, and known business definitions.

When input is incomplete, state the missing assumption in the plan. Do not make
up fields, calculation definitions, targets, or data refresh expectations.

## Intake and Prioritization

Start by classifying each question. A dashboard that tries to answer every
possible question usually becomes a report wall rather than a decision tool.

| Priority | Meaning | Design treatment |
|---|---|---|
| P1 | Decision-critical: the user must act from it | Give it the KPI or primary-view position. |
| P2 | Explains the P1 result | Give it a supporting view or drill path. |
| P3 | Useful exploration | Expose through a filter, tooltip, or detail worksheet. |
| P4 | Reference-only | Do not place it on the first dashboard unless required. |

Ask or infer these constraints before planning:

- **Audience and time budget:** who uses the dashboard, how often, and how long
  they have to scan it.
- **Decision:** the concrete decision or follow-up action the dashboard should
  support, not just a topic such as "sales performance".
- **Comparison:** target, prior period, benchmark, or segment that gives a
  primary metric meaning.
- **Grain:** the expected time grain and entity grain; do not place daily,
  monthly, order-level, and customer-level measures together without an
  explicit reconciliation.
- **Constraints:** required filters, definitions, accessibility needs, screen
  size, and any fields that are unavailable or sensitive.

When only a schema is available, recommend questions conditionally. For example,
a date plus a measure supports a trend question, but does not prove which period
comparison the business needs.

## Audience Constraints

Use the audience to limit chart count, filters, tooltip density, and interaction
complexity. These are planning defaults, not a substitute for user research.

| Audience | Scan time | Dashboard charts | Filters | Tooltip / interaction posture |
|---|---:|---:|---:|---|
| Executive | 5-30 seconds | 4-6 | 0-2 | Short tooltips; scan-first, minimal filtering. |
| Manager | 1-3 minutes | 5-8 | 2-4 | Concise tooltips; light filtering and one drill path. |
| Analyst | 3-15 minutes | 6-10 | 4-6 | Richer tooltips; purposeful cross-filtering. |
| Operations | 5-30 seconds | 3-5 | 1-2 | Alert/status-first; fast exception drill-down. |
| External | 30-90 seconds | 3-5 | 0-1 | Minimal controls; explain terms and preserve context. |

If a request exceeds the audience's likely cognitive budget, reduce the plan to
the P1/P2 questions and move P3 details to a second dashboard or drill-down.

## Planning Rules

- Give every worksheet one question and one primary measure.
- Start with a KPI only when a current-state metric is important to the decision.
- Choose a sorted bar for categorical comparison, a line/area chart for a time
  trend, a map only when location is analytical, and a scatterplot for a
  relationship between measures.
- Prefer one primary view, one to two supporting views, and no more than six
  worksheets on one dashboard.
- Recommend filters in time -> geography -> detail order unless the user has a
  stronger workflow reason.
- Propose a calculation only when an existing field cannot answer the question.
- Use chart types and layout structure supported by the current cwtwb capability
  registry; do not invent a dedicated MCP tool for a recipe or interaction.

### Question-to-Chart Mapping

For each P1/P2 question, document the decision pattern before naming a chart.

| Decision pattern | Default chart | cwtwb implementation notes |
|---|---|---|
| Current status against a target or prior period | KPI/Text plus a compact comparison | Use `Text` with ordered `measure_values`; state the missing target or comparison calculation. |
| Rank or compare categories | Sorted horizontal Bar | Dimension in `rows`, measure in `columns`, `sort_descending` by the displayed measure. |
| Change over time | Line or Area | Date in `columns`; declare the time grain and whether a breakdown is essential. |
| Contribution to a whole | Pie only for 5-6 categories; otherwise Bar/Tree Map | Label the main value and avoid a pie when precise comparison matters. |
| Geographic variation | Map only when location changes the decision | Add parent geography, continuous measure color, and tooltip detail. |
| Relationship between two measures | Scatterplot | State the entity grain; use color/size only for a decision-relevant third field. |
| Two dimensions with a measure | Heatmap | Keep the matrix scannable; otherwise filter, facet, or choose a bar chart. |

For every chart, specify:

- the question answered and priority;
- the primary measure, comparison/baseline, and grain;
- the dimension/date/geography fields and encodings;
- the required calculation, if one is needed;
- what belongs in the tooltip but not on the visual;
- a fallback chart when the category count or field quality makes the default
  unsuitable.

### KPI and Metric Hierarchy

- Limit the top row to the one to three P1 metrics needed to establish status.
- State the comparison period or target beside each KPI; a standalone total
  rarely explains whether action is needed.
- Use a consistent metric order: primary outcome, profitability/quality,
  efficiency, then volume or diagnostic metrics.
- If a KPI needs a calculation, name the business definition in the plan and
  hand the formula work to `calculation_builder` after approval.

### Filter, Tooltip, and Interaction Strategy

- Add a filter only when it supports a stated question or a real audience
  workflow. Do not expose every dimension just because it exists.
- Select filter form by cardinality: low-cardinality categorical fields suit a
  dropdown/checkdropdown; high-cardinality fields need a narrower scope or an
  alternate drill path.
- Scope filters deliberately. Put global analysis filters on the primary view;
  avoid accidental filtering of unrelated helper worksheets.
- Tooltips should provide complementary details: comparison, contribution,
  rank, or a small diagnostic value. They should not repeat every axis value.
- Use `filter` actions for a precise overview-to-detail path, `highlight` when
  comparison context must remain visible, and `go-to-sheet` only for a clear
  next analytical question.
- Document the action as `source worksheet -> target worksheet -> field(s) ->
  expected user result` before calling `add_dashboard_action`.

### Layout, Color, and Responsive Posture

- Build the first viewport around the P1 decision: title/context, KPI row when
  needed, primary view, then supporting detail.
- Use the existing canonical container DSL and prefer fixed-size KPI/filter
  zones with weighted analytical areas. Verify planned worksheet names with
  `list_worksheets` before generating the layout file.
- Assign color semantics once: categorical color identifies a stable dimension;
  continuous color represents magnitude or performance; alert colors require a
  text or tooltip counterpart.
- Describe colors by meaning, not just by hex code. cwtwb's existing chart
  surface may not expose a complete palette API, so record palette decisions as
  implementation guidance rather than promising unavailable controls.
- cwtwb does not currently generate Tableau device layouts. Record any mobile
  requirement as a manual implementation note: which views stack, which labels
  shorten, and which controls collapse or move to a second dashboard.

### Pre-Build Risk Review

Before mutation tools are called, identify the risks most likely to make the
delivered workbook weak or misleading:

| Risk | Planning response |
|---|---|
| Ambiguous metric definition | Keep it as an open question; do not invent a calculation. |
| Mixed grains or unsupported comparison | Add a calculation/design dependency and validate it before charting. |
| Too many categories or filters | Group, filter, split the dashboard, or change chart type. |
| Weak geographic rationale | Replace the map with a sorted comparison chart. |
| Audience overload | Remove P3/P4 content from the first dashboard. |
| Unavailable cwtwb control | Mark as manual Tableau work; do not imply tool support. |

List the top three risks in priority order and add a specific mitigation or a
human decision required to resolve each one.

## Required Design Specification

Return this specification before calling mutation tools. It is deliberately
more detailed than a worksheet list so the plan can be reviewed by a stakeholder
and translated into a reproducible build sequence.

```markdown
## Dashboard Plan: <name>

Audience and time budget: <who, how they use it, scan time>
Decision: <decision supported>
Style: executive | operational | analytical
Scope: <P1/P2 questions included; P3/P4 items deferred>
Assumptions:
- <explicit assumption or "None">

## Question and Metric Map

| Priority | Worksheet | Question / decision | Chart and rationale | Grain | Fields / encodings | Comparison | Required calculation |
|---|---|---|---|---|---|---|---|
| P1 | Sales Trend | Is monthly sales improving? | Line: ordered time trend | Month | MONTH(Order Date), SUM(Sales) | Prior year | YoY Sales % |

## KPI Hierarchy

| Order | Metric | Why it is shown | Format | Comparison / target |
|---|---|---|---|---|
| 1 | SUM(Sales) | Primary outcome | Currency | Prior year |

## Filters, Tooltips, and Interactions

| Type | Scope / source | Target | Fields or content | User outcome |
|---|---|---|---|---|
| Filter | Dashboard | All analytical views | Order Date, Region | Focus analysis period and geography |
| Action | Sales Trend | Sub-Category Detail | Order Date | Inspect detail for a selected period |

Tooltip guidance:
- <worksheet: complementary fields, order, and action cue>

Layout:
- <ASCII outline or canonical container-DSL-compatible hierarchy>
- Title/context: <purpose and time scope>
- Top: <KPI row or reason it is omitted>
- Middle: <primary view and filter/legend area>
- Bottom: <supporting detail views>

Color and accessibility:
- <semantic color assignment and non-color cue for important states>

Implementation sequence:
1. <calculations/parameters to define>
2. <worksheets to create and configure>
3. <layout file and dashboard actions>

Pre-build risks:
1. <risk -> mitigation or required decision>

Open questions:
- <business definition or field ambiguity>
```

Use exact field names returned by `list_fields`. Before building the dashboard,
verify that every planned chart type is present in `list_capabilities` or is an
approved `configure_chart_recipe` value. Use a canonical container hierarchy in
the plan; only `generate_layout_json` should write the final layout file.

## Handoff

After the human or agent reviews the plan:

1. Read `calculation_builder` for the required calculations.
2. Read `chart_builder` and create the worksheets named in the plan.
3. Read `dashboard_designer`, generate the layout file, and create the dashboard.
4. Preserve the plan as the explanation for chart, filter, and layout choices.

## Output Checklist

- [ ] All field references come from `list_fields`.
- [ ] Each worksheet has a distinct question and role in the storyline.
- [ ] Chart choices match the field shape and question.
- [ ] P1/P2 questions fit the audience time and interaction budget.
- [ ] KPI comparisons, filters, tooltips, interactions, and color semantics are specified.
- [ ] Layout uses the canonical cwtwb container DSL.
- [ ] The top three pre-build risks have mitigations or explicit human decisions.
- [ ] Assumptions and open questions are explicit.
- [ ] No workbook mutation happened before the plan was reviewed.
