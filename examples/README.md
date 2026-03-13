# cwtwb SDK Examples

All scripts in `examples/scripts/` and prompts in `examples/prompts/` work
out of the box after a standard `pip install`. No cloned repository or external
data files are needed — the built-in Superstore dataset is bundled with the package.

```bash
pip install cwtwb

# Run your first example
python examples/scripts/demo_connections.py
```

> **Note for `hyper_and_new_charts.py`**: also requires the optional Hyper
> dependency — install with `pip install "cwtwb[examples]"`.

---

## Scripts — Step by Step

Run these directly to explore the SDK from simple to complex.

| Step | Script | Level | What it demonstrates |
|------|--------|-------|----------------------|
| 1 | `scripts/demo_connections.py` | ⭐ Beginner | Switch a workbook's datasource to MySQL or Tableau Server. No charts required. |
| 2 | `scripts/demo_e2e_mcp_workflow.py` | ⭐ Beginner | Full MCP sequence: create workbook → calculated field → Bar + Pie charts → dashboard → save. The canonical "hello world". |
| 3 | `scripts/demo_auto_layout4.py` | ⭐⭐ Intermediate | KPI text cards + bar charts + 3-row declarative layout (header / KPI band / charts) with `fixed_size`. |
| 4 | `scripts/demo_declarative_layout.py` | ⭐⭐ Intermediate | 8 worksheets (KPI text + bar charts) assembled into 3 dashboards from external JSON layout files. |
| 5 | `scripts/demo_all_supported_charts_mcp.py` | ⭐⭐⭐ Advanced | All 15 chart types via MCP tools: 11 core charts + 4 recipe charts (Lollipop, Donut, Butterfly, Calendar). |

---

## Prompts — Step by Step

Copy these into any LLM client with the `cwtwb` MCP server configured.

| Step | Prompt file | Level | What it demonstrates |
|------|-------------|-------|----------------------|
| 1 | `prompts/demo_simple.md` | ⭐ Beginner | 2 KPI cards + 2 bar charts, with `generate_layout_json` + vertical dashboard layout. |
| 2 | `prompts/demo_auto_layout_prompt.md` | ⭐ Beginner | 3 bar charts described in plain language → horizontal split dashboard inferred by the LLM. |
| 3 | `prompts/test_parameter_prefix_bug.md` | ⭐ Beginner | Parameter creation + calculated fields with and without `[Parameters].` prefix. Good for verifying parameter syntax. |
| 4 | `prompts/demo_auto_layout4_prompt.md` | ⭐⭐ Intermediate | KPI cards + bar charts + 3-row layout with fixed header and KPI band. |
| 5 | `prompts/demo_c2_layout_prompt.md` | ⭐⭐ Intermediate | 8 worksheets (4 bar + 4 KPI text) assembled with a C.2 JSON layout file. Requires `examples/layouts/layout_c2.json`. |
| 6 | `prompts/demo_declarative_layout_prompt.md` | ⭐⭐ Intermediate | 8 worksheets assembled into 2 dashboards from two JSON layout files. Requires `examples/layouts/`. |
| 7 | `prompts/all_supported_charts_showcase_en.md` | ⭐⭐⭐ Advanced | Full chart catalog: 15 chart types including all core primitives and recipe-level charts. |
| 8 | `prompts/overview_business_demo.md` | ⭐⭐⭐ Advanced | Parameters + LOD fields + Map + Area charts + filter sidebar + dashboard actions. Business executive demo (English). |
| 9 | `prompts/overview_natural_en.md` | ⭐⭐⭐ Advanced | Structured replication of the full Overview dashboard. Parameters, 6 calculated fields, 4 charts, filter sidebar, 3 actions. |
| 10 | `prompts/overview_natural zh_cn.md` | ⭐⭐⭐ Advanced | Same as step 9 in Chinese — pure natural language description. |

---

## Other Examples (Separate Subfolders)

These live in their own subfolders and may have additional dependencies.

| Example | What it shows | Notes |
|---------|---------------|-------|
| `hyper_and_new_charts.py` | Scatterplot, Heatmap, Tree Map, Bubble Chart against the bundled EU Superstore Hyper extract | Needs `pip install "cwtwb[examples]"` for `tableauhyperapi` |
| `all_supported_charts.py` | Same 15-chart showcase as step 5, using the direct `TWBEditor` API instead of MCP tools | Works after plain `pip install cwtwb` |
| `superstore_recreated/build_exec_overview.py` | Full recreation of the Tableau Superstore "Exec Overview" — table calculations, KPI badges, donut via `extra_axes`, Top N filters | Works after plain `pip install cwtwb` |
| `migrate_workflow/` | Migrate an existing `.twb` workbook to a new datasource with field mapping | Requires the `.twb` and `.xls` files bundled in that folder |

---

## Output

All examples write generated `.twb` files to the project-level `output/` directory,
which is created automatically if it does not exist.
