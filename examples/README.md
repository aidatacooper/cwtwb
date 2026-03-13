# cwtwb SDK Examples

This directory contains Python scripts and prompt examples for the `cwtwb` SDK and MCP server.

The examples are intentionally split by support tier so the project does not accidentally present recipe-level charts as first-class product promises.

## Example tiers

### Core-fit examples

These stay inside the stable surface area and are the best reference points for users starting with the SDK.

| Example | What it shows | How to run |
|---|---|---|
| `scripts/demo_e2e_mcp_workflow.py` | End-to-end workbook creation from MCP-style tool calls using core chart and dashboard primitives | `python examples/scripts/demo_e2e_mcp_workflow.py` |
| `scripts/demo_connections.py` | Supported datasource switching workflows | `python examples/scripts/demo_connections.py` |
| `prompts/demo_simple.md` | Small core dashboard prompt using KPI and bar-chart primitives | Copy into an MCP-enabled assistant |

### Advanced-fit examples

These are supported, but they rely on advanced dashboard composition or interaction features.

| Example | What it shows | How to run |
|---|---|---|
| `scripts/demo_declarative_layout.py` | Declarative JSON dashboard layouts, KPI composition, and more complex layout structures | `python examples/scripts/demo_declarative_layout.py` |
| `scripts/demo_auto_layout4.py` | Advanced nested layout composition with fixed-size header and KPI band | `python examples/scripts/demo_auto_layout4.py` |
| `hyper_and_new_charts.py` | Advanced chart patterns such as Scatterplot, Heatmap, Tree Map, and Bubble Chart, using the Tableau Advent Calendar `Sample - EU Superstore.hyper` extract and resolving the physical `Orders_*` table via Tableau Hyper API | `python examples/hyper_and_new_charts.py` |
| `superstore_recreated/build_exec_overview.py` | Full dashboard recreation of the Tableau Superstore "Exec Overview" — demonstrates table calculations (RANK_DENSE), KPI difference badges (MIN(1) dummy axis + fixed range + color_map + customized_label), donut chart via `extra_axes`, non-traditional Pie for rank display, multi-field label, Top N filters, and row dimension header suppression (`hide_row_label`) | `python examples/superstore_recreated/build_exec_overview.py` |
| `prompts/demo_auto_layout_prompt.md` | Short natural-language request that stays near the core and advanced happy path | Copy into an MCP-enabled assistant |
| `prompts/demo_auto_layout4_prompt.md` | Prompt for advanced declarative layout composition | Copy into an MCP-enabled assistant |
| `prompts/demo_c2_layout_prompt.md` | Prompt for reading a saved JSON layout into a dashboard workflow | Copy into an MCP-enabled assistant |
| `prompts/demo_declarative_layout_prompt.md` | Prompt for a larger advanced dashboard assembly flow | Copy into an MCP-enabled assistant |
| `prompts/overview_business_demo.md` | Interactive dashboard prompt with filters, parameters, and business framing | Copy into an MCP-enabled assistant |
| `prompts/overview_natural_en.md` | Detailed English prompt for a more complex overview dashboard | Copy into an MCP-enabled assistant |
| `prompts/overview_natural zh_cn.md` | Chinese version of the advanced overview prompt | Copy into an MCP-enabled assistant |

### Recipe-heavy examples

These are useful for exploration and showcase purposes, but they should not be treated as the default supported surface area for the SDK.

| Example | What it shows | How to run |
|---|---|---|
| `all_supported_charts.py` | Mixed workbook including core, advanced, and recipe-level chart patterns such as Lollipop, Donut, Butterfly, and Calendar | `python examples/all_supported_charts.py` |
| `scripts/demo_all_supported_charts_mcp.py` | The same mixed workbook recreated strictly through the exported MCP tool functions, using the single `configure_chart_recipe` recipe entrypoint for Lollipop, Donut, Butterfly, and Calendar | `python examples/scripts/demo_all_supported_charts_mcp.py` |
| `prompts/all_supported_charts_showcase_en.md` | English MCP prompt for rebuilding the full worksheet showcase workbook with the unified `configure_chart_recipe` tool | Copy into an MCP-enabled assistant |
| `prompts/test_parameter_prefix_bug.md` | Narrow debugging prompt rather than a clean product-path example | Copy into an MCP-enabled assistant |

## Prompt examples for MCP clients

If you are using an LLM tool with an MCP client, you can copy the prompts in `examples/prompts/` into the chat.

Recommended starting points:

- `prompts/demo_simple.md`
- `prompts/demo_auto_layout_prompt.md`
- `prompts/demo_declarative_layout_prompt.md`

## Output

By default, examples write generated `.twb` files into the project-level `output/` directory.

The `hyper_and_new_charts.py` example needs the optional `tableauhyperapi`
dependency. Install it with `pip install "cwtwb[examples]"` if you want to run
that example from a package install.

If you are not sure whether a generated workbook still sits inside the intended product boundary, run `analyze_twb` or `diff_template_gap` on the output file before promoting the example into docs.
