---
name: Quality Review
description: Review a validated Tableau workbook for visual clarity, interaction quality, accessibility, and maintainability risks.
phase: 5.5
prerequisites: validation (workbook should be saved and structurally validated)
---

# Quality Review Skill

## Your Role

You are a workbook reviewer. After structural validation, assess whether the
workbook is understandable, maintainable, and aligned with the intended
analytical story. This is an advisory review, not proof that Tableau can open
the workbook.

## Workflow

```text
1. Confirm save_workbook and validate_workbook have completed.
2. Review worksheet names, chart choices, filters, actions, layout, labels, and colors.
3. Record findings with severity, evidence, impact, and a cwtwb-oriented fix.
4. Re-run validation after any workbook change.
5. Report remaining human-judgment items separately from deterministic issues.
```

## Review Dimensions

| Dimension | Check |
|---|---|
| Audience adaptation | Complexity, filters, and interactions fit the audience's time budget. |
| Message alignment | Title, context, and chart sequence support a clear decision or question. |
| Chart usage | Time trends use Line/Area, bars are sorted, and pies remain readable. |
| Layout and story | KPI -> primary -> detail hierarchy, scan path, and progressive disclosure are visible. |
| Color and accessibility | Color has a stable meaning and important states have a non-color cue. |
| Text and context | Units, date scope, labels, captions, and tooltips explain the visual without clutter. |
| Typography and maintainability | Hierarchy is readable; worksheet/calculation names and complex logic are documented. |

Classify the dashboard genre before applying defaults: `business_dashboard`,
`analytical`, `narrative`, `editorial`, or `technical`. Do not penalize a
narrative or technical visualization merely because it lacks executive KPIs.

## Evidence and Calibration

Start by recording strengths, then identify gaps. A "could be better" item is
not automatically a defect. Scale severity to the impact on a user making the
intended decision.

- XML evidence can support structural claims such as worksheet count, mark
  types, actions, labels, and field names.
- A rendered screenshot or human review is required for visual claims about
  hierarchy, readability, clipping, contrast, spacing, and typography.
- Do not assign a numeric or letter score from TWB XML alone. Until a dedicated
  review tool can combine structural evidence with rendered images, provide
  dimension findings and an explicit confidence level instead.

## Finding Format

```markdown
### <severity>: <short finding>

Evidence: <worksheet, dashboard, field, or observed configuration>
Impact: <what a workbook user or maintainer cannot reliably understand>
Suggested fix: <specific cwtwb tool call, skill phase, or human decision>
```

Use `blocker` only for an issue that prevents the intended analysis. Use `high`
for a misleading or inaccessible result, `medium` for a strong usability risk,
and `low` for polish. Mark subjective items as `info`; do not turn taste into a
false deterministic score.

## Boundaries

- `validate_workbook` and `validate_workbook_api` establish structural and
  semantic validity; this review does not replace either result.
- Do not claim a visual issue was verified from XML alone. State when a
  screenshot or human review is required.
- Current cwtwb versions do not expose `review_workbook`; perform this review
  manually until a dedicated quality tool is implemented.

## Output Checklist

- [ ] Validation result is recorded separately from review findings.
- [ ] Each finding names evidence and an actionable next step.
- [ ] Human-judgment items are marked as such.
- [ ] Workbook is revalidated after changes.
- [ ] Strengths are recorded before gaps, and every visual claim identifies its evidence source.
