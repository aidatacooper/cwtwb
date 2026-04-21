# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.18.1] - 2026-04-21

### Fixed

- **Nested dashboard layout objects no longer render as empty dashboards**: `add_dashboard` now recursively normalizes legacy container aliases such as `{"type": "horizontal"}` and `{"type": "vertical"}` into the canonical `{"type": "container", "direction": ...}` layout model before XML generation.
- **Invalid dashboard layout nodes now fail loudly**: unknown layout node types raise a `ValueError` with the offending tree path instead of returning `"Created dashboard"` while producing an empty root `<zone>`.
- **MCP-generated layout JSON is safer for complex dashboards**: object layouts produced by `generate_layout_json` or passed directly through the MCP `add_dashboard` tool now preserve deeply nested worksheet zones instead of silently dropping child containers.

### Changed

- **Dashboard layout documentation now uses the canonical schema**: README, MCP layout helper docs, SDK docstrings, and the dashboard designer skill now recommend `type="container"` plus `direction="horizontal" | "vertical"` while documenting recursive compatibility for legacy aliases.
- **Dashboard layout regression coverage**: added a three-level nested legacy-layout test mirroring real MCP output (`horizontal -> vertical -> horizontal/vertical`) and asserting that `list_dashboards()` reports all worksheet zones.
- **Release tooling**: added `scripts/publish_from_env.ps1` so Windows releases can build and upload only the active package version from `.env` credentials without printing tokens.

## [0.18.0] - 2026-04-17

### Added

- **Worksheet clone and local refactor workflow**: added SDK and MCP/server support for duplicating an existing worksheet and rewriting only the cloned worksheet's field and calculation references.
  - New APIs and tools: `clone_worksheet`, `preview_worksheet_refactor`, and `apply_worksheet_refactor`
  - New worksheet visibility helper: `set_worksheet_hidden`
  - Worksheet refactor previews now report renamed local columns, rewritten formulas, cloned datasource-level calculations, and worksheet-local reference rewrites
- **Worksheet clone/refactor MCP prompt**: added the built-in `worksheet_clone_refactor` prompt for guiding an `open -> clone -> preview -> apply -> unhide -> save` workflow through the workbook tool surface.
- **Worksheet refactor example**: added `examples/worksheet_refactor_kpi_profit/` with a local source workbook copy, a runnable `generate_example.py`, and an output workbook containing a visible `1. KPI Profit` worksheet cloned from `1. KPI`.
- **Prompt example for worksheet refactor**: added `examples/prompts/demo_worksheet_refactor_kpi_profit_prompt.md` in the same style as the existing natural-language MCP prompt examples.
- **Regression coverage for worksheet clone/refactor**: added `tests/test_worksheet_refactor.py` covering both direct `TWBEditor` usage and `server.py` wrappers against the real `5 KPI Design Ideas (2).twb` workbook.
- **Regression coverage for MCP wrappers and prompt registration**: added targeted tests for worksheet clone/refactor MCP wrappers, worksheet visibility updates, and `worksheet_clone_refactor` prompt registration.

### Fixed

- **Cloned hidden KPI sheets remained invisible in Tableau Desktop**: cloned worksheet windows can now be explicitly unhidden so the generated worksheet appears in visible sheet tabs when opened in Tableau.
- **Worksheet refactor display labels could fall back to the old metric after clone + replace**: `apply_worksheet_refactor()` now performs a worksheet-local identity-normalization pass for generic `Calculation_*` fields, renames target-metric calculations to stable semantic names, rewrites worksheet references to those new identities, and returns `post_process` evidence (`renamed`, `rewrite_map`) through both the SDK and MCP layers.

## [0.18.0] - 2026-03-31

### Changed

- Routine package release with latest source updates since `0.17.0`.

## [0.17.0] - 2026-03-21

### Added

- **Guided MCP authoring runs**: added a datasource-first, human-in-the-loop workflow that starts from a real local Excel or Hyper file and writes versioned artifacts to `tmp/agentic_run/{run_id}/`.
  - New run lifecycle MCP tools: `start_authoring_run`, `list_authoring_runs`, `get_run_status`, `resume_authoring_run`
  - New guided authoring MCP tools: `intake_datasource_schema`, `draft_authoring_contract`, `review_authoring_contract_for_run`, `finalize_authoring_contract`, `confirm_authoring_stage`, `build_execution_plan`, `generate_workbook_from_run`
  - New `authoring_run.py` runtime with run manifests, confirmation gates, artifact versioning, execution-plan generation, and failure-state tracking
- **Datasource-first MCP prompts**: added `guided_dashboard_authoring`, `dashboard_brief_to_contract`, `light_elicitation`, and `authoring_execution_plan` to guide natural-language requests through schema intake, contract review, execution planning, and workbook generation.
- **Excel datasource connection support**: added `set_excel_connection` to the SDK/MCP surface so guided runs can repoint the workbook datasource to a local Excel file selected during schema intake.
- **New dashboard action types**: `add_dashboard_action` now supports `url` and `go-to-sheet` in addition to the existing `filter` and `highlight` behaviors.
- **Worksheet captions**: added `set_worksheet_caption` to the SDK/MCP surface for plain-text worksheet captions.
- **Authoring contract template update**: added `workbook_template` to the contract schema so guided runs can carry a template decision from contract finalization into execution planning.
- **Regression coverage for guided runs**: added `tests/test_agentic_authoring_v1.py` covering prompt registration, run lifecycle, Excel/Hyper schema intake, contract rewrite-after-rejection, end-to-end workbook generation, and failure-state handling.
- **Agent-first analysis guardrails**: guided authoring now enforces 2-4 candidate analysis directions before contract authoring can proceed, and the human-chosen `selected_direction_id` must be confirmed as part of the default guided path.
- **Regression coverage for agent-first contract execution**: added targeted tests for worksheet shorthand normalization, executive overview layout aliases, multi-direction analysis validation, and dual-axis execution planning for time-series combo charts.

### Changed

- **Examples and docs**: replaced the old pre-baked `agentic_mcp_authoring` demo artifacts with a runtime-oriented walkthrough that starts from a datasource file and lets the MCP workflow generate artifacts dynamically.
- **Guided prompt defaults**: the default human-facing checkpoints are now `schema`, `analysis`, `contract`, and `wireframe`. `execution_plan` is still persisted, but it is treated as an internal read-only artifact unless the human explicitly asks to inspect it.
- **Skill guidance**: updated the skills documentation and authoring workflow skill to recommend a gated flow of `datasource -> schema -> analysis -> contract -> wireframe -> generation`.
- **Profile-aware contract review**: the contract review flow remains generic while using external dataset profiles as hints during normalization and defaulting.

### Fixed

- **Hyper schema inspection robustness**: Hyper inspection now uses project `tmp/` paths, falls back more safely when temporary copies are unavailable, and raises clearer runtime errors when the local Hyper environment cannot inspect the datasource.
- **Workbook generation failure visibility**: guided runs now record `workbook_generation_failed` with the failed tool step and last error in the manifest, making interrupted runs resumable and diagnosable.
- **Worksheet shorthand loss during contract normalization**: top-level worksheet fields such as `rows`, `columns`, `measure_values`, `tooltip`, `color`, `label`, `detail`, `size`, `wedge_size`, and `geographic_field` are now promoted into canonical `encodings` so contract-finalized charts do not silently lose color, tooltip, or shelf mappings during execution.
- **Executive overview layout alias fallback**: layout patterns such as `top-kpis + trend-row + breakdown-row` now resolve to the canonical executive overview layout instead of falling back to a plain vertical stack.
- **Dual-axis combo planning for time-series trends**: `build_execution_plan(...)` now detects `Sales bar + Profit line`-style requests and emits `configure_dual_axis` instead of routing them through the single-mark `configure_chart` path; semantic validation was updated to assert both pane mark classes are present.

## [0.16.0] - 2026-03-19

### Fixed

- **`FieldRegistry.remove()` missing**: `TWBEditor.remove_calculated_field()` and its `remove_calculated_field` MCP tool called `self.field_registry.remove()`, but `FieldRegistry` only defined `unregister()`. Added the missing `remove()` method; the MCP tool now works correctly instead of raising `AttributeError`.
- **Dual-axis pane secondary ID mismatch**: `DualAxisChartBuilder` wrote `id="3"` for the secondary pane in both horizontal and vertical configurations, while all test assertions and internal lookups expected `id="2"`. Changed pane_2 id to `"2"` in both the same-measure (lollipop/donut) and different-measure (combo) branches.
- **`format_capability_catalog()` missing `level_filter` parameter**: The function signature accepted no arguments, but the capability registry design and test suite expected an optional `level_filter: str` parameter to restrict output to a single level (e.g. `"core"`). Added the parameter; calling without it preserves the existing full-catalog behavior.
- **`inspect_target_schema` crashes on non-Excel paths**: The MCP tool passed any path directly to `xlrd.open_workbook()`, raising `FileNotFoundError` or `XLRDError` for `.csv`, non-existent files, or unsupported formats. Added an extension check up-front and a `try/except` fallback; both now return a readable `"Unsupported…"` string instead of an exception.
- **`analyze_twb` missing Capability gap section**: `analyze_twb` returned only `report.to_text()`, omitting the decision-oriented gap summary that `diff_template_gap` produces separately. The tool now appends `report.to_gap_text()` so a single `analyze_twb` call includes both the capability catalog and the gap triage.

## [0.15.0] - 2026-03-18

### Added

- **XSD schema validation** against the official Tableau TWB XSD (2026.1), vendored at `vendor/tableau-document-schemas/`:
  - `TWBEditor.validate_schema()` — validates the in-memory workbook without saving first; returns a `SchemaValidationResult` with `valid`, `errors`, `schema_available`, and `to_text()` summary.
  - `validate_workbook` MCP tool — validates the current open workbook (in memory) or any `.twb`/`.twbx` file on disk by path. Errors are reported as informational; Tableau itself occasionally generates workbooks that deviate from the schema.
  - `validate_against_schema(root)` — public SDK function in `cwtwb.validator`, accepts an lxml `_Element` and returns `SchemaValidationResult`.
  - `SchemaValidationResult` exported from the top-level `cwtwb` package.
  - Two missing XSD imports (`http://www.tableausoftware.com/xml/user` and `http://www.w3.org/XML/1998/namespace`) resolved via local stub XSD files written to `vendor/tableau-document-schemas/schemas/2026_1/` at first use; schema is loaded once and cached for the process lifetime.

## [0.14.0] - 2026-03-17

### Added

- **`.twbx` (Packaged Workbook) support**: `TWBEditor` now reads and writes Tableau Packaged Workbook files transparently.
  - **Open**: `TWBEditor("file.twbx")` and `TWBEditor.open_existing("file.twbx")` unzip the archive, locate the embedded `.twb`, and parse it in-memory. The source ZIP path and inner filename are recorded for later re-packing.
  - **Save as `.twbx`**: `editor.save("output.twbx")` serializes the updated XML and re-packs it into a new ZIP, carrying over all bundled assets (`.hyper` data extracts, images, etc.) from the source `.twbx` automatically.
  - **Save as `.twb` from a `.twbx` source**: `editor.save("output.twb")` extracts just the workbook XML, discarding the packaging.
  - **Plain `.twb` → `.twbx`**: any `.twb`-sourced workbook can be packaged by saving with a `.twbx` extension; the result is a single-entry ZIP containing the workbook XML.
  - MCP tools `create_workbook`, `open_workbook`, and `save_workbook` all support `.twbx` paths with no changes to call signatures.
- **`tests/test_twbx_support.py`**: 25 pytest cases covering open, round-trip save, extract/image preservation, plain-TWB-to-TWBX conversion, modify-and-resave, and MCP tool integration.

## [0.13.0] - 2026-03-17

### Added

- **Rich-text `label_runs` in `configure_chart`**: Multi-style labels built from a list of run dicts. Each run supports `text` (literal string), `field` (field expression → `<field_ref>` CDATA), `prefix`, and per-run font attributes (`fontname`, `fontsize`, `fontcolor`, `bold`, `fontalignment`). Use `"\n"` as text to insert a paragraph separator. Pass `"fontalignment": None` to suppress the default alignment attribute. Enables KPI cards with two-line labels, dynamic titles with inline field values, and branded separators.
- **14 new `configure_worksheet_style` options**:
  - `hide_col_field_labels` / `hide_row_field_labels` — hide column and row field label headers in table/cross-tab views
  - `hide_droplines` — remove drop lines from mark tooltips
  - `hide_table_dividers` — remove row/column divider lines in cross-tab views
  - `hide_reflines` — hide reference lines
  - `disable_tooltip` — disable tooltip entirely (`tooltip-mode='none'`)
  - `pane_cell_style: dict` — pane-level cell text alignment, e.g. `{"text-align": "center", "vertical-align": "center"}`
  - `pane_datalabel_style: dict` — pane-level data label font family, size, and color
  - `pane_mark_style: dict` — pane-level mark color, stroke, transparency, and size (0.0–1.0 scale via `"size"` key)
  - `pane_trendline_hidden: bool` — hide trendline in pane style
  - `label_formats: list[dict]` — per-field label style (font, color, orientation, display toggle)
  - `cell_formats: list[dict]` — per-field table cell style
  - `header_formats: list[dict]` — per-field header height/width
  - `axis_style: dict` — global tick color plus per-field axis display and height control
- **`mark_color_1` in `configure_dual_axis`**: Explicit hex color for primary-axis marks, symmetric with the existing `mark_color_2`. Useful for pairing a gray bar (`mark_color_1`) against a blue target GanttBar (`mark_color_2`).
- **`color_map_1` in `configure_dual_axis`**: Datasource-level palette mapping for the primary-axis `color_1` field, using the same mechanism as `configure_chart(color_map=...)`.
- **`default_format` in `add_calculated_field`**: Optional Tableau number format string written as `default-format` on the column XML, e.g. `'c"$"#,##0,.0K'`.
- **`color_map` in `configure_dual_axis(extra_axes=[...])`**: Custom palette for `:Measure Names` when used as `"color"` on an extra axis. Each bucket is mapped to a hex color via a datasource-level `<encoding>` element.
- **`show_title` in dashboard layout nodes**: Pass `show_title: false` in a layout zone dict to suppress the worksheet title bar inside a dashboard zone.
- **Expanded test suite — 7 new test modules**:
  - `test_worksheet_style.py` — all 18 `configure_worksheet_style` options (hide flags, background, pane styles, per-field formats, axis style)
  - `test_label_runs.py` — text runs, field-ref runs, newline separator, font styling, prefix, fontalignment suppression, KPI card and dynamic title patterns
  - `test_dual_axis_basic.py` — horizontal/vertical dual-axis combos, shared axis, color encoding, filters
  - `test_dual_axis_advanced.py` — `mark_color_1/2`, `color_map_1`, `reverse_axis_1`, `hide_zeroline`, synchronized axis, `show_labels`, `size_value_1/2`
  - `test_dashboard_action_types.py` — highlight action (`tsc:brush`), field-captions param, multiple coexisting actions, error handling (unsupported type, unknown dashboard)
  - `test_mcp_tools.py` — `remove_calculated_field` (add/remove/re-add cycle), connection MCP wrappers, `inspect_target_schema`, `list_capabilities`, `analyze_twb`
  - `test_template_datasource_structure.py` — Superstore template structural sanity: column count, connection class, datasource-dependencies
- **`tests/README.md`**: Full test suite documentation — run instructions, file index grouped by coverage area, function-to-test mapping table, known gaps.

### Changed

- **Examples reorganized**: Scripts moved from `examples/` root into `examples/scripts/` with consistent `demo_` prefix naming. `examples/README.md` updated with a new 7-script progression table and expanded Showcase Projects section.
- **Exec Overview example refined**: Dashboard header updated to 2023, KPI cards use `pane_cell_style` for center alignment, `show_title: false` on Sales by Sub-Category worksheet, spacer zone added for axis alignment.

## [0.12.0] - 2026-03-13

### Added
- **Bundled Hyper Extracts**: `Sample - EU Superstore.hyper` and `Sample _ Superstore.hyper` are now included in `src/cwtwb/references/` and distributed with the wheel. `hyper_and_new_charts.py` and `build_exec_overview.py` no longer require a cloned repository.
- **Progressive Examples**: All scripts in `examples/scripts/` (5 steps, Beginner → Advanced) and prompts in `examples/prompts/` (10 steps, Beginner → Advanced) now carry explicit step numbers and difficulty labels. `examples/README.md` rewritten with a Quick Start section and full progression tables.

### Fixed
- **Packaging**: Removed redundant `artifacts` declarations from `pyproject.toml`. All non-Python files under `src/cwtwb/` are git-tracked and included in the wheel automatically via `packages = ["src/cwtwb"]`.
- **`.gitignore`**: Added `!src/cwtwb/references/*.hyper` exception so bundled Hyper files are tracked by git and always present at wheel build time.
- **Examples — zero external dependencies**: All scripts in `examples/scripts/` and prompts in `examples/prompts/` updated to use `TWBEditor("")` / `create_workbook("")` (built-in default template) instead of hard-coded paths to `templates/twb/superstore.twb`. All work after a plain `pip install cwtwb`.

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
