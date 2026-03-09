# cwtwb Prompt Examples

This directory contains prompt examples for interacting with the `cwtwb` MCP server. You can copy and paste these prompts into an MCP-enabled assistant to automate Tableau workbook generation.

The prompts span multiple support tiers. Prefer starting with the core-fit and advanced-fit prompts listed in `examples/README.md` before using the recipe-heavy or debugging prompts.

The surrounding docs now use the same capability-aware language as the SDK:
core primitives, advanced patterns, and recipe-style showcase charts. When a
prompt output starts drifting beyond the intended support boundary, validate it
with `list_capabilities`, `describe_capability`, `analyze_twb`, or
`diff_template_gap`.

## Examples list

### Basic and declarative layout examples

- **`demo_simple.md`**: Small core-path example using KPI and bar-chart primitives with `generate_layout_json`
- **`demo_auto_layout_prompt.md`**: Short natural-language request for an adaptive dashboard layout
- **`demo_auto_layout4_prompt.md`**: Advanced declarative layout example with fixed sizing
- **`demo_c2_layout_prompt.md`**: Reads an existing external JSON layout and applies it to a dashboard
- **`demo_declarative_layout_prompt.md`**: Larger dashboard assembly flow using external layout files

### Interactive overview examples

- **`overview_business_demo.md`**: Business-oriented prompt for an interactive overview dashboard
- **`overview_natural_en.md`**: Detailed English prompt for a more technical overview reconstruction
- **`overview_natural zh_cn.md`**: Chinese version of the detailed overview prompt

### Debugging and narrow checks

- **`test_parameter_prefix_bug.md`**: Checks parameter reference parsing with and without the `[Parameters].` prefix

> Tip:
> If you encounter payload or context limits, follow the pattern used in `demo_simple.md`: call `generate_layout_json` first, save the JSON locally, and then pass the file path to `add_dashboard`.
