# Map and Web Page authoring

These public Python and MCP capabilities are available since `0.29.0a3`.
Install the alpha explicitly:

```bash
python -m pip install --upgrade cwtwb==0.29.0a4
```

## Drive Time map tool

Call this after configuring a map worksheet:

```python
editor.configure_map_selection("Map", tool="drive_time", show_toolbar=True)
```

The setting updates the worksheet and existing dashboard viewpoints. Dashboards
created later inherit it. Only `drive_time` is currently supported. It requires
a supporting Tableau client and configures its tool; the SDK does not calculate
travel-time areas or replace the client's routing services.

## Independent sources in native map layers

Create sources and calculated fields with `add_hyper_datasource`,
`select_datasource` and `add_calculated_field` before configuring the map.
Assuming the active source contains `Building Location`, and an existing source
captioned `Pump Locations` contains `Pump Location`, `ID` and `name`:

```python
editor.configure_chart(
    "Map",
    mark_type="Map",
    geographic_field="Building Location",
    map_layer_mode="native",
    map_layers=[
        {"geometry": "Building Location", "mark_type": "Circle", "detail": "ID"},
        {
            "datasource": "Pump Locations",
            "geometry": "Pump Location",
            "mark_type": "Shape",
            "detail": "ID",
            "tooltip": ["name"],
        },
    ],
)
```

A layer accepts an existing datasource name or unique caption. Its geometry,
details, tooltip fields and color expressions resolve against that source.
No join or blend is introduced. Top-level fields and filters still use the
active primary source. Per-layer datasource selection requires native mode.

## Web Page layout and action routing

For an existing `Selector` worksheet with a link field:

```python
editor.add_dashboard(
    "Portal",
    layout={
        "type": "container",
        "children": [
            {"type": "worksheet", "name": "Selector"},
            {"type": "web", "name": "Preview", "url": "https://example.org"},
        ],
    },
)
editor.add_dashboard_action(
    "Portal",
    action_type="url",
    source_sheet="Selector",
    url="<[Viz Link]>",
    target_web_zone="Preview",
)
```

Use a nonempty HTTP(S) initial URL without credentials or whitespace. Standard
layout sizes, floating bounds and zone styles also apply to Web Page nodes.
The target name must resolve to exactly one Web Page node on the source
dashboard. Invalid or ambiguous targets fail before action mutation.
Omit `target_web_zone` to keep the existing default URL destination.

The SDK writes `specific-zone` routing and its `SpecificWebTargetsForActions`
manifest declaration. Do not hardcode the generated zone ID. MCP exposes the
same option through `add_dashboard_action`; MCP layout workflows can supply
the same nodes in a generated layout JSON file.

## Validation boundary

Synthetic tests cover XML, per-source references, public API/MCP forwarding,
invalid inputs and saved-workbook schemas. Three feature workbooks and 50
rebuilt historical cases loaded in Tableau Desktop 2026.2.
Actual Drive Time gestures, story transitions and embedded-page navigation
have not completed live acceptance. Remote pages may restrict embedding.
Validate the required interactions in the intended Tableau environment.
