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

### Advanced-fit examples

These are supported, but they rely on advanced dashboard composition or interaction features.

| Example | What it shows | How to run |
|---|---|---|
| `scripts/demo_declarative_layout.py` | Declarative JSON dashboard layouts, KPI composition, and more complex layout structures | `python examples/scripts/demo_declarative_layout.py` |

### Recipe-heavy examples

These are useful for exploration and showcase purposes, but they should not be treated as the default supported surface area for the SDK.

| Example | What it shows | How to run |
|---|---|---|
| `all_supported_charts.py` | Mixed workbook including core, advanced, and recipe-level chart patterns such as Lollipop, Donut, Butterfly, and Calendar | `python examples/all_supported_charts.py` |
| `hyper_and_new_charts.py` | Additional chart experiments and connection workflows | `python examples/hyper_and_new_charts.py` |

## Prompt examples for MCP clients

If you are using an LLM tool with an MCP client, you can copy the prompts in `examples/prompts/` into the chat.

Recommended starting points:

- `prompts/demo_auto_layout_prompt.md`
- `prompts/demo_c2_layout_prompt.md`
- `prompts/demo_declarative_layout_prompt.md`

## Output

By default, examples write generated `.twb` files into the project-level `output/` directory.
