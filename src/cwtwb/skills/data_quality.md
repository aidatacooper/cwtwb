---
name: Data Quality Triage
description: Assess the available cwtwb field schema for local authoring risks before planning a Tableau workbook.
phase: 0
prerequisites: create_workbook or open_workbook, list_fields
---

# Data Quality Triage Skill

## Your Role

You are a local schema reviewer. Inspect the fields available to cwtwb before
designing charts or calculations, and identify only evidence-backed authoring
risks. This is the cwtwb adaptation of the schema-hygiene mindset in Adam
Mico's Data Quality Sentinel; it is not a Tableau Cloud/Server scan and does
not profile row-level distributions.

## Workflow

```text
1. Create or open the workbook, then call list_fields.
2. Classify candidate fields: time, measure, dimension, geography, ID, parameter, calculation.
3. Map each P1/P2 business question to the fields required to answer it.
4. Record schema gaps, naming/type risks, and calculation complexity risks.
5. Stop or reframe planning when a P1 question has no credible field mapping.
```

## Checks

| Domain | Local check | Action when it fails |
|---|---|---|
| Schema fitness | A question has a measure, grouping field, and time field when trend is requested. | Request the missing field, use a supported derived calculation, or reframe the question. |
| Naming | Field names are cryptic, duplicated, or not business-facing. | Use captions/names in plan and document the source name. |
| Type and role | A likely date, numeric measure, boolean, or ID appears to be used in the wrong role. | Do not silently coerce it; confirm source semantics before charting. |
| Cardinality | A high-cardinality field is proposed as a visible color or axis. | Use a filter, Top N, grouping, or detail drill instead. |
| Calculation complexity | A planned calc needs nested LODs, deep branches, or cross-grain logic. | Create a calculation design contract and require validation cases. |
| Metadata | Description, owner, refresh, or certification is unknown. | Mark it unknown for documentation; never fabricate it. |

## Output Format

```markdown
## Local Schema Triage

Fit for planned dashboard: ready | ready_with_gaps | blocked

| Severity | Question / field | Evidence | Impact | Required decision |
|---|---|---|---|---|
| High | Retention trend | No date field in `list_fields` | Cannot establish period trend | Add a date or redesign as snapshot comparison |

Confirmed building blocks:
- Time: <field or unknown>
- Measures: <fields>
- Dimensions/geography: <fields>
- IDs excluded from visual encodings: <fields>
```

## Boundaries

- `list_fields` is schema context, not proof of null rates, value distributions,
  freshness, row-level quality, or certified status.
- Do not claim that data is clean, statistically representative, or production
  ready without a data-profile capability outside cwtwb.
- Route formula design to `calculation_builder`, dashboard planning to
  `design_advisor`, and site-level governance to the appropriate external
  Tableau process.
