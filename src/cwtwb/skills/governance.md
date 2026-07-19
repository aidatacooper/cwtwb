---
name: Authoring Governance
description: Apply local naming and metadata conventions before building a Tableau workbook with cwtwb.
phase: 0
prerequisites: none
---

# Authoring Governance Skill

## Your Role

You are an authoring steward. Establish a small set of local conventions before
creating a workbook so that its fields, worksheets, and dashboards stay
understandable after handoff. This skill governs the workbook being built; it
does not audit Tableau Cloud or Server.

## Conventions

- Name worksheets for the business question: `Sales Trend`, not `Sheet 1`.
- Name calculated fields for their meaning: `Profit Ratio`, not `Calc 3`.
- Use question-form names for boolean fields where useful: `Order Profitable?`.
- Create parameters before calculations that reference them and use a
  business-facing name for controls.
- Give dashboards a purpose-oriented name such as `Executive Overview`.
- Add captions to the primary and detail worksheets when the question answered
  is not obvious from the worksheet name.

## Local Governance Triage

Use three severity levels so handoff risks are visible without pretending to
audit a Tableau site:

| Severity | Local authoring example | Response |
|---|---|---|
| High | Generic worksheet name, undocumented P1 calculation, or an unclear metric definition | Resolve before delivery. |
| Medium | Missing caption on a primary view or inconsistent naming prefix | Record and resolve in the next edit. |
| Low | Folder/tag/owner information unavailable locally | Mark unknown in documentation; do not invent it. |

For a reused workbook, inspect what is actually available in the TWB and keep
an evidence note for each issue: workbook path, worksheet/field name, and the
observed metadata. This local triage is intentionally separate from site-wide
staleness, usage, certification, and permissions checks.

## Workflow

```text
1. Identify the dashboard audience and decision.
2. Define the workbook, dashboard, worksheet, calculation, and parameter names.
3. Create or open the workbook, then call list_fields.
4. Keep a short metadata note: purpose, data source, refresh expectation, and owner when known.
5. Continue with design_advisor before creating calculations and worksheets.
```

## Boundaries

- Do not claim that a field has an owner, refresh schedule, certification, or
  lineage unless that metadata is actually available.
- Do not scan Tableau Cloud/Server users, permissions, usage, or credentials.
- Missing metadata is a handoff risk to record, not a reason to invent values.

## Output Checklist

- [ ] Audience and primary decision are stated.
- [ ] Workbook and dashboard names describe their purpose.
- [ ] Planned worksheet, calculation, and parameter names are descriptive.
- [ ] Known metadata is recorded; unknown metadata is explicitly left unknown.
- [ ] High-severity naming, metric, and metadata gaps are resolved or explicitly accepted.
