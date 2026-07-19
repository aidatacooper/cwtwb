---
name: Calculation Builder
description: Expert guidance for creating Tableau calculated fields, parameters, and LOD expressions via cwtwb.
phase: 1
prerequisites: create_workbook must be called first
---

# Calculation Builder Skill

## Your Role

You are a **Tableau calculation expert**. Your job is to define parameters and calculated fields that form the analytical foundation of the workbook. Get this right, and everything downstream (charts, dashboard) will be clean and powerful.

## Workflow

```
1. Define parameters first (they're referenced by calculated fields)
2. Create basic calculated fields (ratios, differences, flags)
3. Create advanced fields (LOD expressions, table calculations)
4. Verify: call list_fields to confirm all fields are registered
```

## Parameter Best Practices

### Naming
- Use clear, business-friendly names: "Target Profit", "Growth Rate" — not "param1"
- Parameters will appear as interactive controls on dashboards

### Data Types & Formats
| Use Case | datatype | format | domain_type |
|----------|----------|--------|-------------|
| Currency target | `real` | `"$#,##0"` | `range` |
| Percentage rate | `real` | `"p0.00%"` | `range` |
| Category selector | `string` | — | `list` |
| Year selector | `integer` | — | `list` |
| Toggle switch | `string` | — | `list` (values: ["On","Off"]) |

### Range Parameters
- Always set `min_value`, `max_value`, and `granularity`
- Choose granularity that makes the slider usable (e.g., 1000 for currency, 0.01 for percentages)

### Example
```python
add_parameter(
    name="Target Profit",
    datatype="real",
    default_value="10000",
    domain_type="range",
    min_value="-30000",
    max_value="100000",
    granularity="10000",
    default_format="$#,##0"
)
```

## Calculated Field Best Practices

### Formula Syntax Rules
1. **Field references** use brackets: `[Sales]`, `[Profit]`
2. **Parameter references** use the prefix: `[Parameters].[Parameter Name]`
3. **String literals** use double quotes: `"Technology"`
4. **Aggregations** can be nested: `SUM([Profit]) / SUM([Sales])`

### Common Patterns

| Pattern | Formula | datatype |
|---------|---------|----------|
| Ratio | `SUM([Profit])/SUM([Sales])` | `real` |
| Per-entity metric | `SUM([Profit])/COUNTD([Customer Name])` | `real` |
| Boolean flag | `SUM([Profit]) > 0` | `boolean` |
| What-if estimate | `[Sales]*(1-[Parameters].[Churn Rate])*(1+[Parameters].[Growth])` | `real` |
| Rounded estimate | `ROUND([Quantity]*(1-[Parameters].[Rate]), 0)` | `integer` |

### LOD Expressions
- **FIXED**: `{FIXED [Order ID] : SUM([Profit])} > 0` — computes at specified granularity
- Use `datatype="string"` for LOD boolean flags (Tableau treats them as dimensions)
- LOD expressions are powerful for order-level or customer-level calculations

### LOD Selection Guide

| Analytical need | Expression | Example |
|---|---|---|
| Keep a result independent of the view grain | `FIXED` | `{ FIXED [Customer Name] : MIN([Order Date]) }` |
| Add a lower grain before aggregating back to the view | `INCLUDE` | `{ INCLUDE [Order ID] : SUM([Sales]) }` |
| Remove a dimension that is present in the view | `EXCLUDE` | `{ EXCLUDE [State/Province] : SUM([Sales]) }` |

Before writing an LOD, state the intended grain in plain language. Do not use
an LOD merely to work around an unclear aggregation problem. Remember that
`FIXED` expressions have Tableau order-of-operations implications: a regular
dimension filter may not affect them unless it is a context filter.

## Calculation Recipes

Use these as starting patterns and adjust field names, date grain, and null
handling to match the workbook. They are Tableau formulas, not a new cwtwb DSL.

| Need | Formula pattern | Notes |
|---|---|---|
| Safe ratio | `IF SUM([Sales]) = 0 THEN 0 ELSE SUM([Profit]) / SUM([Sales]) END` | Avoid division-by-zero errors. |
| Year-over-year growth | `IF SUM([Sales PY]) = 0 THEN NULL ELSE (SUM([Sales CY]) - SUM([Sales PY])) / SUM([Sales PY]) END` | Keep CY and PY filters aligned. |
| Last 12 complete months | `DATEDIFF('month', [Order Date], TODAY()) BETWEEN 1 AND 12` | Excludes the incomplete current month. |
| First order by customer | `{ FIXED [Customer Name] : MIN([Order Date]) }` | Use for new/returning customer flags. |
| Boolean status label | `IF SUM([Profit]) > 0 THEN "Profitable" ELSE "Loss" END` | Use a descriptive categorical output. |

### Performance and Compatibility

- Prefer one clearly named calculation over deeply nested `IF` chains; use
  `CASE` when matching one field against fixed values.
- Avoid nested LOD expressions unless the required grains are documented and
  tested against a known result.
- Treat `COUNTD` on large data sources as a performance risk. Consider a
  documented `FIXED` pre-aggregation only when it preserves the intended grain.
- Table calculations depend on the worksheet partition and addressing, so test
  them on the final chart rather than treating the formula as self-contained.
- Do not promise Tableau-version compatibility for a function unless the target
  version has been verified in the packaged function reference or Tableau docs.

## Calculation Design Contract

Before calling `add_calculated_field`, record enough context that the field can
be reviewed and maintained. This is adapted from the production-readiness
discipline in Adam Mico's Calc Engine, but uses cwtwb's existing API.

| Required item | Why it matters |
|---|---|
| Business purpose | Prevents technically valid calculations with unclear meaning. |
| Type | Identify row-level, aggregate, LOD, or table calculation. |
| Intended grain | Makes LOD and aggregation behavior reviewable. |
| Filter behavior | States whether context, dimension, or table-calc filters should affect it. |
| Dependencies | Names source fields, parameters, and prerequisite calculations. |
| Usage | States the worksheet shelf, encoding, label, or filter that consumes it. |
| Validation cases | Covers nulls, zero denominators, period boundaries, and empty partitions. |

For table calculations, record both addressing and partitioning in the
calculation note. `table_calc="Rows"` or `table_calc="Columns"` configures the
emitted XML, but it does not replace validating the result in the final view.

### Order-of-Operations Guardrails

- Use `FIXED` when a value must be computed at an explicit grain and should
  ignore ordinary dimension filters; make a filter context only when that is
  part of the business requirement.
- Use `INCLUDE` or `EXCLUDE` when the calculation should follow normal
  dimension filters at a grain relative to the view.
- Use a table calculation for a result that depends on visible mark order, such
  as a running total, prior-period lookup, rank, or windowed average.
- Do not replace a correct regular aggregate with an LOD merely because the LOD
  looks more sophisticated.

### Handoff Format

Write this compact contract with each non-trivial calculation:

```text
Name: <business-facing field name>
Purpose: <decision it supports>
Type and grain: <aggregate | LOD | table calc; grain>
Dependencies: <fields, parameters, prerequisite calcs>
Filter behavior: <what should and should not affect it>
Usage: <worksheet/encoding/filter>
Validation: <null, zero, boundary, and partition checks>
```

### Naming Conventions
- Use descriptive names: "Profit Ratio", "Profit per Customer"
- For boolean fields, use question format: "Order Profitable?"
- For estimates, suffix with "estimate": "Sales estimate"

## Table Calculations (Rank, Running Sum, etc.)

Table calculations like `RANK_DENSE`, `RUNNING_SUM`, and `WINDOW_SUM` require an extra `table_calc` parameter so the SDK emits the correct `<table-calc>` XML element inside the calculation:

```python
add_calculated_field(
    field_name="Rank CY",
    formula="RANK_DENSE(sum([Current Year Sales]),'desc')",
    datatype="integer",
    field_type="ordinal",   # important: ordinal → :ok suffix → Pie/Text mark can use it as label
    table_calc="Rows",      # must match the partitioning direction
)
```

**Rules:**
- `table_calc` must be `"Rows"` (partition by row) or `"Columns"` (partition by column).
- The SDK automatically propagates the `<table-calc ordering-type="Columns"/>` element into every `<column-instance>` that references this field.
- Set `field_type="ordinal"` when the result is a rank (integer used as a label, not summed).
- Use `field_type="quantitative"` (default) for running totals / window aggregates.

| Pattern | Formula | datatype | field_type | table_calc |
|---------|---------|----------|------------|------------|
| Dense rank (desc) | `RANK_DENSE(SUM([Sales]),'desc')` | `integer` | `ordinal` | `"Rows"` |
| Running total | `RUNNING_SUM(SUM([Sales]))` | `real` | `quantitative` | `"Rows"` |
| Window sum | `WINDOW_SUM(SUM([Profit]))` | `real` | `quantitative` | `"Rows"` |

## Common Pitfalls

| Pitfall | Problem | Fix |
|---------|---------|-----|
| Missing `[Parameters].` prefix | Parameter not recognized | Always use `[Parameters].[Name]` syntax |
| Wrong datatype for LOD boolean | Field treated as measure | Use `datatype="string"` for boolean LOD |
| Forgetting to create parameters first | Calculation references undefined parameter | Always create parameters before calculated fields that use them |
| Division by zero | Error in ratio calculations | Use `IF SUM([Sales]) = 0 THEN 0 ELSE SUM([Profit])/SUM([Sales]) END` |

## Output Checklist

Before moving to Phase 2 (Chart Builder):
- [ ] All parameters created with appropriate ranges and formats
- [ ] All calculated fields created with correct formulas
- [ ] `list_fields` confirms all new fields appear
- [ ] Field datatypes are correct (real/string/integer/boolean)
- [ ] Parameter references use `[Parameters].[Name]` syntax
- [ ] Every LOD has an explicitly stated target grain
- [ ] Ratios handle zero denominators and table calculations were checked on the final view
