# cwtwb SDK — Examples

Run the hello-world example in under a minute:

```bash
pip install cwtwb
python examples/scripts/demo_e2e_mcp_workflow.py
```

All scripts use the **built-in Superstore dataset** — no external files needed.

For the newer datasource-first MCP workflow, see
`examples/agentic_mcp_authoring/README.md`. That flow starts from a real
Excel or Hyper file, writes paired JSON + Markdown review artifacts under
`tmp/agentic_run/{run_id}/`, prefers MCP elicitation for approval gates when
the client supports it, and falls back cleanly to chat confirmation when it
does not.

---

## Scripts — Simple to Complex

Seven runnable Python scripts, ordered from beginner to advanced.

| Step | Script | Level | What it demonstrates |
|------|--------|-------|----------------------|
| 1 | `scripts/demo_connections.py` | ⭐ Beginner | Switch a workbook's datasource to MySQL or Tableau Server. No charts required. |
| 2 | `scripts/demo_e2e_mcp_workflow.py` | ⭐ Beginner | Full end-to-end sequence: create workbook → calculated field → Bar + Pie charts → dashboard → save. The canonical hello world. |
| 3 | `scripts/demo_auto_layout4.py` | ⭐⭐ Intermediate | KPI text cards + bar charts assembled into a 3-row layout (header / KPI band / charts) with `fixed_size`. |
| 4 | `scripts/demo_declarative_layout.py` | ⭐⭐⭐ Advanced | 8 worksheets assembled into 3 dashboards driven by external JSON layout files in `layouts/`. |
| 5 | `scripts/demo_all_supported_charts_mcp.py` | ⭐⭐⭐ Advanced | All 15 chart types via **MCP tool functions** — the same path an LLM follows at runtime. |
| 6 | `scripts/demo_all_supported_charts.py` | ⭐⭐⭐ Advanced | Same 15-chart showcase using the **direct `TWBEditor` Python API**. Good for SDK regression testing. |
| 7 | `scripts/demo_hyper_and_new_charts.py` | ⭐⭐⭐ Advanced | Scatterplot · Heatmap · Tree Map · Bubble Chart in a 2×2 grid, optionally against a Hyper extract. Needs `pip install "cwtwb[examples]"`. |

Run any script from the project root:

```bash
python examples/scripts/demo_e2e_mcp_workflow.py
python examples/scripts/demo_all_supported_charts.py
```

---

## Prompts — for MCP / LLM Clients

For the guided run workflow, prefer the MCP prompts exposed by the server:
`guided_dashboard_authoring`, `dashboard_brief_to_contract`,
`light_elicitation`, and `authoring_execution_plan`. The files in this section
remain useful as direct prompt examples for one-shot workbook generation.

Copy these into any LLM client (Claude, etc.) with the `cwtwb` MCP server configured.

| Step | Prompt file | Level | What it demonstrates |
|------|-------------|-------|----------------------|
| 1 | `prompts/demo_simple.md` | ⭐ Beginner | 2 KPI cards + 2 bar charts with `generate_layout_json` + vertical dashboard. |
| 2 | `prompts/demo_auto_layout_prompt.md` | ⭐ Beginner | 3 bar charts in plain language → horizontal-split dashboard inferred by the LLM. |
| 3 | `prompts/test_parameter_prefix_bug.md` | ⭐ Beginner | Parameter creation + calculated fields with/without `[Parameters].` prefix. Good for verifying parameter syntax. |
| 4 | `prompts/demo_auto_layout4_prompt.md` | ⭐⭐ Intermediate | KPI cards + bar charts + 3-row layout with fixed header and KPI band. |
| 5 | `prompts/demo_c2_layout_prompt.md` | ⭐⭐ Intermediate | 8 worksheets assembled with a C.2 JSON layout. Requires `layouts/layout_c2.json`. |
| 6 | `prompts/demo_declarative_layout_prompt.md` | ⭐⭐ Intermediate | 8 worksheets into 2 dashboards from two JSON layout files. Requires `layouts/`. |
| 7 | `prompts/all_supported_charts_showcase_en.md` | ⭐⭐⭐ Advanced | Full chart catalog — all 15 chart types including core primitives and recipe charts. |
| 8 | `prompts/overview_business_demo.md` | ⭐⭐⭐ Advanced | Parameters + LOD fields + Map + Area charts + filter sidebar + dashboard actions. Business executive demo (English). |
| 9 | `prompts/overview_natural_en.md` | ⭐⭐⭐ Advanced | Full Overview dashboard: parameters, 6 calculated fields, 4 charts, filter sidebar, 3 actions. (English) |
| 10 | `prompts/overview_natural zh_cn.md` | ⭐⭐⭐ Advanced | Same as step 9 in Chinese — pure natural-language description. |

---

## Showcase Projects

End-to-end examples with their own subfolders and all required assets.

| Project | What it shows | How to run |
|---------|---------------|------------|
| `agentic_mcp_authoring/` | Datasource-first guided MCP authoring run: schema intake, analysis brief, contract review, ASCII wireframe, human confirmation gates, execution planning, and final `.twb` generation | Start the MCP server with `python -m cwtwb.mcp` or `uvx cwtwb`, then follow `agentic_mcp_authoring/README.md` in your MCP client, or run `python examples/agentic_mcp_authoring/demo_guided_authoring_mcp_client.py` for a deterministic protocol-level demo |
| `superstore_recreated/` | Full recreation of Tableau's "Exec Overview" dashboard — table calculations, KPI badges, donut via `extra_axes`, Top N filters, rich-text labels | `python examples/superstore_recreated/build_exec_overview.py` |
| `migrate_workflow/` | Migrate an existing `.twb` workbook to a new datasource with automatic field mapping and a migration report | `python examples/migrate_workflow/test_migration_workflow.py` |
| `worksheet_refactor_kpi_profit/` | Clone the `1. KPI` worksheet, refactor its calculation chain from Sales to Profit, and write an output workbook with a visible `1. KPI Profit` worksheet | `python examples/worksheet_refactor_kpi_profit/generate_example.py` |
| `screenshot2layout/` | Dashboard screenshots paired with their JSON layout descriptors — useful as reference input for layout-generation workflows | Open the PNGs and JSON files directly |

---

## Output

All scripts write generated `.twb` files to `output/` in the project root,
which is created automatically on first run.
