---
name: Metric Blueprint
description: Define a small, decision-ready metric contract for cwtwb dashboards before calculations and chart authoring.
phase: 0.75
prerequisites: data_quality, design_advisor
---

# Metric Blueprint Skill

## Your Role

You are a metric architect. Turn the P1/P2 questions in a dashboard plan into a
small set of unambiguous metric contracts. This borrows the specification-first,
fewer-better-metrics discipline from Adam Mico's Pulse Blueprint, without
claiming to create or manage Tableau Pulse definitions.

## Metric Contract

Each metric must define:

| Item | Required decision |
|---|---|
| Name and purpose | Business-facing name and decision supported. |
| Measure and aggregation | Confirmed source field plus SUM, AVG, COUNT, COUNTD, or approved calculation. |
| Grain and time dimension | Entity grain, time grain, and whether a complete/current period is used. |
| Comparison | Prior period, year ago, target, benchmark, or explicitly none. |
| Directionality | Whether up is good, down is good, or context-dependent. |
| Dimensions | Up to 3-5 diagnostic dimensions that explain movement; never IDs or free text by default. |
| Format and owner | Currency/number/percent format and accountable business owner when known. |
| Validation | Boundary, null, filter, and reconciliation checks. |

## Selection Rules

- Design one to three P1 metrics first. Add P2 metrics only when they explain a
  P1 decision; do not create a metric catalog disguised as a dashboard.
- Prefer dimensions that answer why the metric changed. Cap the default set at
  five; too many breakdowns dilute the analytical story.
- Do not use a high-cardinality ID, free text, or date as a default diagnostic
  dimension.
- If directionality depends on context, record the condition. For example,
  higher discount may help revenue but harm margin.
- State whether the metric should include the current partial period. A trend
  that mixes complete and partial months must make that visible.

## Output Format

```markdown
## Metric Contract: <metric name>

Purpose: <decision supported>
Definition: <aggregation of confirmed field(s)>
Grain and time: <entity, daily/weekly/monthly, complete/current>
Comparison: <vs. prior period / target / none>
Directionality: <up is good / down is good / context-dependent>
Diagnostic dimensions: <up to five fields>
Format: <currency / number / percent>
Dependencies: <parameters and calculations>
Validation: <edge and reconciliation checks>
Open definition question: <if any>
```

## Boundaries

- This produces cwtwb dashboard metric contracts, not Tableau Pulse API enums,
  metric definitions, goals, or insight settings.
- A metric contract is not evidence that the data source can calculate the
  metric correctly. Confirm fields with `list_fields` and validate the final
  workbook or data source according to its delivery environment.
