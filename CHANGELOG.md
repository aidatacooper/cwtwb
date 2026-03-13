# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.11.0] - 2026-03-13

### Added
- **Table Calculation Fields**: `add_calculated_field` now accepts a `table_calc` parameter (e.g. `table_calc="Rows"`) that writes a `<table-calc ordering-type="..."/>` child inside the `<calculation>` element, enabling `RANK_DENSE`, `RUNNING_SUM`, `WINDOW_AVG`, and all other Tableau table calculation functions to work correctly in the generated workbook.
- **Table Calc Column Instances**: `_setup_datasource_dependencies` in `builder_base` now automatically propagates a `<table-calc ordering-type="Columns"/>` element to any `<column-instance>` whose source column contains a table-calc calculation, matching the pattern Tableau uses for rank and running calculations.
- **Multi-field Label Support**: `configure_chart` now accepts `label_extra: list[str]` to bind multiple `<text>` encodings to a single mark, enabling combined text labels such as a sales figure plus a state name in one cell.
- **Row Dimension Label Hiding**: `configure_worksheet_style` now accepts `hide_row_label: str` to suppress the header column that Tableau renders for a rows-shelf dimension (adds `<style-rule element="label"><format attr="display" ... value="false"/></style-rule>`).
- **Donut Chart via `extra_axes`**: Pie panes in `configure_dual_axis(extra_axes=[...])` now automatically receive a `<size column="[Multiple Values]"/>` encoding when `measure_values` is present, completing the standard Tableau donut chart pattern without manual intervention.
- **Non-traditional Pie Mark via `BasicChartBuilder`**: `configure_chart(mark_type="Pie")` without `color` or `wedge_size` now routes through `BasicChartBuilder` instead of `PieChartBuilder`, allowing a Pie mark to display a label (e.g. a rank number) on a dimension-shelved view while retaining full rows/sort/filter support.
- **`selection-relaxation-disallow` on single-pane charts**: All charts built by `BasicChartBuilder` now set `selection-relaxation-option="selection-relaxation-disallow"` on the `<pane>` element, matching Tableau's default for filtered single-view worksheets and preventing click-interaction from relaxing Top N or categorical filters.

### Fixed
- **Measure Names filter ordering**: In `configure_dual_axis` with `extra_axes` containing `measure_values`, the Measure Names `<filter>` is now inserted into the `<view>` before Top N filters, matching the element order Tableau produces when creating these worksheets interactively.

### Example
- **Exec Overview Recreated** (`examples/superstore_recreated/`): Added `Rank CY` table calculation field; corrected `Top 5 Locations` to use Pie mark with Rank CY label; corrected `Top 5 Locations text` and `Sales by Sub-Category` to match reference workbook (donut size encoding, label style rules, filter order).

## [0.10.0] - 2026-03-11

### Fixed
- **XML Schema Conformity**: Fixed strict DTD validation errors related to `<pane>` child element ordering (e.g., `<customized-label>` must precede `<style>`) and `<datasource>` element ordering.
- **Customized Labels**: Fixed `<customized-label>` generation to correctly wrap dynamic template variables with physical `<` and `>` runs within the XML `<formatted-text>` nodes, complying with strict formatting limits.
- **Object-Graph Relationship Wiping**: Completely rewrote the `set_hyper_connection` logic for multi-table connections. It now preserves table-level relational links by surgically updating individual pre-existing `<object-graph>/<relation>` attributes correctly matching object definitions instead of flattening them into an unmapped collection.

### Added
- **Charting Capabilities**: Added parameters `axis_fixed_range` to configure exact visual bounds on measures, `color_map` for granular dataset-level color palette assignments, `mark_sizing_off` to disable auto scaling, `customized_label` for rich template texts, and `text_format` for rapid formatting adjustments.
- **Dashboard Enhancements**: Added support for explicit `"empty"` layout model objects acting as blank spacers within absolute sizing layouts.
- **MCP Server Capabilities**: Exposed `configure_worksheet_style` tool expressly to cleanly edit gridlines and aesthetics independently of core configuration.

## [0.9.0] - 2026-03-10

### Added
- **Unified Recipe Chart API**: Added `configure_chart_recipe` as the single MCP/server entrypoint for showcase recipes, covering `lollipop`, `donut`, `butterfly`, and `calendar` via one registry-driven dispatcher.
- **Recipe Validation Coverage**: Added regression tests for unknown recipe rejection, required-argument validation, automatic prerequisite field creation, and full `all_supported_charts` showcase reconstruction through the unified recipe API.

### Changed
- **Recipe Tool Surface**: Replaced the old recipe-specific MCP tools with one `configure_chart_recipe` interface to keep the public API compact as more showcase patterns are added.
- **Recipe Defaults**: Donut and Calendar recipes now auto-create their standard helper calculations (`min 0` and `Sales Over 400`) when those defaults are used and the fields are missing.
- **Examples and Prompts**: Updated README, examples, skill docs, and the showcase MCP prompt to teach the unified recipe workflow instead of enumerating one tool per recipe chart.

### Removed
- **Recipe-Specific MCP Tools**: Removed `configure_lollipop_chart`, `configure_donut_chart`, `configure_butterfly_chart`, `configure_calendar_chart`, and `apply_calendar_chart_layout` from the public MCP/server API.

## [0.8.0] - 2026-03-09

### Added
- **Capability Registry**: Added a shared capability catalog that classifies chart, encoding, dashboard, action, connection, and feature support into `core`, `advanced`, `recipe`, and `unsupported` tiers.
- **TWB Gap Analysis**: Added `twb_analyzer.py` plus MCP tools `list_capabilities`, `describe_capability`, `analyze_twb`, and `diff_template_gap` so templates can be evaluated against the declared product boundary before implementation work begins.
- **Hyper Example Coverage**: Added `tests/test_hyper_example.py` to lock in the Advent Calendar Hyper example's physical `Orders_*` table resolution via Tableau Hyper API.

### Changed
- **Product Positioning**: Updated the root README and example READMEs to describe `cwtwb` as a workbook engineering toolkit rather than a conversational analysis competitor.
- **Chart Architecture**: Refactored chart handling into focused modules under `src/cwtwb/charts/`, including dispatcher, pattern mapping, routing policy, helpers, and a dedicated text builder while keeping the public `configure_chart` API stable.
- **Dashboard Architecture**: Split dashboard orchestration, layout resolution, datasource dependency generation, and action creation into dedicated modules while keeping `DashboardsMixin` as a thin compatibility facade.
- **Layout Architecture**: Split declarative layout computation and XML rendering into `layout_model.py` and `layout_rendering.py`, leaving `layout.py` as a compatibility export layer.
- **MCP Architecture**: Split the MCP server implementation into `mcp/app.py`, `mcp/state.py`, `mcp/resources.py`, `mcp/tools_support.py`, `mcp/tools_layout.py`, and `mcp/tools_workbook.py`, with `server.py` now acting as a thin compatibility entry point.
- **Advanced Hyper Example**: Updated `examples/hyper_and_new_charts.py` to prefer the Tableau Advent Calendar `Sample - EU Superstore.hyper` extract and resolve the physical `Orders_*` table name automatically.

### Fixed
- **Hyper Extract Selection**: The advanced Hyper example no longer picks the first bundled `.hyper` file opportunistically and instead targets the intended Superstore extract.
- **Hyper Table Resolution**: The advanced Hyper example now resolves the real physical `Orders_*` table name instead of using an incorrect generic table name.

## [0.7.0] - 2026-03-06

### Added
- **Agent Skills Workflow System**: Introduced 4 specialized skill files that provide expert-level guidance to AI agents during dashboard creation, inspired by Jeffrey Shaffer (Tableau Visionary Hall of Fame).
  - `calculation_builder.md` — Phase 1: Parameters, calculated fields, LOD expressions
  - `chart_builder.md` — Phase 2: Chart type selection, encodings, filter strategy
  - `dashboard_designer.md` — Phase 3: Layout design, filter panels, interaction actions
  - `formatting.md` — Phase 4: Number formats, color strategy, sorting, tooltips
- **Skills MCP Resources**: Skills are exposed via MCP protocol as `cwtwb://skills/index` and `cwtwb://skills/{skill_name}`, allowing AI agents to load domain expertise on demand.
- **Updated MCP Server Instructions**: Server instructions now prompt AI agents to read skills before each phase for professional-quality output.

### Changed
- **ROADMAP**: Updated `docs/ROADMAP.md` — marked completed P0 items (module refactor ✅, version sync ✅), added new Skills workflow section.
- **Package Build**: Added `artifacts` config in `pyproject.toml` to ensure `.md` skill files are distributed with the PyPI wheel.

## [0.6.0] - 2026-03-06

### Added
- **Runtime TWB Validator**: `save()` now automatically validates TWB XML structure before writing to disk. Fatal errors (missing `<workbook>`, `<datasources>`, `<table>`) raise `TWBValidationError` and block saving; non-fatal warnings are logged. Validation can be disabled via `save(path, validate=False)`.
- **`map_fields` Parameter**: New parameter for `configure_chart(mark_type="Map", ...)` allowing users to specify additional geographic LOD fields (e.g. `map_fields=["Country/Region", "City"]`).
- **TWBAssert DSL**: Chainable assertion API (`tests/twb_assert.py`) for structural TWB validation in tests, with 20+ assertion methods covering worksheets, encodings, filters, parameters, calculated fields, dashboards, and maps.
- **Shared Test Fixtures**: Added `tests/conftest.py` with `editor` and `editor_superstore` pytest fixtures.
- **Structure Test Suite**: 19 new tests in `tests/test_twb_structure.py` covering Bar, Line, Pie, Area, Map, KPI, Parameters, Calculated Fields, Dashboards, and Filters.
- **Project Roadmap**: Added `docs/ROADMAP.md` with P0–P3 priority issues and feature plans.

### Changed
- **Module Architecture**: Refactored `twb_editor.py` (2083→375 lines) into Mixin classes:
  - `charts.py` (ChartsMixin) — `configure_chart` and 9 chart helper methods
  - `dashboards.py` (DashboardsMixin) — `add_dashboard` and dashboard actions
  - `connections.py` (ConnectionsMixin) — MySQL and Tableau Server connections
  - `parameters.py` (ParametersMixin) — parameter management
  - `config.py` — shared constants and `_generate_uuid`
- **Version Management**: `__init__.py` now dynamically reads the version from `pyproject.toml` via `importlib.metadata` instead of hardcoding it.
- **API Exports**: `__init__.py` now exports `TWBEditor`, `FieldRegistry`, and `TWBValidationError`.
- **Worksheet XML Structure**: Improved `add_worksheet` to generate proper `<panes>/<pane>/<view>` hierarchy, `<style>` element, and `<simple-id>` placement per Tableau XSD schema.

### Fixed
- **Error Handling**: Replaced 6 instances of `except Exception: pass` with specific exception types (`KeyError`, `ValueError`) and proper `logging` output across `twb_editor.py`, `layout.py`.
- **Circular Import**: Extracted `REFERENCES_DIR` and path constants to `config.py`, eliminating circular imports between `twb_editor.py` and `server.py`.
- **Redundant Imports**: Removed 4 function-level `import` statements (`re`, `copy`, `dataclasses.replace`) by consolidating them at module level.

### Breaking Changes
- **Map Charts**: `configure_chart(mark_type="Map")` no longer automatically adds `Country/Region` as an LOD field. Users must now explicitly pass `map_fields=["Country/Region"]` if needed.

## [0.5.3] - 2026-03-05

### Fixed
- **Calculated Field Parsing**: Improved parameter replacement regex to safely handle both `[ParamName]` and `[Parameters].[ParamName]` formats, preventing double-prefixing and broken expressions.

## [0.5.2] - 2026-03-05

### Added
- **Business Profitability Overview Prompt**: Added `examples/prompts/overview_business_demo.md` to demonstrate creating an interactive what-if profitability dashboard with parameters and dashboard actions.

### Fixed
- **Packaging Issues**: Pinned `hatchling<1.27.0` to workaround a `twine` metadata validation error related to `license-files` and fixed Windows encoding issues during package build.

## [0.5.1] - 2026-03-04

### Changed
- **License**: Updated project license from MIT to AGPL-3.0-or-later.

## [0.5.0] - 2026-03-02

### Added
- **Zero-Config Blank Templates**: The SDK and MCP server now come with a built-in `empty_template.twb` and a minimal `Sample - Superstore - simple.xls` dataset.
- **Dynamic Connection Resolution**: When initializing `TWBEditor` without a `template_path`, it automatically resolves and rewrites the internal Excel connection to the runtime absolute path of the bundled sample dataset.
- **Always-Valid Workbooks**: `clear_worksheets()` now guarantees the creation of at least one default worksheet (`Sheet 1`), ensuring generated TWB files are completely valid and openable in Tableau Desktop immediately upon creation.

### Changed
- **MCP Tool `create_workbook`**: The `template_path` parameter is now optional. When omitted, it boots up the zero-config blank template.
- **XML Element Ordering Fix**: `add_worksheet` and `add_dashboard` now strictly enforce the Tableau XSD schema by smartly inserting XML nodes *before* `<windows>`, `<thumbnails>`, and `<external>` tags instead of appending them at the end.

## [0.4.0] - 2026-02-28

### Fixed
- **Dashboard Sizing Bug**: Added `sizing-mode="fixed"` to the dashboard `<size>` element. This ensures that custom dimensions (width/height) specified in `add_dashboard` are correctly enforced by Tableau Desktop.

### Added
- **New Showcase Prompt**: Added `examples/prompts/demo_auto_layout4_prompt.md` in English, demonstrating complex nested layouts with fixed headers and KPIs.
- **Enhanced Testing**: Added assertions to verify `sizing-mode` in `test_declarative_dashboards.py`.

## [0.3.0] - 2026-02-28

### Added

- **Agentic UX Tool: `generate_layout_json`**:
  - Introduced a dedicated MCP tool tailored for Language Models to handle complex dashboard layouts gracefully avoiding `EOF` (End of File) payload oversize crashes.
  - Automatically wraps standard nested `layout` dicts inside the payload with a human-readable `_ascii_layout_preview`, persisting an easy-to-review design draft to local disk.
  - Generates perfectly calculated XML `<zone>` absolute coordinates (in Tableau's 100,000 scale) for both relative weighting (`weight`) and exact sizes (`fixed_size`).
- `TWBEditor.add_dashboard()` intelligent parsing:
  - If given a file path, it now smartly unpacks the layout JSON, automatically extracting `"layout_schema"` and safely discarding extraneous metadata (like the ASCII diagram).
- **Prompt Strategies (`demo_simple.md`)**:
  - Updated the golden prompt strategy guide showing models how to seamlessly split reasoning logic: Step 1 (Tool: write layout to disk) -> Step 2 (Tool: pass file path to build dashboard).

## [0.2.0] - 2026-02-28

### Added

- **Database Connections**:
  - `TWBEditor.set_mysql_connection`: Configure TWB to load data from a Local MySQL database.
  - `TWBEditor.set_tableauserver_connection`: Configure TWB for a Tableau Server hosted datasource.
  - Automatically clears template-included dashboards, worksheets, metadata, and column aliases during config to prevent phantom "ghost" fields.
- **Dynamic Field Registration**:
  - The `field_registry` will now automatically infer the field type natively via naming heuristics when initializing `configure_chart` on strictly offline unknown schemas.
- **Declarative JSON Dashboard Layouts**:
  - `add_dashboard` now accepts a deeply nested dictionary (JSON-friendly) `layout` schema, allowing complex, FlexBox-like hierarchical layouts.
  - `add_dashboard` `layout` parameter also directly accepts a file path (string) to a `.json` file, easing the payload size for MCP LLM calls.
  - Generates perfectly calculated XML `<zone>` absolute coordinates (in Tableau's 100,000 scale) for both relative weighting (`weight`) and exact sizes (`fixed_size`).
  - Added `demo_declarative_layout.py` showcasing the JSON engine.
- **MCP Server Tools**:
  - Exposed `set_mysql_connection` and `set_tableauserver_connection` to the MCP Server.
  - Upgraded `add_dashboard` MCP tool to accept JSON-based dictionaries and JSON file paths for the `layout` schema.
- **Examples & Documentation**:
  - Reorganized the `examples/` directory into `scripts/` (for Python demos) and `prompts/` (for natural language MCP prompts).
  - Extracted test workflows into runnable demos (`demo_e2e_mcp_workflow.py` and `demo_connections.py`).

## [0.1.0] - 2026-02-27

### Added

- **Core library** (`cwtwb`):
  - `FieldRegistry`: Field name ↔ TWB internal reference mapping with expression parsing (SUM, AVG, COUNT, YEAR, etc.)
  - `TWBEditor`: lxml-based TWB XML editor supporting:
    - Template loading and field initialization
    - Calculated field management (add/remove)
    - Worksheet creation with configurable chart types (Bar, Line, Pie, Area, Circle, Text, Automatic)
    - Color, size, label, detail, and wedge-size encodings
    - Dashboard creation with layout-flow zone structure (vertical, horizontal, grid-2x2)
    - Valid TWB output compatible with Tableau Desktop

- **MCP Server** (`server.py`):
  - 8 atomic tools: `create_workbook`, `list_fields`, `add_calculated_field`, `remove_calculated_field`, `add_worksheet`, `configure_chart`, `add_dashboard`, `save_workbook`
  - FastMCP-based stdio transport

- **Dashboard layouts**:
  - Verified against Tableau Dashboard Layout Templates (c.2 (2) reference)
  - Dashboard windows use `<viewpoints>` + `<active>` structure (not `<cards>`)
  - Zone structure uses `layout-flow` with `param='vert'/'horz'`

- **Tests**:
  - `test_debug.py`: Step-by-step debug test generating intermediate TWB files
  - `test_e2e.py`: End-to-end integration test covering all MCP tools
  - `test_c2_replica.py`: Full replica of c.2 (2) dashboard layout with 8 worksheets

- **Package configuration**:
  - `pyproject.toml` with hatchling build backend
  - `cwtwb` CLI entry point
