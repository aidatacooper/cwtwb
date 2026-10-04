# Case-driven SDK enhancements

## 2020 WW42-46: date domains, filter controls and independent colors

WW42's Strava calendar uses a compact year slider with the track hidden. A filter
layout node accepts boolean `show_slider=False`, emitting native `show-slider`;
omitting it preserves the default. Invalid values fail before replacing a
dashboard. The same case exposed missing dashboard dependencies for expressions
such as `YEAR(Date)`: filter dependencies now include the resolved base column
and the actual year instance, rather than looking up an expression as a column.

WW44 completes a source date domain while Year, Quarter, Month and Day instances
are on the shelves. `configure_worksheet_domain_range` now recognizes those
used date instances and Attribute dates from the same source column. Unused
fields, nondate fields and unrelated numeric aggregation remain invalid. The
public method and native base-date reference are unchanged.
The same case's complete diagnostic date table needs discrete date truncation,
not a calculated date alias: `DISCRETE(DAYTRUNC(Order Date))` preserves the native
Day-Trunc derivation with an ordinal instance. The wrapper also supports month,
quarter and year truncation, while unwrapped truncations remain continuous.
Synthetic checks cover shelves, calculation addressing and base-date completion.

WW45 colors Profit independently from its Orders and Sales table measures:

```python
editor.configure_chart("Metrics", mark_type="Square", rows=["Group"],
    measure_values=["COUNT(ID)", "SUM(Sales)", "SUM(Profit)"],
    color="Multiple Values", separate_measure_domains=True)
```

The virtual field is not added as a physical datasource column. Native color
and text bindings share `separate-domains="true"`, while existing detail,
tooltip and color bindings survive Measure Values setup. Square marks retain
their class; Automatic measure tables use Text. Each measure's palette remains
configured by the existing worksheet `color_style`. Layered pane dictionaries
accept the same option. Python, MCP and declarative run-spec forward the public
flag, and invalid types or missing measure/color bindings fail before mutation.
Compound viz-in-tooltip filters also register every member on both source and
target worksheets, including recursive calculated-field dependencies. A
synthetic two-level calculated member verifies declaration order and idempotency;
native contracts establish tooltip behavior without claiming a hover execution.

WW46 imports an opponent name from an independent match datasource.
`import_blended_field(..., "ATTR(Opponent)")` now emits Tableau's `ATTR` function
instead of invalid `ATTRIBUTE`. String measures retain nominal metadata, while
Count and CountD proxies use integer quantitative metadata. Synthetic Hyper
fixtures cover all four aggregates, native blending and packaged saves.

These enhancements have no author data in their regression fixtures. WW43's
narrow KPI layout reuses existing parameter actions and native zone visibility;
its default REST rendering does not establish mobile-browser interaction.

## 2020 WW30–41: controls, compound tooltips and native date grains

The ten articles in this batch represent WW30, WW31, WW32, WW33 and WW36–41.
Article dates remain folder dates; official challenge identities are verified
independently, including an incorrectly labelled WW33 author workbook.

WW31 requires viz-in-tooltip targets filtered by both country and year.
`configure_custom_tooltip` now accepts multiple explicit `filter_fields`, creates
matching native crossjoin groups and target action filters, and supports the
sheet option `filter_context=True` for ranking targets. Filter insertion follows
all datasource dependencies, including Parameters. Synthetic fixtures verify
both dimension identities, idempotency, context updates, MCP forwarding and
schema-valid saves without author workbooks.

WW36 requires an existing set's native membership dropdown. The declarative
dashboard node `{"type": "set_control", "field": "Selected Categories",
"worksheet": "Plot", "mode": "dropdown"}` binds the real datasource group,
adds the matching worksheet card and declares `SetMembershipControl`.
Invalid set references, worksheets and modes fail before an existing dashboard
is replaced. Synthetic tests retain explicit members and validate packaged XML.
REST parameter/filter exports do not execute set membership selection.

The county map also exposed an executed calculation failure: unsuffixed or
colliding native instances rendered Alaska/Hawaii county percentiles as 100%.
Independent Cloud diagnostic exports held the input and
formulas fixed: a local calculation instance restored all 34 county ranks;
geographic metadata and single-pane changes did not. Layered charts now accept
`table_calc_context=True` with explicit `table_calc_overrides` to declare local
instances without requiring caller-written native identifiers. Mark bindings,
label fields, worksheet styles and dashboard legends reuse those identities.
Context identities are distinct across worksheets in a workbook, so different
addressing of the same calculation cannot collide. Rebuilding a worksheet keeps
its existing context identity. A two-worksheet synthetic regression protects
the different addressing alongside dashboard composition.
Synthetic fixtures cover both normal and Measure Values encodings, idempotency,
valid saves, MCP/run-spec forwarding and invalid options before mutation.

WW38 requires a stepped sequential color scale. Worksheet `color_style` accepts
`num_steps` (or native `num-steps`) as a positive integer for custom or named
interpolated palettes. Invalid boolean, null, fractional and nonpositive values
are rejected before writing the encoding.

WW39 authors a mobile-sized default canvas and a matching custom Phone layout.
`copy_default_device_layout("Dashboard", "Phone")` copies the complete default
zone tree without changing IDs, coordinates, hidden groups or toggle buttons.
The device inherits the default canvas size; Tablet is also supported. This is
distinct from the existing automatic vertically scrolling phone layout.
Synthetic tests check geometry, shared identities, hidden state and valid saves;
desktop REST images do not establish rendering in a mobile browser.

WW41 requires continuous quarter axes, rather than discrete quarter date parts
or arbitrary exact-date ticks. `QUARTERTRUNC(Date)`, `MONTHTRUNC(Date)` and
`YEARTRUNC(Date)` bind native quantitative truncation instances and require a
date or datetime field. Synthetic chart saves cover all three grains and both
date types, and still reject generated instance names as input expressions.

The same case exposed a Cloud publication failure when a min/max label range
field was serialized as its display caption. `mark-labels-range-field` (or its
underscore spelling) now resolves a public field expression to the actual
qualified instance in both layered `mark_style` and worksheet pane styles.
Layered styles declare the required dependency even when the range field differs
from the axis. Synthetic fixtures cover both pane-style collection forms,
aggregate calculations, idempotency and unknown-field rejection.

Investigation of WW41's empty Cloud views also exposed a supported custom
parameter internal ID being misclassified as a physical datasource column.
Correcting this dependency error alone did not resolve the complete case.
Dependency
scanning now excludes qualified `[Parameters].[CustomID]` tokens rather than
assuming names start with `Parameter `. Parameter dependencies remain in the
Parameters datasource. Synthetic basic, dual-axis and layered fixtures cover
custom IDs referenced through multiple aggregate calculations.

A separate complete-workbook probe isolated explicit table-calculation
addressing: dropping overrides made the quarter view nonempty but computed the
wrong reference values. Temporal `order` expressions now retain their native
date-grain instance instead of referring to the raw date column. With the full
public builder and overrides retained, Cloud exports restored all 48 quarterly
values and per-category quarter averages. `ordering_field` resolves ordinary
dimensions to datasource columns and aggregates to calculation instances,
matching the distinct native reference forms. Eight synthetic regressions cover
six temporal grains and both ordering-field forms without author fixtures.

WW30–33 also exposed misspelled filter dictionaries being silently omitted.
Chart dispatch now requires each filter to have a nonempty `column` expression
before any builder replaces the worksheet. The regression covers standard,
dual-axis and layered APIs, retains an existing worksheet on invalid input,
and verifies a valid native filter and MCP error propagation.

WW40 exposed a meaningful order-of-operations issue: shelf sorting made the NFL
table readable but INDEX pagination selected the wrong player members on later
pages. `configure_layered_chart(..., sort_field="Member",
sort_descending="SUM(Metric)", sort_mode="computed")` emits native member
sorting before table calculation filtering, even when the member is on the row
shelf. `auto` preserves existing routing; `shelf` selects shelf sorting explicitly.
Competing sort entries for the same dimension are removed on updates.
Synthetic nested-row tests cover native ordering, pagination filters, valid
saves, repeated calls, mode changes and invalid options before mutation. MCP and
run-spec's `layered` worksheet configuration forward the same public arguments.

## 2020 WW25–29: assets, fiscal dates and independent logical tables

WW25 requires categorical image marks authored without an original workbook.
`set_shape_palette("Type", {"Crust": "inputs/crust.png"}, palette="Custom")`
embeds PNG assets and writes the native categorical shape palette. Asset names
are unambiguous and repeated calls are idempotent. Synthetic fixtures use small
generated images; the case locks the extracted author images as inputs. Its
menu-triggered set add/remove actions reuse the existing public action API.
`initialize_dashboard_filter_action("Dashboard", "Type Selection", {"Type": ["Size"]})`
initializes a native action filter tied to the existing action and its targets.
The initial members can be replaced by later action events; an ordinary fixed
Type filter would instead intersect subsequent choices and make other types
empty. Synthetic tests check the native group, target filter and action identity
together, including idempotent updates and invalid inputs before mutation.

WW26 requires an October fiscal year. `set_field_fiscal_year_start("Date", 10)`
sets native date metadata on the active datasource and existing worksheet
dependencies; later charts inherit the same property. This changes fiscal date
interpretation, not the dates themselves. Synthetic tests cover date types,
valid month boundaries, invalid inputs and existing/future chart dependencies.

WW28 has daily actual sales and monthly segment/category targets. A physical
join would multiply goals and lose goal-only periods. The optional
`relationships` argument to `set_hyper_connection` inspects real Hyper field
types and creates independent logical objects with explicit equality keys:

```python
editor.set_hyper_connection(
    "inputs/facts-and-targets.hyper",
    tables=[{"name": "Actual", "table": "Transactions"},
            {"name": "Goals", "table": "Targets"}],
    relationships=[{"left": "Actual", "right": "Goals", "keys": [
        ["Segment", "Segment"], ["Category", "Category"], ["Month", "Month"]]}],
)
```

Physical tables reside in the `Extract` schema. Repeated secondary dimension
names are qualified by logical table, for example `Month (Goals)`. Explicit
key fields and datatypes must match, and the graph must be connected before
mutation. The legacy connection path remains available when `relationships`
is omitted. Synthetic tests cover three equality predicates, atomic invalid
inputs, run-spec/MCP forwarding, and a packaged extract with multiple actual
rows per target and a target-only month. No physical join is generated.

WW27 nested customer distribution calculations and WW29 intermediate heatmap
labels reuse existing addressing, set action and native total APIs. Cloud
validation distinguishes stored states and full worksheet exports from action
contracts; it does not claim browser clicks or hover execution.

## 2020 WW15–24: dates, independent grains and native layouts

WW15 exposed missing interior weekdays in an exact-date grid.
`configure_worksheet_domain_range("Viz", ["[Date]"])` declares native
`show-full-range` for fields already in the view. It cannot invent leading or
trailing dates beyond the data domain; the case also locks a zero-filled daily
calendar derived from its original extract and checks every daily aggregate.

WW16 and WW17 require data blending, rather than joining monthly targets into
daily facts. `import_blended_field("Plan", "Targets", "SUM(Target)")` creates
a qualified aggregate proxy in the active primary source.
`configure_datasource_blend("Viz", "Targets", {"Month": "Month"}, ["SUM(Target)"])`
declares secondary dependencies and native links. Linked captions and datatypes
must match. Independent Hyper sources remain independently packaged; synthetic
tests use deliberately different fact grains. Table-calculation addressing must
still be configured for each actual worksheet orientation.

WW18 needs weighted profit margins in native subtotals.
`configure_subtotals(..., aggregation="Automatic")` preserves the calculation's
native aggregate instead of imposing a sum or average of displayed margins.
`set_measure_name_aliases("Viz", {"Margin": "Margin"})` writes aliases against
the worksheet's actual qualified measure instances, including table calculations,
so native headers do not append addressing descriptions or truncate long captions.
Expanded WW18 Cloud tables also exposed a missing native viewpoint zoom:
dashboard worksheet zones with `fit="width"` or `fit="height"` now emit
`fit-width` or `fit-height` on their dashboard window viewpoint, alongside the
layout-cache sizing. This keeps columns readable at the actual zone width.
WW19 requires date/datetime set members: `add_set` accepts ISO values or naive
Python date objects and emits native temporal literals. Invalid members fail
before mutation.

WW20 and WW22 exposed set add/remove action serialization and invalid ATTR set
tooltip instances. Add/remove modes now emit native membership elements and
required feature declarations; assign mode retains its existing contract.
Set tooltips resolve native In/Out instances. These are artifact contracts;
REST exports do not execute browser clicks.

WW21 combines dynamic Top-N and Bottom-N sets with
`add_combined_set("Both", ["Top", "Bottom"])`, preserving native membership.
Bottom-N now selects the bottom end of a descending ranking.
`enable_automatic_phone_layout("Dashboard", worksheet_height=280)` derives
the automatic Phone layout from the default dashboard's leaf objects, preserves
their IDs and gives sheets a fixed height in a vertical scrolling container.
Phone behavior is checked in the artifact; desktop REST rendering alone does
not prove mobile browser rendering.

WW23 needs numeric year palette buckets and axis-unit bars aligned left.
Temporal date-part palettes retain numeric members rather than quoted physical
dates. Layered mark sizing accepts native left/right alignment. Reference lines
can also bind the virtual Multiple Values axis without a physical fake column.
WW21 Cloud publishing also rejected quoted year filter members. Discrete
date-part filters and pane palettes now use numeric members consistently; six
synthetic date-part cases cover years, quarters, months, days, weeks and weekdays.
All new authoring APIs have public SDK and MCP entry points and capability entries;
worksheet blends and automatic Phone layouts are also available in run specs.

## 2020 WW07: overlaid measures and virtual palettes

The parameter-driven forecast view needs Sales and Forecast bars to overlap,
with a consistent blue/teal Measure Names palette. Layered panes previously
forced `breakdown="auto"` and attempted to resolve Measure Names as a physical
colour field. Pane dictionaries now accept `breakdown` (`auto`, `on`, `off`).
Virtual palettes resolve each measure expression to its actual quoted, fully
qualified Tableau instance without inventing a physical Measure Names column.
Cloud comparison also exposed identical widths hiding the underlying Sales bar.
Layered panes accept `size="Measure Names"` as a native virtual binding, allowing
Tableau to assign different widths to overlaid measures. A synthetic regression
checks that no physical Measure Names field is introduced.

## 2020 WW09: categorical order-event shapes

Cloud publishing exposed a qualified-name parse error in nested order-date
calculations. Table calculation overrides now resolve `level_address` captions
to qualified datasource column references, matching `field` and `level_break`.
Synthetic tests cover ordinary and layered charts without private field access.
Repeated ordinary axis expressions also receive distinct pane indices, keeping
both timeline layers and both KPI panes visible and independently exportable.
Cloud rendering also requires categorical shape encodings to use `type="shape"`,
not the color palette encoding type. The ordinal/null shape regression checks
this native type so triangles and diamonds do not silently fall back to circles.

The reorder timeline distinguishes a customer's initial order from later
orders using a triangle/diamond shape palette and colours zero/one/null event
categories. Layered panes now support `shape` and `shape_map`, and numeric
palette serialization preserves Tableau's `%null%` category. Colour and shape
palettes retain the real calculation instance and addressing identity.

## 2020 WW10: independent spatial sources and filtered tooltip sheets

The intermediate buffer map and parameter-driven hotel map use different
extracted datasets. `add_hyper_datasource(name, filepath)` adds and activates an
independent source; `select_datasource(name)` selects by internal name or unique
caption without replacing prior worksheet references. Packaging includes all
source extracts. A failed add leaves the current source unchanged.

`configure_custom_tooltip` accepts a sheet run such as
`{"sheet": {"name": "Details", "filter_fields": ["Hotel"], "maxwidth": 300, "maxheight": 300}}`.
This authors the native Sheet token, hidden sheet-link group and target action
filter. Explicit filter fields prevent accidental unfiltered tooltip lists.
Source and target must use the same datasource. One explicit filter field is
currently supported; compound scopes are rejected. This is an artifact contract;
REST worksheet exports verify target data, without claiming hover execution.

The distance colour and size legends can now use `reverse=True`, matching the
native continuous palette direction without case-specific transformed metrics.

## 2020 WW10 and WW12: native collapsible containers

`add_dashboard_toggle_button(dashboard_name, target_worksheets, initially_hidden=True,
position={"x": 12, "y": 50, "w": 330, "h": 30})` creates a native button bound to
the dedicated shared layout-flow container and dashboard window identity.
`caption_shown` and `caption_hidden` label its two states. This preserves the
native show/hide event and hidden-by-user state instead of substituting a
parameter action. Targets must share a non-root container and position uses
dashboard pixels. The SDK does not claim that REST image export clicks buttons.

## 2020 WW12: bars sized in axis units

Mixing a set action with a filter action exposed duplicate `[Action1]` identities.
All action kinds now participate in allocation, and single-select set actions
declare `GroupActionSingleSelect`. A public API probe published without the set
action but failed with the duplicated identities even without the toggle button;
the final case capture validates the corrected combined workbook.

Daily, weekly and monthly selected-period bars need native mark scaling and
axis-unit width settings. Layered pane `mark_sizing` accepts the validated native
keys `mark-sizing-setting`, `mark-alignment`, `use-custom-mark-size` (boolean),
and `custom-mark-size-in-axis-units` (positive finite number). Underscore spellings
are normalized. Existing `mark_sizing_off` remains supported; the two settings
cannot be combined. Spatial map layers also display explicitly requested labels
instead of unconditionally suppressing them (WW10 buffer counts).

All additions have synthetic regressions in
`tests/test_independent_sources_tooltips_and_controls.py`, covering independent
source references and packaging, invalid-input rejection, tooltip field scopes,
native button targets, sizing, categorical nulls and virtual measure palettes.
Public authoring operations are also exposed through MCP and the capability
registry; layered pane settings travel through the existing dictionary API.

## 2020 WW02: parameter control title visibility

The compact date-period dropdown declares `show_title=False`, but parameter
zones previously ignored this shared layout option. Parameter controls now emit
the native `show-title="false"` attribute. Explicit `True` and the default retain
normal titles and the parameter identity is preserved. A synthetic MCP/layout
test covers all three settings and workbook save/load.

## 2020 WW03: native statistical trend lines

The order-time views encode distinct order counts with circles by hour and day
or weekday, overlay earliest-to-latest hour ranges with Gantt marks, and add
native linear fits. A
straight line drawn as marks would not preserve Tableau's model semantics.
Layered pane dictionaries now accept `trendline` and `trendline_style` for native
linear, polynomial, log, exponential and power fits, confidence bands, intercept
and color partitioning, excluded factor fields, analytics and tooltips. The
builder resolves excluded fields through the registry and emits the trendline
before pane tooltip/label/style nodes. Python and MCP forward the same pane
dictionary. Synthetic regressions cover native XML, invalid options and save/load.

WW04's selector and KPI panes also exposed a shared serialization error: panes
whose text bindings were virtual or supplemental emitted encodings after styles.
The builder now inserts those encodings immediately after the mark, retaining
Tableau's required ordering and the customized label formatting in Cloud.

WW03 also exposed table-scoped LOD formulas such as `{MAX([Value])}` being
misclassified as aggregate expressions. All LOD braces now hide their inner
aggregates from outer derivation inference, including unscoped forms. Row-level
boolean comparisons retain `None`, while aggregates outside the LOD remain `User`.
Synthetic tests include direct and referenced LOD values and a filtered view.

```python
editor.configure_layered_chart("Scatter", columns=["SUM(Value)"], rows=["Ratio"],
    panes=[{"axis": "Ratio", "mark_type": "Circle", "detail": "Item",
            "trendline": {"fit": "linear", "enable_instant_analytics": True},
            "trendline_style": {"line-pattern-only": "dotted", "stroke-size": "1"}}])
```

## 2020 WW01: independent measure panes and custom sort headers

The single-click sorting challenge places sales bars, a text column, and profit
ratio bars beside one another in one worksheet. Layered charts previously folded
every secondary axis into an overlay. `configure_layered_chart(fold_axes=False)`
now keeps the measure axes independent while retaining pane-specific marks,
labels, styles, and axis visibility. The default remains the existing overlay.

The author's separate clickable header replaces Tableau's built-in sorting
controls. `configure_worksheet_style(hide_sort_controls=True)` emits the native
view control; `False` restores it, and the default `None` preserves current state.
Both options are available through Python and MCP. Synthetic tests cover
independent panes, existing folding, hide-control idempotence, explicit removal,
option validation, and workbook save/load without author data.

Parameter actions also resolve the virtual `Measure Names` source directly to
`[:Measure Names]`, avoiding an invented physical column when header marks choose
the sort metric. Tests cover both the display name and virtual reference spelling.

```python
editor.configure_layered_chart(
    "Comparison", rows=["Item"], columns=["SUM(Value)", "SUM(Ratio)"],
    axis_shelf="columns", fold_axes=False, hide_axes=True,
    panes=[{"axis": "SUM(Value)", "mark_type": "Bar"},
           {"axis": "SUM(Ratio)", "mark_type": "Text"}],
)
editor.configure_worksheet_style("Comparison", hide_sort_controls=True)
```

## Five additional cases: 2019 WW46–48 and 2026 WW07/09

These enhancements were discovered by independent empty-workbook builds, then
checked against real Tableau Cloud image/CSV exports in the companion case lab.
They remain generic APIs and contain no author workbook or case-specific data.

- **WW46 manufacturer groups:** `add_group(default_value=None)` preserves
  ungrouped source values. Categorical bins now escape literal quotes with
  backslashes rather than SQL doubled quotes, and escape `#`, `%` and backslashes.
  The incorrect encoding created 327 manufacturer groups instead of 183 in Cloud;
  tests use synthetic quoted/pattern-like strings, without the author data.
- **WW48 threshold bars:** `configure_layered_chart(sort_descending=...)` exposes
  shared sorting through the facade, dispatcher and MCP. Numeric categorical
  palettes emit numeric buckets, rather than quoted strings that Cloud ignores.
  Structured table-calculation `order` addresses both grouping dimensions so the
  selected/combined state counts span the full view.
- **WW07 paired TC/LOD bars:** shelf sorts target the inner nominal dimension,
  consistent with Tableau's innermost sort flag, preserving the outer region
  partitions while sorting categories by sales.
- **WW09 parallel coordinates:** layered pane dictionaries accept `path` and
  `color_extra` bindings. Repeated `Multiple Values` axes retain their distinct
  pane indices and fold classes; explicit `measure_values` lists retain metric
  order through the Measure Names dictionary. Table-calculation overrides use
  the same validated ordered/nested addressing as ordinary charts. Virtual
  `Measure Names` labels and worksheet styles bypass physical field registration.
  Explicit `ATTR` expressions preserve nominal/ordinal domains, keeping textual
  tooltips and labels correctly typed.

```python
editor.configure_layered_chart(
    "Comparison", columns=["Measure Names"],
    rows=["Multiple Values", "Multiple Values"],
    panes=[
        {"axis": "Multiple Values", "mark_type": "Line", "detail": "Item",
         "color": "Selected", "color_extra": ["ATTR(Venue)"],
         "measure_values": ["Metric A", "Metric B"]},
        {"axis": "Multiple Values", "mark_type": "Line", "path": "Item",
         "label": "Measure Names"},
    ],
    table_calc_overrides={"Metric A": [{"ordering_type": "Field", "order": ["Item", "Selected"]}]},
    synchronized=True, hide_axes=True,
)
editor.configure_worksheet_style("Comparison", label_formats=[
    {"field": "Measure Names", "display": "false"}])
```

**WW47 boundary:** deterministic order-ID jitter is a case-level reproducibility
choice. `RANDOM()` remains excluded from the official function catalog: Tableau's
[support article](https://help.salesforce.com/s/articleView?id=001473019&language=en_US&type=1)
identifies it as unofficial and potentially deprecated. REST captures and static
action contracts do not establish browser clicks, hover or live Explain Data use.

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


## 2019 WW49?51 and 2026 WW08/11: geography, actions and dashboard contracts

WW49 requires generated latitude/longitude/geometry in layered panes, compound
geographic detail, explicit initial set members, set-specific table calculation
addressing, and single-selection assignment with retained selection on clear.
`add_set(..., members=[...])` validates and escapes members; layered charts expose
`geometry`, `detail_extra`, `filters`, and `sort_field`. Hidden exclusions use a
binary set difference and remain outside ordinary filter slices.

Cloud exports exposed an inherited geocoding country in the empty template.
Generated US maps must explicitly establish their lookup context. Fields whose
source names do not identify geography can receive an explicit geographic role;
existing worksheet dependency copies are updated as well.

```python
editor.set_geocoding_context(country="United States", state=None)
editor.set_field_geographic_role("Region Name", "state")
```

WW50 needs ordinal date cohort shelves and an explicit sort dimension rather than
an implicit innermost dimension. Basic, text, dual-axis and layered chart APIs
accept `sort_field`. WW51 requires one filter source targeting multiple sheets and
hover highlighting with multiple source and target sheets. Dashboard actions now
accept `source_sheets` and `target_sheets`, validate dashboard membership, and
serialize excluded sheets separately for each side. Continuous color styles can
use `colors=["#f1f1f1", "#83514a"]`; map styles expose named layer visibility.
`EXACTDATE(...)` is preserved through field normalization without registering a
spurious field bearing the whole expression as its name.

WW08 requires genuine dynamic zone visibility driven by a boolean calculation.
A layout node may specify `visibility={"field": "Panel Visible",
"initially_visible": False}`. The SDK creates field/zone datagraph bindings and
manifest flags. Filter controls expose relevant values and `show_all=False`;
`link_worksheet_filters(field, worksheet_names)` shares an existing categorical
filter across selected sheets. Dashboard rich text may contain parameter runs.
Measure Values text charts preserve the supplied measure order, and rich labels
support virtual `Multiple Values` and `Measure Names` fields with required text
encodings. These capabilities allow KPI values and captions in one chart.

WW11 requires native rounded container corners. Layout `corner_radius` accepts
finite nonnegative values and enables the corresponding workbook feature. The
same layout graph supports inner and outer containers with independent padding.

Synthetic regressions cover generated geography, geocoding context, hidden set
exclusions, set calculation addressing, scope validation for multi-sheet actions,
virtual KPI labels, dynamic visibility graphs, shared filters, parameter text,
rounded corners, and exact date normalization. Cloud images and actual CSV scope
are recorded by the case repository separately; artifact tests do not claim
browser interaction execution.


WW50 also requires the layered shelf grammar to distinguish a discrete dimension
crossing continuous axes (`dimension * (axis1 + axis2)`) from continuous axis
addition and hierarchical discrete dimensions (`dimension1 / dimension2`).
WW51 Cloud diagnostics isolated empty queries to redundantly encoding a temporal
shelf field as a tooltip mark. Chart builders now retain the formatted tooltip
reference while omitting a duplicate encoding for an expression already present
on rows or columns. A synthetic month/year regression covers that distinction.


## 2020 WW11: grouped row banding

The below-average workbook groups customer rows by region and state. Its native
banding level and size must follow those groups rather than alternate individual
customer rows. `configure_worksheet_style(..., table_formats=[...])` accepts
`attr`, `value`, and optional `scope="rows"` or `"cols"`. For example:

```python
editor.configure_worksheet_style("Customers", table_formats=[
    {"attr": "band-level", "value": 3, "scope": "rows"},
    {"attr": "band-size", "value": 1, "scope": "rows"},
])
```

Formats are replaced by attribute and scope, preserving other table formats,
including background color. Underscores in attribute names normalize to hyphens.
Synthetic tests cover independent row/column scopes, repeated updates, preserved
backgrounds, invalid inputs and Python/MCP forwarding. Rich label runs retain the
existing native `fontsize` spelling; case label dictionaries using `font_size`
should correct their key instead of adding a case-specific SDK interface.


## 2020 WW10: compact color and size legends

The hotel distance view needs both a color scale and a size scale. The original
SDK could create a color legend, but not its native size counterpart. A wide
legend caption also covered hotel labels in the replication. Dashboard layout
now accepts `type="size"` alongside `type="color"`, with a short custom `caption`
and optional positive integer `pane_index` to bind the appropriate chart pane:

```python
{"type": "size", "worksheet": "Hotels", "field": "SUM(Distance)",
 "caption": "Distance (m)", "pane_index": 1}
```

Both legends use the worksheet encoding reference and retain normal floating
layout positioning and title visibility. Cases can place narrow controls in a
clear dashboard corner instead of covering marks. Synthetic tests cover both
native zone types, shared field references, custom captions, pane bindings, and
invalid pane identities. The case repository checks the actual Cloud rendering
and metric scope separately.


The WW10 Cloud review exposed clipped size-scale entries with the default legend
font. `configure_worksheet_style("Hotels", legend_style={"font-size": 8})` now
sets native legend formats under the worksheet table style. Attribute names
normalize underscores, updates replace matching attributes, and unrelated
legend formats and table backgrounds remain intact. Python and MCP expose the
same validated dictionary. Synthetic regressions cover font updates, preserved
formatting, invalid payloads and MCP forwarding.

The native legend custom-caption metadata can be ignored by Tableau Cloud, even
when present in the workbook. It does not guarantee the requested caption will
render. For a reliable compact heading, use `show_title=False` on the legend and
a separate text layout node; retain enough legend height for the full scale.


A further WW10 capture showed that increasing the enclosing legend height did
not increase its visible body: a native control flow container nested inside
`layout-basic` was constrained during Cloud layout. Independently positioned
container children of a floating parent now serialize as peers directly under
`dashboard/zones`, matching native floating container structure. Their controls
remain children of the flow container and retain configured geometry and fixed
sizes. The public layout API is unchanged. Synthetic tests verify elevation only
for absolute containers under floating parents, preservation of nested controls,
and unchanged nesting for ordinary tiled or nonabsolute flow containers.

Native show/hide buttons accept the elevated dedicated flow container while
continuing to reject the dashboard tiled root and incomplete target sheet lists.
