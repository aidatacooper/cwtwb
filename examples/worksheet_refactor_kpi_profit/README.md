# Worksheet Refactor Example

This example demonstrates worksheet-level cloning plus local refactoring:

- Source workbook: `5 KPI Design Ideas (2).twb`
- Source worksheet: `1. KPI`
- Cloned worksheet: `1. KPI Profit`
- Replacement mapping: `Sales -> Profit`

Artifacts in this folder:

- `generate_example.py`
  Regenerates the output workbook from the source workbook in this same folder.
- `5 KPI Design Ideas (2) - KPI Profit Worksheet Example.twb`
  Output workbook containing both the original `1. KPI` worksheet and the
  migrated `1. KPI Profit` worksheet.

Expected result:

- `1. KPI` stays on the original Sales-based calculation chain.
- `1. KPI Profit` is a new worksheet whose local calculations and referenced
  top-level calculations are rewritten to use Profit.
- `1. KPI Profit` is unhidden so it appears in Tableau's visible worksheet tabs.
