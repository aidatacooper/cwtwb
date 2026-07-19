---
name: Workbook Documentation
description: Prepare concise or detailed workbook handoff documentation and metric definitions from verified cwtwb metadata.
phase: 6
prerequisites: validation, quality_review
---

# Workbook Documentation Skill

## Your Role

You are a documentation author. Create a handoff package that lets a business
user understand the dashboard and lets a maintainer understand its fields,
calculations, filters, and known limitations. The structure is informed by Adam
Mico's Tableau Scribe, but cwtwb currently guides manual Markdown authoring; it
does not yet expose automatic documentation generation.

## Choose Depth

| Depth | Audience | Include |
|---|---|---|
| Brief | Business users and reviewers | Purpose, audience, KPI definitions, filters, primary interactions, data period, owner/contact when known. |
| Detailed | Maintainers and analytics teams | Brief content plus worksheet inventory, calculation contracts, data connection notes, actions, quality findings, assumptions, and change log. |

## Evidence Rules

- Derive field names, worksheet names, dashboards, calculations, filters, and
  actions from the workbook or cwtwb tool outputs.
- Explain a calculation in plain language only when its formula and intended
  grain are confirmed; otherwise state that a business definition is pending.
- Separate observed facts from inferred usage guidance.
- Do not expose datasource credentials, filesystem secrets, or sensitive sample
  values in the documentation.

## Required Markdown Structure

```markdown
# <Dashboard Name>

## Purpose and Audience
## Data Scope and Refresh Context
## KPI and Metric Definitions
## Filters and Interactions
## Worksheet Guide
## Calculations and Parameters
## Known Assumptions and Limitations
## Validation and Quality Review
## Ownership and Change History
```

For the worksheet guide, document the question answered, chart type, key fields,
filters, and expected user action. For each non-trivial calculation, include its
calculation design contract rather than pasting unexplained Tableau syntax.

## Delivery Checklist

- [ ] Brief or detailed depth is selected for the actual reader.
- [ ] Every metric definition states grain, comparison, and directionality.
- [ ] Validation evidence and quality findings are kept separate.
- [ ] Unknown ownership, refresh, certification, or lineage is marked unknown.
- [ ] No credentials, private record values, or fabricated metadata appear.
