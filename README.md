# cwtwb

> **Tableau Workbook (.twb/.twbx) generation toolkit for reproducible dashboards and workbook engineering**
> Programmatically create Tableau workbooks with stable analytical primitives, dashboard composition, and built-in structural validation.

**Author:** Cooper Wenhua &lt;imgwho@gmail.com&gt;

## Overview

**cwtwb** is a Model Context Protocol (MCP) server and Python toolkit for generating Tableau Desktop workbook files (`.twb` / `.twbx`) from code or AI-driven tool calls.

It is designed as a **workbook engineering layer**, not as a conversational data exploration agent. The goal is to make workbook generation reproducible, inspectable, and safe to automate in local workflows, scripts, and CI.

The default workflow is:

1. Start from a known template (`.twb` or `.twbx`) or the built-in zero-config template
2. Add calculated fields and parameters
3. Build worksheets from stable chart primitives
4. Assemble dashboards and interactions
5. Save and validate a `.twb` or `.twbx` that opens in Tableau Desktop

For natural-language MCP authoring, cwtwb also supports a guided run workflow
that starts from a real datasource file instead of a hand-written contract:

1. Start an authoring run from a local Excel or Hyper file
2. Inspect the datasource schema and pause for human confirmation
3. Build an analysis brief, present 2-4 candidate dashboard directions, and confirm the chosen direction
4. Draft, review, and finalize a structured authoring contract
5. Build and confirm a human-facing wireframe
6. Build a mechanical execution plan internally and generate the final workbook
7. Persist every intermediate artifact under `tmp/agentic_run/{run_id}/`

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

For local testing without `uvx`, you can also start the server with:

```bash
python -m cwtwb.mcp
```

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

### Clone and Refactor an Existing Worksheet

Use worksheet clone/refactor when you want to duplicate an existing visual
module and rebind only the cloned worksheet to a different core measure. This
is especially useful for KPI cards such as turning a Sales KPI worksheet into
an independent Profit KPI worksheet while preserving the original sheet.

```python
from cwtwb.twb_editor import TWBEditor

editor = TWBEditor.open_existing("examples/worksheet_refactor_kpi_profit/5 KPI Design Ideas (2).twb")

editor.clone_worksheet("1. KPI", "1. KPI Profit")
editor.apply_worksheet_refactor("1. KPI Profit", {"Sales": "Profit"})
editor.set_worksheet_hidden("1. KPI Profit", hidden=False)

editor.save("output/kpi_profit_clone.twb")
```

Available worksheet-refactor helpers:

- `clone_worksheet(source_worksheet, target_worksheet)`
- `preview_worksheet_refactor(worksheet_name, replacements)`
- `apply_worksheet_refactor(worksheet_name, replacements)`
- `set_worksheet_hidden(worksheet_name, hidden=True)`

`apply_worksheet_refactor(...)` now also performs a worksheet-local identity
normalization pass for generic Tableau `Calculation_*` fields. This stabilizes
pill labels after clone-and-replace workflows and returns `post_process`
evidence describing renamed calculation identities and worksheet-local rewrite
maps.

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
| `start_authoring_run` | Create a guided datasource-first authoring run and persist its manifest under `tmp/agentic_run/{run_id}/` |
| `list_authoring_runs` | List previously created authoring runs, their current status, and available artifacts |
| `get_run_status` | Inspect one authoring run, including confirmation gates, current artifact versions, and failure details |
| `resume_authoring_run` | Re-open a previous authoring run after a client or server restart |
| `intake_datasource_schema` | Read the run datasource from the manifest and persist a structured schema summary for Excel or Hyper |
| `build_analysis_brief` | Create the analysis brief scaffold from the current schema summary |
| `finalize_analysis_brief` | Finalize 2-4 candidate directions plus the selected direction for the run |
| `draft_authoring_contract` | Create a contract draft from the schema summary plus a human brief |
| `review_authoring_contract_for_run` | Review the current draft, apply profile-aware defaults, and produce clarification guidance |
| `finalize_authoring_contract` | Merge review output with human answers and persist the finalized contract |
| `interactive_stage_confirmation` | Prefer MCP elicitation for schema, analysis, contract, and wireframe confirmation, with chat fallback when unsupported |
| `confirm_authoring_stage` | Persist an approval or rejection for `schema`, `analysis`, `contract`, `wireframe`, or `execution_plan` after a fresh confirmation request |
| `build_wireframe` | Build a reviewable wireframe artifact from the confirmed contract |
| `finalize_wireframe` | Finalize the wireframe review, including layout notes and supported actions |
| `reopen_authoring_stage` | Reopen `analysis`, `contract`, `wireframe`, or `execution_plan` after a rejection or downstream scope change |
| `build_execution_plan` | Convert the finalized contract into a mechanical MCP tool-call plan |
| `generate_workbook_from_run` | Execute the confirmed plan, save the workbook, and persist validation and analysis reports |
| `create_workbook` | Load a `.twb` or `.twbx` template and initialize a rebuild-from-template workspace |
| `open_workbook` | Open an existing `.twb` or `.twbx` and keep its worksheets and dashboards for editing |
| `list_fields` | List all available dimensions and measures |
| `list_worksheets` | List worksheet names in the active workbook |
| `list_dashboards` | List dashboards and the worksheet zones they reference |
| `add_parameter` | Add an interactive parameter for what-if analysis |
| `add_calculated_field` | Add a calculated field with Tableau formula |
| `remove_calculated_field` | Remove a previously added calculated field |
| `clone_worksheet` | Clone an existing worksheet and its worksheet window |
| `preview_worksheet_refactor` | Preview worksheet-scoped field rewrites before mutating the workbook |
| `apply_worksheet_refactor` | Apply worksheet-scoped field rewrites while preserving the original worksheet |
| `add_worksheet` | Add a new blank worksheet |
| `configure_chart` | Configure chart type and field mappings |
| `configure_worksheet_style` | Apply worksheet-level styling: background color, axis/grid/border visibility |
| `configure_dual_axis` | Configure a dual-axis chart composition |
| `configure_chart_recipe` | Configure a showcase recipe chart such as `lollipop`, `donut`, `butterfly`, or `calendar` |
| `add_dashboard` | Create a dashboard combining worksheets |
| `add_dashboard_action` | Add filter, highlight, URL, or go-to-sheet actions to a dashboard |
| `set_worksheet_caption` | Set or clear a worksheet caption using plain text |
| `set_worksheet_hidden` | Hide or unhide a worksheet by updating its worksheet window metadata |
| `generate_layout_json` | Build an interactive structured dashboard flexbox layout |
| `list_capabilities` | Show cwtwb's declared support boundary |
| `describe_capability` | Explain whether a chart or feature is core, advanced, recipe, or unsupported |
| `analyze_twb` | Analyze a `.twb` file against the capability catalog; output includes both the full capability breakdown and the capability gap triage summary |
| `diff_template_gap` | Summarize the non-core gap of a template |
| `validate_workbook` | Validate a workbook against the official Tableau TWB XSD schema (2026.1) |
| `migrate_twb_guided` | Run the built-in TWB migration workflow and pause for warning confirmation when needed |
| `set_excel_connection` | Configure the datasource to use a local Excel workbook and register fields from the selected sheet |
| `set_mysql_connection` | Configure the datasource to use a local MySQL connection |
| `set_tableauserver_connection` | Configure connection to an online Tableau Server |
| `set_hyper_connection` | Configure the datasource to use a local Hyper extract connection |
| `save_workbook` | Save the workbook as `.twb` (plain XML) or `.twbx` (ZIP with bundled extracts and images) |

## MCP Prompts

The MCP server also exposes prompts that guide a datasource-first, human-in-the-loop workflow:

| Prompt | Purpose |
|---|---|
| `guided_dashboard_authoring` | Top-level orchestration prompt for `datasource -> schema -> analysis -> contract -> wireframe -> workbook` |
| `dashboard_brief_to_contract` | Convert a human brief plus schema summary into a strict contract draft |
| `light_elicitation` | Ask only the minimum missing business questions from a contract review |
| `authoring_execution_plan` | Turn a finalized contract into an execution-oriented internal MCP build plan |
| `worksheet_clone_refactor` | Guide a worksheet-scoped `open -> clone -> preview -> apply -> unhide -> save` refactor workflow for existing workbooks |

## Guided MCP Authoring Runs

Use the guided run flow when you want a more structured Agentic BI authoring experience than a single free-form tool sequence.

High-level flow:

1. `start_authoring_run(datasource_path=...)`
2. `intake_datasource_schema(run_id)`
3. Human confirms the schema, preferably with `interactive_stage_confirmation(..., stage="schema")`
4. `build_analysis_brief(...)`
5. In `agent_first` mode, author and present 2-4 candidate directions, then `finalize_analysis_brief(...)`
6. Human confirms the selected direction, preferably with `interactive_stage_confirmation(..., stage="analysis")`
7. `draft_authoring_contract(...)`
8. `review_authoring_contract_for_run(...)`
9. `finalize_authoring_contract(...)`
10. Human confirms the contract, preferably with `interactive_stage_confirmation(..., stage="contract")`
11. `build_wireframe(...)`
12. `finalize_wireframe(...)`
13. Human confirms the wireframe, preferably with `interactive_stage_confirmation(..., stage="wireframe")`
14. `build_execution_plan(...)`
15. `generate_workbook_from_run(...)`

`confirm_authoring_stage(...)` is still the persistence step when a client falls
back to chat or when replaying an already-explicit human decision. By default,
`execution_plan` remains an internal artifact and is not a human approval gate.

Every run writes versioned artifacts, for example:

```text
tmp/agentic_run/20260319-153045-a1b2c3d4/manifest.json
tmp/agentic_run/20260319-153045-a1b2c3d4/schema_summary.20260319-153046.json
tmp/agentic_run/20260319-153045-a1b2c3d4/contract_final.20260319-153120.json
tmp/agentic_run/20260319-153045-a1b2c3d4/execution_plan.20260319-153155.json
tmp/agentic_run/20260319-153045-a1b2c3d4/final_workbook.twb
tmp/agentic_run/20260319-153045-a1b2c3d4/validation_report.20260319-153205.json
tmp/agentic_run/20260319-153045-a1b2c3d4/analysis_report.20260319-153206.json
```

Supported datasource types for this workflow today:

- Excel (`.xls`, `.xlsx`, `.xlsm`)
- Hyper (`.hyper`)

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
- Dashboard filter, highlight, URL, and go-to-sheet actions
- Worksheet captions
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

Use the canonical layout tree shape for nested dashboards:

```json
{
  "type": "container",
  "direction": "horizontal",
  "children": [
    {"type": "worksheet", "name": "Sidebar", "fixed_size": 160},
    {
      "type": "container",
      "direction": "vertical",
      "children": [
        {"type": "worksheet", "name": "Header", "fixed_size": 80},
        {"type": "worksheet", "name": "Main Chart", "weight": 1}
      ]
    }
  ]
}
```

For compatibility with older MCP prompts and generated JSON files, `add_dashboard`
also accepts legacy container aliases and normalizes them recursively:
`{"type": "horizontal", "children": [...]}` and
`{"type": "vertical", "children": [...]}`. Unknown layout node types now raise a
clear error instead of silently creating an empty dashboard zone.

## Hyper-backed Example

The `examples/hyper_and_new_charts.py` example uses the `Sample - EU Superstore.hyper`
extract bundled directly in the package (`src/cwtwb/references/`) and resolves the
physical `Orders_*` table via Tableau Hyper API before switching the workbook connection.
No repository clone is needed — install with `pip install "cwtwb[examples]"` and run directly.

## Workbook Migration

cwtwb includes a migration subsystem for switching an existing `.twb` to a new
datasource — for example, repointing a workbook built on one Excel file to a
different Excel with a different schema, or migrating between language variants
of the same dataset.

### How it works

Migration is a multi-step workflow. Each step is available as both an MCP tool
and a Python function:

```
1. inspect_target_schema   →  Scan the target Excel and list its columns
2. profile_twb_for_migration  →  Inventory which fields the workbook uses
3. propose_field_mapping   →  Match source fields to target columns (fuzzy)
4. preview_twb_migration   →  Dry-run: show what would change, blockers/warnings
5. apply_twb_migration     →  Write the migrated .twb + JSON reports
```

`migrate_twb_guided` is a convenience wrapper that runs steps 2–5 in sequence
and pauses automatically when only low-confidence field matches remain, returning
a `warning_review_bundle` for human review before proceeding.

### Python example

```python
from cwtwb.migration import migrate_twb_guided_json
import json

# One-call guided migration
result = migrate_twb_guided_json(
    file_path="templates/SalesDashboard.twb",
    target_source="data/new_data_source.xlsx",
    output_path="output/SalesDashboard_migrated.twb",
)
bundle = json.loads(result)

if bundle["status"] == "warning_review_required":
    # Inspect low-confidence matches and confirm or override them
    print(bundle["warning_review_bundle"])
    # Re-run with confirmed mappings
    result = migrate_twb_guided_json(
        file_path="templates/SalesDashboard.twb",
        target_source="data/new_data_source.xlsx",
        output_path="output/SalesDashboard_migrated.twb",
        mapping_overrides={"Old Field Name": "New Column Name"},
    )
```

### MCP tool example

When using cwtwb as an MCP server, an AI agent can run the full workflow:

```
inspect_target_schema(target_source="data/new_data_source.xlsx")
→ returns column list and data types

migrate_twb_guided(
    file_path="templates/SalesDashboard.twb",
    target_source="data/new_data_source.xlsx",
    output_path="output/SalesDashboard_migrated.twb"
)
→ returns status: "applied" or "warning_review_required"
```

### Output files

A completed migration writes three files:

| File | Contents |
|---|---|
| `<output>.twb` | Migrated workbook with rewritten field references |
| `migration_report.json` | Per-field status: mapped / warning / blocked |
| `field_mapping.json` | Final source→target field mapping for audit |

### Scope parameter

`scope="workbook"` migrates all worksheets. Pass a worksheet name to limit
migration to a single sheet.

### Self-contained example

`examples/migrate_workflow/` contains a template `.twb`, the original
Superstore Excel, a target Chinese-locale Superstore Excel, and a runnable
script:

```bash
python examples/migrate_workflow/test_migration_workflow.py
```

## Project Structure

```text
cwtwb/
|-- src/cwtwb/
|   |-- __init__.py
|   |-- capability_registry.py
|   |-- config.py
|   |-- contracts/
|   |-- authoring_contract.py
|   |-- authoring_run.py
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
|   |-- skills/
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
