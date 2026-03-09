# cwtwb

> **Tableau Workbook (.twb) generation toolkit for reproducible dashboards and workbook engineering**
> Programmatically create Tableau workbooks with stable analytical primitives, dashboard composition, and built-in structural validation.

## Overview

**cwtwb** is a Model Context Protocol (MCP) server and Python toolkit for generating Tableau Desktop workbook files (`.twb`) from code or AI-driven tool calls.

It is designed as a **workbook engineering layer**, not as a conversational data exploration agent. The goal is to make workbook generation reproducible, inspectable, and safe to automate in local workflows, scripts, and CI.

The default workflow is:

1. Start from a known template or the built-in zero-config template
2. Add calculated fields and parameters
3. Build worksheets from stable chart primitives
4. Assemble dashboards and interactions
5. Save and validate a `.twb` that opens in Tableau Desktop

## Installation

```bash
pip install cwtwb
```

### Requirements

- Python >= 3.10
- [lxml](https://lxml.de/) >= 5.0
- [mcp](https://pypi.org/project/mcp/) >= 1.0

## Quick Start

### As MCP Server

To allow an MCP client to build Tableau workbooks automatically, add `cwtwb` to the client's MCP configuration.

The simplest way to run it is via `uvx`.

#### Claude Desktop

Open `~/Library/Application Support/Claude/claude_desktop_config.json` on macOS or `%APPDATA%\Claude\claude_desktop_config.json` on Windows and add:

```json
{
  "mcpServers": {
    "cwtwb": {
      "command": "uvx",
      "args": ["cwtwb"]
    }
  }
}
```

#### Cursor IDE

1. Open **Cursor Settings** -> **Features** -> **MCP**
2. Click **Add New MCP Server**
3. Set **Type** to `command`
4. Set **Name** to `cwtwb`
5. Set **Command** to `uvx cwtwb`

#### Claude Code

```bash
claude mcp add cwtwb -- uvx cwtwb
```

#### VSCode

Add the same `uvx cwtwb` command to your MCP configuration.

### As Python Library

```python
from cwtwb.twb_editor import TWBEditor

editor = TWBEditor("templates/twb/superstore.twb")
editor.clear_worksheets()
editor.add_calculated_field("Profit Ratio", "SUM([Profit])/SUM([Sales])")

editor.add_worksheet("Sales by Category")
editor.configure_chart(
    worksheet_name="Sales by Category",
    mark_type="Bar",
    rows=["Category"],
    columns=["SUM(Sales)"],
)

editor.add_worksheet("Segment Pie")
editor.configure_chart(
    worksheet_name="Segment Pie",
    mark_type="Pie",
    color="Segment",
    wedge_size="SUM(Sales)",
)

editor.add_dashboard(
    dashboard_name="Overview",
    worksheet_names=["Sales by Category", "Segment Pie"],
    layout="horizontal",
)

editor.save("output/my_workbook.twb")
```

## MCP Tools

| Tool | Description |
|---|---|
| `create_workbook` | Load a TWB template and initialize the workspace |
| `list_fields` | List all available dimensions and measures |
| `add_parameter` | Add an interactive parameter for what-if analysis |
| `add_calculated_field` | Add a calculated field with Tableau formula |
| `remove_calculated_field` | Remove a previously added calculated field |
| `add_worksheet` | Add a new blank worksheet |
| `configure_chart` | Configure chart type and field mappings |
| `configure_dual_axis` | Configure a dual-axis chart composition |
| `add_dashboard` | Create a dashboard combining worksheets |
| `add_dashboard_action` | Add filter or highlight actions to a dashboard |
| `generate_layout_json` | Build an interactive structured dashboard flexbox layout |
| `list_capabilities` | Show cwtwb's declared support boundary |
| `describe_capability` | Explain whether a chart or feature is core, advanced, recipe, or unsupported |
| `analyze_twb` | Analyze a `.twb` file against the capability catalog |
| `diff_template_gap` | Summarize the non-core gap of a template |
| `set_mysql_connection` | Configure the datasource to use a local MySQL connection |
| `set_tableauserver_connection` | Configure connection to an online Tableau Server |
| `set_hyper_connection` | Configure the datasource to use a local Hyper extract connection |
| `save_workbook` | Save the final TWB file |

## Capability Model

### Core primitives

These are the stable building blocks the project should continue to promise:

- **Bar**
- **Line**
- **Area**
- **Pie**
- **Map**
- **Text** / KPI cards
- Parameters and calculated fields
- Basic dashboard composition

### Advanced patterns

These are supported, but they are higher-level compositions or interaction features rather than the default surface area:

- **Scatterplot**
- **Heatmap**
- **Tree Map**
- **Bubble Chart**
- **Dual Axis**
- Filter zones, parameter controls, color legends
- Dashboard filter and highlight actions
- Declarative JSON layout workflows

### Recipes and showcase patterns

These can be generated today, but they should be treated as recipes or examples rather than first-class promises:

- **Donut**
- **Lollipop**
- **Bullet**
- **Bump**
- **Butterfly**
- **Calendar**

This distinction matters because `cwtwb` is not trying to become a chart zoo or compete with Tableau's own conversational analysis tooling. The project is strongest when it provides a reliable, automatable workbook generation layer.

### Capability-first workflow

When you are not sure whether something belongs in the stable SDK surface:

1. Use `list_capabilities` to inspect the declared boundary
2. Use `describe_capability` to check a specific chart, encoding, or feature
3. Use `analyze_twb` or `diff_template_gap` before chasing a showcase template

This keeps new feature work aligned with the project's real product boundary instead of with whatever happens to appear in a sample workbook.

## Built-in Validation

`save()` automatically validates the TWB XML structure before writing:

- **Fatal errors** such as missing `<workbook>` or `<datasources>` raise `TWBValidationError`
- **Warnings** such as missing `<view>` or `<panes>` are logged but do not block saving
- Validation can be disabled with `editor.save("output.twb", validate=False)`

## Dashboard Layouts

| Layout | Description |
|---|---|
| `vertical` | Stack worksheets top to bottom |
| `horizontal` | Place worksheets side by side |
| `grid-2x2` | 2x2 grid layout for up to four worksheets |
| `dict` or `.json` path | Declarative custom layouts for more complex dashboards |

Custom layouts can be built programmatically using a nested `layout` dictionary or via `generate_layout_json` for MCP workflows.

## Project Structure

```text
cwtwb/
|-- src/cwtwb/
|   |-- __init__.py
|   |-- capability_registry.py
|   |-- twb_analyzer.py
|   |-- config.py
|   |-- field_registry.py
|   |-- twb_editor.py
|   |-- charts/
|   |-- dashboards.py
|   |-- connections.py
|   |-- parameters.py
|   |-- validator.py
|   |-- layout.py
|   `-- server.py
|-- tests/
|-- examples/
|-- docs/
|-- pyproject.toml
`-- README.md
```

## Development

```bash
# Install in editable mode
pip install -e .

# Run test suite
pytest --basetemp=output/pytest_tmp

# Run the mixed showcase example
python examples/all_supported_charts.py

# Start MCP server
cwtwb
```

## License

AGPL-3.0-or-later
