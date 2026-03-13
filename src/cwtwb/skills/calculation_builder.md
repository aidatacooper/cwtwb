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
