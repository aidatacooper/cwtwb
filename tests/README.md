# cwtwb Test Suite

This directory contains the full test suite for the **cwtwb** SDK and MCP server.

## Running Tests

```bash
# Run everything
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run a single file
pytest tests/test_connections.py -v

# Run a single test class
pytest tests/test_worksheet_style.py::TestHideBasicOptions -v

# Run with coverage (requires pytest-cov)
pytest tests/ --cov=src/cwtwb --cov-report=term-missing
```

---

## Test File Index

Files are grouped by what they cover. Within each group, they are ordered from
most fundamental to most complex.

### SDK Core — Chart Generation

| File | Coverage |
|------|----------|
| `test_charts.py` | `configure_chart`: mark-type aliases (Scatterplot→Circle, Heatmap→Square, Tree Map, Bubble Chart) |
| `test_generate_pie.py` | Pie chart full XML structure: mark, color encoding, wedge-size, row/col shelf |
| `test_interactive_features.py` | `tooltip` and `filters` on charts |
| `test_interactive_features.py` | Categorical filter: union groupfilter XML |
| `test_chart_routing.py` | Chart routing policy: pattern mapping, dispatcher, route family and support level |

### SDK Core — Dual Axis

| File | Coverage |
|------|----------|
| `test_dual_axis_basic.py` | Horizontal/vertical dual-axis combos; pane marks; shared axis; color encoding; filters |
| `test_dual_axis_advanced.py` | `mark_color_1/2`, `color_map_1`, `reverse_axis_1`, `hide_zeroline`, synchronized axis, `show_labels`, `size_value_1/2` |

### SDK Core — Worksheet Styling

| File | Coverage |
|------|----------|
| `test_worksheet_style.py` | All `configure_worksheet_style` options: hide_axes, hide_gridlines, hide_zeroline, hide_borders, hide_band_color, background_color, hide_col/row_field_labels, hide_droplines, hide_reflines, hide_table_dividers, disable_tooltip, pane_cell_style, pane_datalabel_style, pane_mark_style, pane_trendline_hidden, label_formats, cell_formats, header_formats, axis_style |

### SDK Core — Rich-Text Labels

| File | Coverage |
|------|----------|
| `test_label_runs.py` | `label_runs`: text runs, field-ref runs, newline paragraph separator (U+00C6), font styling, prefix, fontalignment suppression, KPI card pattern, dynamic title pattern, replace-on-re-configure |

### SDK Core — Parameters & Calculated Fields

| File | Coverage |
|------|----------|
| `test_level1_features.py` | `add_parameter`: range, list, multiple, internal-name tracking |
| `test_twb_structure.py` | Parameters and calculated fields via TWBAssert DSL |
| `test_mcp_showcase_workbook.py` | `add_calculated_field` type inference (quantitative/nominal) |

### SDK Core — Connections

| File | Coverage |
|------|----------|
| `test_connections.py` | SDK: `set_mysql_connection`, `set_tableauserver_connection`, `set_hyper_connection` (with XML verification) |
| `test_mcp_tools.py` | MCP wrappers: same three tools via `server.py`; XML verification |
| `test_template_datasource_structure.py` | Superstore template's column count, connection class, datasource-dependencies |

### SDK Core — Dashboards

| File | Coverage |
|------|----------|
| `test_declarative_dashboards.py` | Complex declarative JSON layout; simple horizontal/vertical string layouts |
| `test_layout_ascii.py` | `generate_layout_json` tool; JSON file creation; dashboard from JSON path |
| `test_level1_features.py` | Filter zone and ParamCtrl zone in dashboard layout |
| `test_twb_structure.py` | Dashboard structure via TWBAssert DSL |

### SDK Core — Dashboard Actions

| File | Coverage |
|------|----------|
| `test_dashboard_actions.py` | `filter` action: XML structure, link expression, command params |
| `test_dashboard_action_types.py` | `highlight` action: `tsc:brush` command, field-captions param, special-fields=all, multiple coexisting actions; error handling (unsupported type, unknown dashboard, custom caption/event_type) |

### SDK Core — Map Charts

| File | Coverage |
|------|----------|
| `test_level1_features.py` | Map chart: Lat/Lon shelf, mapsources, color/size encodings |
| `test_twb_structure.py` | Map with map_fields LOD; map without map_fields |

### SDK Core — Recipe Charts

| File | Coverage |
|------|----------|
| `test_mcp_showcase_workbook.py` | All four recipes (Lollipop, Donut, Butterfly, Calendar); auto-prerequisite calculated fields; invalid recipe name; missing required args |

### SDK Core — TWBAssert Structural Tests

| File | Coverage |
|------|----------|
| `test_twb_structure.py` | Comprehensive structural assertions (via `TWBAssert` DSL) for Bar, Line, Pie, Area, Map, KPI text table, Parameters, Calculated Fields, Dashboards, Filters |

### MCP Tool Layer

| File | Coverage |
|------|----------|
| `test_e2e.py` | Full MCP workflow: create → list_fields → add_calculated_field → configure_chart → add_dashboard → save; clean output (no spurious top-level elements) |
| `test_mcp_tools.py` | `remove_calculated_field` (add/remove/re-add cycle, XML verification); connection MCP wrappers; `inspect_target_schema` (non-hyper path); `list_capabilities`; `analyze_twb` |
| `test_mcp_showcase_workbook.py` | All supported chart types via MCP tools end-to-end |
| `test_existing_workbook_editing.py` | `open_workbook`, reconfigure worksheets, parameter restore, dashboard zone ID continuity, thumbnail stripping |

### Analysis, Capability Registry & Migration

| File | Coverage |
|------|----------|
| `test_capability_registry.py` | Alias resolution, recipe listing, level summary, catalog text, capability detail |
| `test_twb_analyzer.py` | `analyze_workbook` on generated and real workbooks; gap text; `diff_template_gap`; `describe_capability` |
| `test_migration_workflow.py` | Full migration pipeline: profile, propose, preview, apply, guided flow (pause/confirm), MCP tool JSON payloads |

### Integration / Replica Tests

| File | Coverage |
|------|----------|
| `test_overview_replica.py` | Full Overview workbook: parameters, calculated fields, Map/Area/Text charts, filter/paramctrl zones |
| `test_c2_replica.py` | c.2 (2) multi-section dashboard: 8 worksheets, KPI row, nested 2×2 grid, zone structure |
| `test_screenshot2layout.py` | Dashboard-from-JSON-layout workflow for two real-world dashboard shapes; JSON layout files optional (skip if absent) |
| `test_hyper_example.py` | `_resolve_orders_table_name` helper in the hyper example script |

### Miscellaneous

| File | Coverage |
|------|----------|
| `test_template_datasource_structure.py` | Superstore template structural sanity: column presence, connection class, datasource-dependencies |
| `test_overview_full.py` | Full Exec Overview dashboard recreation (high-fidelity; may require all template assets) |
| `test_debug.py` | Legacy debug script (not pytest) |

---

## Test Infrastructure

| File | Purpose |
|------|---------|
| `conftest.py` | Shared fixtures: `editor` (blank template) and `editor_superstore` (Superstore template) |
| `twb_assert.py` | `TWBAssert` fluent assertion DSL for XML structure checks |
| `parse_twb.py` | Low-level XML parse helpers |

---

## Coverage Map

The table below maps each SDK/MCP public function to its primary test file.

| Function | Primary Test File |
|----------|------------------|
| `create_workbook` / `open_workbook` | `test_e2e.py`, `test_existing_workbook_editing.py` |
| `add_worksheet` | `test_charts.py`, `test_twb_structure.py` |
| `configure_chart` | `test_charts.py`, `test_generate_pie.py`, `test_twb_structure.py`, `test_interactive_features.py` |
| `configure_dual_axis` | `test_dual_axis_basic.py`, `test_dual_axis_advanced.py`, `test_mcp_showcase_workbook.py` |
| `configure_worksheet_style` | `test_worksheet_style.py` |
| `configure_chart_recipe` | `test_mcp_showcase_workbook.py` |
| `label_runs` | `test_label_runs.py` |
| `add_calculated_field` | `test_e2e.py`, `test_mcp_showcase_workbook.py`, `test_twb_structure.py` |
| `remove_calculated_field` | `test_mcp_tools.py` |
| `add_parameter` | `test_level1_features.py`, `test_twb_structure.py` |
| `add_dashboard` | `test_declarative_dashboards.py`, `test_twb_structure.py`, `test_c2_replica.py` |
| `add_dashboard_action` (filter) | `test_dashboard_actions.py` |
| `add_dashboard_action` (highlight) | `test_dashboard_action_types.py` |
| `generate_layout_json` | `test_layout_ascii.py` |
| `set_mysql_connection` | `test_connections.py`, `test_mcp_tools.py` |
| `set_tableauserver_connection` | `test_connections.py`, `test_mcp_tools.py` |
| `set_hyper_connection` | `test_connections.py`, `test_mcp_tools.py` |
| `inspect_target_schema` | `test_mcp_tools.py` |
| `list_fields` / `list_worksheets` / `list_dashboards` | `test_e2e.py`, `test_existing_workbook_editing.py` |
| `list_capabilities` | `test_mcp_tools.py`, `test_capability_registry.py` |
| `analyze_twb` / `diff_template_gap` / `describe_capability` | `test_twb_analyzer.py`, `test_mcp_tools.py` |
| `profile_twb_for_migration` | `test_migration_workflow.py` |
| `propose_field_mapping` | `test_migration_workflow.py` |
| `preview_twb_migration` | `test_migration_workflow.py` |
| `apply_twb_migration` | `test_migration_workflow.py` |
| `migrate_twb_guided` | `test_migration_workflow.py` |

---

## Known Gaps & Out-of-Scope

- **`inspect_target_schema` on real `.hyper` files**: requires `tableauhyperapi` installed and a real `.hyper` file. The MCP test covers the non-hyper fallback path only.
- **`configure_chart` with `label_param`**: parameter-driven label content is not separately unit-tested (tested implicitly via `label_runs` with `param` key).
- **`configure_chart` with `customized_label`** (raw string override): no dedicated test; simple text labels are covered by `test_label_runs.py`.
- **`url` dashboard action type**: explicitly unsupported; error-path tested in `test_dashboard_action_types.py`.
- **Multi-table hyper connection** (`tables` parameter in `set_hyper_connection`): no unit test; requires a real multi-table `.hyper` file.
- **MCP resources** (`read_skill`, `read_skills_index`, `read_tableau_functions`): no automated tests; they are thin file-read wrappers.
