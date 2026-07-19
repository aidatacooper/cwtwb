# TWB Migration Example

This example folder is a self-contained migration case:

- `5 KPI Design Ideas (2).twb`: the template workbook
- `Sample - Superstore.xls`: the original source data used by the template
- `示例 - 超市.xls`: the target Excel data for migration
- `test_migration_workflow.py`: a runnable example script that executes the guided migration workflow

Run it from the repo root:

```bash
python examples/migrate_workflow/test_migration_workflow.py
```

The script first runs `migrate_twb_guided()` to collect any
`warning_review_bundle`, then confirms those warning mappings by passing the
suggested targets back through `mapping_overrides`.

By default the script writes these files back into this same folder:

- `5 KPI Design Ideas (2) - migrated to target.twb`
- `migration_report.json`
- `field_mapping.json`

The copied `.twb` in this folder already points at the copied Excel files in this same folder, so you can also open it directly in Tableau Desktop without any repository-level template folder.
