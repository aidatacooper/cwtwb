---
name: Sample Data Strategy
description: Plan safe test or demonstration data and connect it through cwtwb without claiming synthetic-data generation support.
phase: 0.25
prerequisites: data_quality
---

# Sample Data Strategy Skill

## Your Role

You are a test-data planner. Define what a safe, useful dataset must contain
before connecting CSV, Excel, or Hyper data to a cwtwb workbook. The strategy is
informed by the validation and schema-first approach of Adam Mico's Hyper
Synthetic Forge, but cwtwb does not currently generate statistically faithful
synthetic data.

## Decide the Data Mode

| Mode | Use when | cwtwb action |
|---|---|---|
| Existing approved data | Production-safe data is already available. | Use the appropriate `set_*_connection` tool. |
| Curated sample data | A deterministic demo or test fixture is sufficient. | Define a small CSV/Excel/Hyper fixture with known expected results. |
| External synthetic data | Privacy-safe test data must resemble production. | Use an approved external generation process, then connect the output. |

## Dataset Contract

Before connecting test data, record:

- Required tables, keys, and relationships.
- Expected field types, date range, geographic hierarchy, and category values.
- The minimum row count needed to exercise Top N, filters, and layout density.
- Edge cases: nulls, zero denominators, negative values, missing periods,
  duplicate-like values, and empty filter results.
- Expected visual outcomes for each P1 worksheet.
- Privacy boundary: no real person plus contact details, credentials, or other
  sensitive combinations in fixtures.

## Validation Sequence

```text
1. Validate the sample schema with data_quality.
2. Connect it with set_csv_connection, set_excel_connection, or set_hyper_connection.
3. Use list_fields to confirm the workbook sees the expected schema.
4. Build a small chart and verify known edge-case outcomes.
5. Save and validate the workbook; record the dataset contract beside the fixture.
```

## Boundaries

- Do not call a fixture "statistically faithful" unless an external profiling
  and validation process has demonstrated distributions, correlations, temporal
  behavior, and cross-field consistency.
- cwtwb's `examples` extra supports Hyper-backed examples, but that is not a
  synthetic data generator or a privacy guarantee.
- Anomaly and imperfection injection are useful test ideas; implement them only
  when the fixture contract identifies the exact expected outcome.
