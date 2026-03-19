# cwtwb

> **Tableau Workbook (.twb/.twbx) generation toolkit for reproducible dashboards and workbook engineering**
> Programmatically create Tableau workbooks with stable analytical primitives, dashboard composition, and built-in structural validation.

## Overview

**cwtwb** is a Model Context Protocol (MCP) server and Python toolkit for generating Tableau Desktop workbook files (`.twb` / `.twbx`) from code or AI-driven tool calls.

It is designed as a **workbook engineering layer**, not as a conversational data exploration agent. The goal is to make workbook generation reproducible, inspectable, and safe to automate in local workflows, scripts, and CI.

The default workflow is:

1. Start from a known template (`.twb` or `.twbx`) or the built-in zero-config template
2. Add calculated fields and parameters
3. Build worksheets from stable chart primitives
4. Assemble dashboards and interactions
5. Save and validate a `.twb` or `.twbx` that opens in Tableau Desktop

```
                            Interfaces
  ┌───────────────────────────────────────────────────────────────┐
  │  ┌──────────────────────────┐  ┌───────────────────────────┐  │
  │  │        MCP Server        │  │      Python Library       │  │
  │  │  tools_workbook          │  │  from cwtwb.twb_editor    │  │
  │  │  tools_layout            │  │  import TWBEditor         │  │
  │  │  tools_migration         │  │                           │  │
  │  │  tools_support           │  │  editor.add_...()         │  │
  │  │                          │  │  editor.configure_...()   │  │
  │  │  (Claude / Cursor /      │  │  editor.save(...)         │  │
  │  │   VSCode / Claude Code)  │  │                           │  │
  │  └─────────────┬────────────┘  └──────────────┬────────────┘  │
  │                └──────────────┬────────────────┘               │
  └─────────────────────────────  ┼  ─────────────────────────────┘
                                  ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                          TWBEditor                            │
  │       ParametersMixin  ·  ConnectionsMixin                    │
  │       ChartsMixin      ·  DashboardsMixin                     │
  └──────────┬──────────────────┬──────────────────┬─────────────┘
             ▼                  ▼                  ▼
  ┌──────────────────┐  ┌──────────────┐  ┌──────────────────────┐
  │  Chart Builders  │  │  Dashboard   │  │  Analysis &          │
  │                  │  │  System      │  │  Migration           │
  │  Basic  DualAxis │  │              │  │                      │
  │  Pie    Text     │  │  layouts     │  │  migration.py        │
  │  Map    Recipes  │  │  actions     │  │  twb_analyzer.py     │
  │                  │  │  dependencies│  │  capability_registry │
  └────────┬─────────┘  └──────┬───────┘  └──────────┬───────────┘
           └───────────────────┼──────────────────────┘
                               ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                     XML Engine  (lxml)                        │
  │    template.twb/.twbx  →  patch  →  validate  →  save        │
  └───────────────────────────────┬───────────────────────────────┘
                                  ▼
                      output.twb  /  output.twbx
```

## Installation

```bash
pip install cwtwb
```

To run the bundled Hyper-backed example that inspects `.hyper` files and
resolves the physical `Orders_*` table automatically, install the optional
example dependency as well:

```bash
pip install "cwtwb[examples]"
```

### Requirements

- Python >= 3.10
- [lxml](https://lxml.de/) >= 5.0
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [mcp](https://pypi.org/project/mcp/) >= 1.0

## Quick Start

### As MCP Server

To allow an MCP client to build Tableau workbooks automatically, add `cwtwb`
to that client's MCP configuration.

The launch command is the same across clients:

```bash
uvx cwtwb
```

Each client stores this command in a different configuration format. Use the
matching example below.

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

Open the workspace `.vscode/mcp.json` file or your user-profile `mcp.json`
file and add:

```json
{
  "servers": {
    "cwtwb": {
      "command": "uvx",
      "args": ["cwtwb"]
    }
  }
}
```

In VSCode, you can open these files from the Command Palette with
**MCP: Open Workspace Folder Configuration** or
**MCP: Open User Configuration**. You can also use **MCP: Add Server** and
enter the same `uvx cwtwb` command through the guided flow.

### As Python Library

Use `TWBEditor(...)` to start from a template and rebuild workbook content.
Use `TWBEditor.open_existing(...)` when you want to keep existing worksheets
and dashboards and reconfigure a sheet in place.

```python
from cwtwb.twb_editor import TWBEditor

editor = TWBEditor("")  # "" uses the built-in Superstore template
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

### Working with Packaged Workbooks (.twbx)

`.twbx` files are ZIP archives that bundle the workbook XML together with data extracts (`.hyper`) and image assets. cwtwb reads and writes them transparently:

```python
from cwtwb.twb_editor import TWBEditor

# Open a packaged workbook — extracts and images are preserved automatically
editor = TWBEditor.open_existing("templates/dashboard/MyDashboard.twbx")

# Make changes as usual
editor.add_calculated_field("Profit Ratio", "SUM([Profit])/SUM([Sales])")

# Save as .twbx — re-bundles the updated .twb with the original extracts/images
editor.save("output/MyDashboard_v2.twbx")

# Or extract just the XML when the packaged format isn't needed
editor.save("output/MyDashboard_v2.twb")
```

A plain `.twb` can also be packaged:

```python
editor = TWBEditor("templates/twb/superstore.twb")
# ...
editor.save("output/superstore.twbx")  # produces a single-entry ZIP with the .twb inside
```

## MCP Tools

| Tool | Description |
|---|---|
| `create_workbook` | Load a `.twb` or `.twbx` template and initialize a rebuild-from-template workspace |
| `open_workbook` | Open an existing `.twb` or `.twbx` and keep its worksheets and dashboards for editing |
| `list_fields` | List all available dimensions and measures |
| `list_worksheets` | List worksheet names in the active workbook |
| `list_dashboards` | List dashboards and the worksheet zones they reference |
| `add_parameter` | Add an interactive parameter for what-if analysis |
| `add_calculated_field` | Add a calculated field with Tableau formula |
| `remove_calculated_field` | Remove a previously added calculated field |
| `add_worksheet` | Add a new blank worksheet |
| `configure_chart` | Configure chart type and field mappings |
| `configure_worksheet_style` | Apply worksheet-level styling: background color, axis/grid/border visibility |
| `configure_dual_axis` | Configure a dual-axis chart composition |
| `configure_chart_recipe` | Configure a showcase recipe chart such as `lollipop`, `donut`, `butterfly`, or `calendar` |
| `add_dashboard` | Create a dashboard combining worksheets |
| `add_dashboard_action` | Add filter or highlight actions to a dashboard |
| `generate_layout_json` | Build an interactive structured dashboard flexbox layout |
| `list_capabilities` | Show cwtwb's declared support boundary |
| `describe_capability` | Explain whether a chart or feature is core, advanced, recipe, or unsupported |
| `analyze_twb` | Analyze a `.twb` file against the capability catalog |
| `diff_template_gap` | Summarize the non-core gap of a template |
| `validate_workbook` | Validate a workbook against the official Tableau TWB XSD schema (2026.1) |
| `migrate_twb_guided` | Run the built-in TWB migration workflow and pause for warning confirmation when needed |
| `set_mysql_connection` | Configure the datasource to use a local MySQL connection |
| `set_tableauserver_connection` | Configure connection to an online Tableau Server |
| `set_hyper_connection` | Configure the datasource to use a local Hyper extract connection |
| `save_workbook` | Save the workbook as `.twb` (plain XML) or `.twbx` (ZIP with bundled extracts and images) |

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
- **Dual Axis** — `mark_color_1/2`, `color_map_1`, `reverse_axis_1`, `hide_zeroline`, `synchronized`
- **Table Calculations** — `RANK_DENSE`, `RUNNING_SUM`, `WINDOW_SUM` via `add_calculated_field(table_calc="Rows")`
- **KPI Difference badges** — `MIN(1)` dummy axis + `axis_fixed_range` + `color_map` + `customized_label`
- **Donut (via extra_axes)** — multi-pane Pie + white circle using `configure_dual_axis(extra_axes=[...])`; supports `color_map` for `:Measure Names` palette
- **Rich-text labels** — `configure_chart(label_runs=[...])` for multi-style KPI cards and dynamic titles with inline field values
- **Advanced worksheet styling** — `configure_worksheet_style` supports pane-level cell/datalabel/mark styles, per-field label/cell/header formats, axis tick control, tooltip disabling, and all Tableau visual noise suppressions
- **Row dimension header suppression** — `configure_worksheet_style(hide_row_label="FieldName")`
- Filter zones, parameter controls, color legends
- Dashboard filter and highlight actions
- Declarative JSON layout workflows
- Dashboard zone title control via `show_title: false` in layout dicts

### Recipes and showcase patterns

These can be generated today, but they should be treated as recipes or examples rather than first-class promises:

- **Donut**
- **Lollipop**
- **Bullet**
- **Bump**
- **Butterfly**
- **Calendar**

Recipe charts are intentionally exposed through a single `configure_chart_recipe`
tool so the public MCP surface does not grow one tool at a time for every
showcase pattern.

This distinction matters because `cwtwb` is not trying to become a chart zoo or compete with Tableau's own conversational analysis tooling. The project is strongest when it provides a reliable, automatable workbook generation layer.

### Capability-first workflow

When you are not sure whether something belongs in the stable SDK surface:

1. Use `list_capabilities` to inspect the declared boundary
2. Use `describe_capability` to check a specific chart, encoding, or feature
3. Use `analyze_twb` or `diff_template_gap` before chasing a showcase template

This keeps new feature work aligned with the project's real product boundary instead of with whatever happens to appear in a sample workbook.

## Built-in Validation

### Structural validation

`save()` automatically validates the TWB XML structure before writing:

- **Fatal errors** such as missing `<workbook>` or `<datasources>` raise `TWBValidationError`
- **Warnings** such as missing `<view>` or `<panes>` are logged but do not block saving
- Validation can be disabled with `editor.save("output.twb", validate=False)` or `editor.save("output.twbx", validate=False)`

### XSD schema validation

`TWBEditor.validate_schema()` checks the workbook against the official Tableau TWB XSD schema (2026.1), vendored at `vendor/tableau-document-schemas/`:

```python
result = editor.validate_schema()
print(result.to_text())
# PASS  Workbook is valid against Tableau TWB XSD schema (2026.1)
# — or —
# FAIL  Schema validation failed (2 error(s)):
#   * Element 'workbook': Missing child element(s)...

result.valid          # bool
result.errors         # list[str] — lxml error messages
result.schema_available  # False if the vendor submodule is not checked out
```

The same check is available as an MCP tool:

```
validate_workbook()                       # validate current open workbook in memory
validate_workbook(file_path="out.twb")    # validate a file on disk (.twb or .twbx)
```

XSD errors are **informational** — Tableau itself generates workbooks that occasionally deviate from the schema — but recurring errors signal structural problems worth fixing.

## Dashboard Layouts

| Layout | Description |
|---|---|
| `vertical` | Stack worksheets top to bottom |
| `horizontal` | Place worksheets side by side |
| `grid-2x2` | 2x2 grid layout for up to four worksheets |
| `dict` or `.json` path | Declarative custom layouts for more complex dashboards |

Custom layouts can be built programmatically using a nested `layout` dictionary or via `generate_layout_json` for MCP workflows.

## Hyper-backed Example

The `examples/hyper_and_new_charts.py` example uses the `Sample - EU Superstore.hyper`
extract bundled directly in the package (`src/cwtwb/references/`) and resolves the
physical `Orders_*` table via Tableau Hyper API before switching the workbook connection.
No repository clone is needed — install with `pip install "cwtwb[examples]"` and run directly.

## Guided Migration Example

The self-contained migration case under `examples/migrate_workflow/` includes a
template `.twb`, the original Superstore Excel, the target Chinese Superstore
Excel, and a runnable script that writes the migrated workbook plus JSON reports
back into that same example folder.

The guided migration workflow now pauses when only low-confidence warnings
remain and returns a compact `warning_review_bundle`. You can confirm those
suggested mappings by passing them back through `mapping_overrides`, which keeps
the core migration flow deterministic and avoids any server-side model keys.

## Project Structure

```text
cwtwb/
|-- src/cwtwb/
|   |-- __init__.py
|   |-- capability_registry.py
|   |-- config.py
|   |-- charts/
|   |-- connections.py
|   |-- dashboard_actions.py
|   |-- dashboard_dependencies.py
|   |-- dashboard_layouts.py
|   |-- dashboards.py
|   |-- field_registry.py
|   |-- layout.py
|   |-- layout_model.py
|   |-- layout_rendering.py
|   |-- mcp/
|   |-- parameters.py
|   |-- twb_analyzer.py
|   |-- twb_editor.py
|   |-- validator.py
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
python examples/scripts/demo_all_supported_charts.py

# Run the advanced Hyper-backed example
python examples/scripts/demo_hyper_and_new_charts.py

# Run the guided migration example
python examples/migrate_workflow/test_migration_workflow.py

# Start MCP server
cwtwb
```

## License

AGPL-3.0-or-later
