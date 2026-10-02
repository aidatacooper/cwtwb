# Case-driven SDK enhancements

## 2019 WW34: single-sheet Top N manufacturers

Each region must rank manufacturers independently. The earlier dual-axis API had no way to describe its INDEX addressing, ordered dimensions, descending quantity sort, or nested calculation addressing. `configure_dual_axis(table_calc_overrides=...)` now exposes the shared chart addressing API through the builder, dispatcher, Python facade, and MCP. Structured specifications accept `order` field lists, `sort` with `direction` and `using`, `level_break`, and nested `field` expressions. Dimension shelves now cross a dual-axis measure union instead of adding dimension and measure expressions.

```python
table_calc_overrides={
    "Index": [{"ordering_type": "Field", "level_break": "Manufacturer Category",
               "order": ["Region", "Manufacturer Category"],
               "sort": {"direction": "DESC", "using": "SUM(Quantity)"}}]
}
```

## 2026 WW06: apply dates and deselect the Apply button

The Apply control copies minimum and maximum selected dates into parameters. A filter action then maps a constant false source field to a constant true target field on the button itself, so the selection clears. The previous `fields` API mapped each field to itself. `add_dashboard_action(field_mappings={"False": "True"})` now supports distinct source and target fields and a direct target worksheet. Existing same-field filter actions keep their dashboard target and exclusions. The API rejects conflicting `fields`, empty mappings, and mappings on non-filter actions before creating an action.

Tests cover ranked addressing on both shelves, nested calculations, MCP forwarding, mapped filter payloads, invalid mappings, and legacy action behavior. Cloud rendering and interaction acceptance are documented in the case repository separately from SDK regression tests.

## 2019 WW29: independently scaled monthly Gantt panels

The author uses a separate quantitative domain for each segment. Styling a global
axis cannot reproduce those panels. `configure_worksheet_style(axis_style={
"encodings": [...]})` now exposes field-bound, scoped axis encodings: independent
or fixed ranges, bounds, domain expansion, and axis classes. Fields are resolved
through the registry rather than requiring caller-authored XML references.

## 2019 WW31: dark spatial route overlays

Route lines and venue points must share one map. Repeated generated longitude
axes now fold into one spatial overlay without incorrectly enabling the modern
`Layers` feature. `map_style={"map_style": "dark", "washout": 0}` configures the
basemap through the SDK. Datasource palette buckets now quote string members and
keep boolean/set members as boolean literals, so region colors bind correctly.

## 2019 WW33: overlaid bars and scoped table formatting

Distinct continuous measures on a column dual axis must use a shared axis class,
with only the second axis folded. Leading dimensions cross the measure union.
Field-specific display/range encodings can independently hide those axes while
preserving labels. `pane_formats` accepts pane-wide formats plus `scope` and
`data_class` selectors, allowing consistent row sizing without changing marks.

## 2019 WW34: categorical palette binding and manufacturer labels

Primary-axis categorical palettes now register a local datasource instance rather
than a fully qualified worksheet reference. This fixes default Tableau colors in
region-partitioned Top N bars. The same correction is available to every dual-axis
chart, without case-specific field names or values.

## 2019 WW30 and 2026 WW05: legend presentation

Layout color zones support `show_title=False` and `mode="horizontal"`. This
preserves the author's compact horizontal legend instead of introducing a titled
vertical control. Worksheet zones retain their existing width fitting behavior.

## 2026 WW04: parameter captions and title alignment

The author's control captions differ from parameter identities. Layout `paramctrl`
and `filter` zones now accept optional `caption`, serialized as a custom control
title without renaming fields or parameters. Omitted captions preserve the normal
Tableau title. Worksheet rich-title runs accept `fontalignment`, including centered
dynamic titles; existing parameter placeholder resolution is unchanged.

```python
layout = {"type": "paramctrl", "parameter": "Timeframe",
          "caption": "Select Date Timeframe"}
editor.set_worksheet_rich_title("Sales", [
    {"text": "Sales", "fontalignment": "center", "fontsize": 14}])
```

## 2026 WW06: actual average totals, weekday origin, and diverging color

A visual-total attribute alone does not enable subtotal rows. `configure_subtotals`
now adds the selected subtotal dimensions and binds the measure's visual-total
instance consistently throughout the worksheet. Repeated calls remain idempotent.
Subsequent field-bound styles resolve the visual-total instance; `cell_formats`
preserve `data_class` and `scope` as selectors instead of emitting them as formats.
This permits decimal average totals with integer detail values.

`set_date_options(start_of_week="sunday")` controls weekday headers and calculations
without depending on the starter workbook's locale defaults. `color_style` exposes
continuous palette, center, bounds, and inclusion of totals for null-safe averages.
`pane_formats` controls matrix row geometry separately from dashboard size. MCP forwards these styles and week settings through the same
Python API.

```python
editor.set_date_options(start_of_week="sunday")
editor.configure_worksheet_style("Average", color_style={
    "field": "SUM(Sales)", "palette": "red_blue_white_diverging_10_0",
    "center": 0, "include_totals": True}, cell_formats=[{
    "field": "SUM(Sales)", "text-format": "n0.00",
    "data_class": "subtotal", "scope": "rows"}])
```

## Validation boundary

SDK regression tests verify generic serialization, field bindings, idempotence,
invalid input rejection, and MCP forwarding. They do not certify Tableau Cloud
visual equivalence or browser interactions. Case-specific Cloud images, parameter
states, and interaction acceptance belong to the case repository.

## 2019 WW32: styled labels on layered step/area marks

Layered chart `panes[].label_runs` now calls the shared rich-label builder instead
of a nonexistent editor method. Literal runs and field references retain individual
font colors, sizes, and weight, allowing rise/drop labels to follow their mark
semantics. A regression constructs a real layered chart and checks styled field
references in the resulting customized label.

Layered categorical palettes also preserve the worksheet-bound column instance's
full table-calculation context, including nested calculations and addressing child
nodes. Tableau resolves a table-calculation palette by context, so a name-only
instance can silently fall back to default colors. This correction copies only
SDK-generated bound metadata; it never reads an author workbook. Synthetic MCP
coverage verifies the palette and worksheet contexts match and are independent
XML nodes. Cloud verification remains a separate case acceptance step.

## 2019 WW30: floating navigation objects and field formats

Tableau's floating navigation buttons are direct peers under dashboard `zones`.
Nesting those objects inside a `layout-basic` container can clip them to thin lines
in Cloud. Floating navigation nodes now render at the dashboard level while
retaining their computed absolute bounds; worksheet/text siblings retain existing
container layout behavior. Target UUID validation and navigation action generation
remain unchanged.

`set_field_format(field, default_format)` sets the default Tableau format of a
physical or calculated field without renaming its registry identity. Physical
fields with only connection metadata receive an explicit datasource column, and
existing worksheet dependency copies are updated. Empty strings clear the format.
The same operation is exposed by MCP. This lets the detail dashboards use currency
formatting without touching internal datasource XML.

```python
editor.set_field_format("Sales", 'c"$"#,##0.00')
```

## 2026 WW04: parameter-driven axis titles

Dynamic axes require Tableau's expression graph rather than a literal fallback
axis-title format. `axis_style.per_field` accepts `title_parameter` and a `rows` or
`cols` scope. The SDK creates field-bound axis-title and parameter-value nodes,
connects their pins, registers their execution subgraph, and enables the required
manifest features. Repeated calls update the parameter binding for the same axis.
Synthetic MCP tests check field/sheet references, edge connectivity and idempotence;
Cloud parameter-state exports verify actual displayed Month/Quarter/Week titles.

```python
editor.configure_worksheet_style("Sales", axis_style={"per_field": [{
    "field": "Date", "scope": "cols", "title_parameter": "Timeframe"}]})
```

## 2019 WW31: explicit spatial size range

The route width and destination point size depend on both each pane's mark size
and the worksheet's quantitative size range. `size_style` now exposes `rangesize`
encodings with a resolved `field`, data-domain `min`/`max`, and independent
`min_size`/`max_size` bounds. This prevents a constant concert count from mapping
to an unintended oversized line. Numeric values or numeric strings are accepted;
strings preserve exact Tableau precision. Invalid types and non-finite sizes are
rejected. MCP uses the same interface and repeated updates replace the field's
encoding.

```python
editor.configure_worksheet_style("Routes", size_style={
    "field": "Concert Count", "min": 1, "min_size": "0.00251905",
    "max_size": 1, "type": "rangesize"})
```

WW30 navigation rendering also declares `BasicButtonObject`,
`BasicButtonObjectTextSupport`, and `NavigationAction` in the workbook manifest.
These feature declarations identify the navigation text-button capabilities.
A working navigation target also requires the correct window UUID, described below.

## 2026 WW05: gridline orientation

`gridline_style={"rows": {"line_visibility": "on"}, "cols": {
"line_visibility": "off"}}` controls horizontal and vertical gridlines separately.
The earlier global `hide_gridlines` switch could not retain only the author's
horizontal guides. Scoped line visibility, stroke color, size and pattern are
available through Python and MCP; repeat updates replace matching scope formats.

Dynamic-axis expression graphs are retained during workbook serialization. The
previous cleanup assumed obsolete schema support and removed every graph; current
2026 schemas include them. A save-and-reparse regression verifies the graph survives,
and omitted fallback titles use the selected parameter's current display alias.

WW30 also exposed a distinct navigation identity bug: Tableau's `goto-sheet`
`window-id` must reference the target dashboard's **window** UUID, not its dashboard
UUID. The two identifiers can differ. Using the dashboard UUID creates an invalid
target, leaving the Cloud button disabled and gray regardless of its color style.
Navigation rendering now resolves `windows/window[@class="dashboard"]` by target
name and requires its simple ID. A synthetic test deliberately assigns distinct
UUIDs to prove the action references the window.
