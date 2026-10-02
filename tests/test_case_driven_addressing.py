"""Regression tests for independent WW34 addressing and WW06 button actions."""
from pathlib import Path
from urllib.parse import quote
import pytest
from cwtwb import TWBEditor
from cwtwb.mcp import tools_workbook

@pytest.fixture
def editor():
    return TWBEditor(Path(__file__).parents[1] / "src/cwtwb/references/superstore.twb")

@pytest.mark.parametrize("shelf", ["rows", "columns"])
def test_dual_axis_crosses_leading_dimension_and_sorts_rank(editor, shelf):
    editor.add_calculated_field("Rank", "INDEX()", datatype="integer", field_type="ordinal", table_calc="Rows")
    editor.add_calculated_field("Rank Label", "STR([Rank])", datatype="string", table_calc="Rows")
    editor.add_worksheet("Ranked")
    measures = ["Region", "SUM(Sales)", "SUM(Profit)"]
    kwargs = {shelf: measures, "columns" if shelf == "rows" else "rows": ["Rank"]}
    editor.configure_dual_axis("Ranked", dual_axis_shelf=shelf, label_2="Rank Label", **kwargs,
        table_calc_overrides={
            "Rank": [{"ordering_type": "Field", "level_break": "Category", "order": ["Region", "Category"], "sort": {"direction": "DESC", "using": "SUM(Sales)"}}],
            "Rank Label": [{"ordering_type": "Columns"}, {"field": "Rank", "ordering_type": "Field", "order": ["Category"], "sort": {"direction": "DESC", "using": "SUM(Sales)"}}],
        })
    ws = editor._find_worksheet("Ranked")
    assert " * (" in ws.find("table/rows" if shelf == "rows" else "table/cols").text
    rank = editor.field_registry.parse_expression("Rank")
    tc = ws.find(f".//column-instance[@name='{rank.instance_name}']/table-calc")
    assert tc.get("level-break").endswith("." + editor.field_registry.parse_expression("Category").column_local_name)
    assert [node.get("field").split("].")[-1] for node in tc.findall("order")] == [editor.field_registry.parse_expression(field).column_local_name for field in ["Region", "Category"]]
    assert tc.find("sort").get("using").endswith("." + editor.field_registry.parse_expression("SUM(Sales)").instance_name)
    label = editor.field_registry.parse_expression("Rank Label")
    nested = ws.find(f".//column-instance[@name='{label.instance_name}']/table-calc[@field]")
    assert nested.get("field").endswith("." + rank.column_local_name)


def test_mcp_dual_axis_accepts_overrides(editor, monkeypatch):
    editor.add_calculated_field("Rank", "INDEX()", datatype="integer", table_calc="Rows")
    editor.add_worksheet("Ranked")
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_dual_axis("Ranked", columns=["SUM(Sales)", "SUM(Profit)"], rows=["Rank"], dual_axis_shelf="columns", table_calc_overrides={"Rank": [{"ordering_type": "Columns"}]})
    rank = editor.field_registry.parse_expression("Rank")
    assert editor._find_worksheet("Ranked").find(f".//column-instance[@name='{rank.instance_name}']/table-calc").get("ordering-type") == "Columns"


def test_mapped_filter_deselects_button_and_is_exposed_by_mcp(editor, monkeypatch):
    for name, formula in [("Always False", "FALSE"), ("Always True", "TRUE")]:
        editor.add_calculated_field(name, formula, datatype="boolean", role="dimension")
    editor.add_worksheet("Apply Button")
    editor.configure_chart("Apply Button", mark_type="Square", detail="Always False")
    editor.add_dashboard("Dashboard", worksheet_names=["Apply Button"])
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.add_dashboard_action("Dashboard", "filter", "Apply Button", "Apply Button", field_mappings={"Always False": "Always True"})
    action = editor.root.find("actions/action")
    ds = editor._datasource.get("name")
    source = editor.field_registry.parse_expression("Always False").column_local_name
    target = editor.field_registry.parse_expression("Always True").column_local_name
    assert action.find("link").get("expression") == f"tsl:Apply%20Button?{quote(f'[{ds}]')}.{quote(target)}~s0=<[{ds}].{source}~na>"
    assert [(param.get("name"), param.get("value")) for param in action.findall("command/param")] == [("target", "Apply Button")]

@pytest.mark.parametrize("extra", [{"fields": ["Region"], "field_mappings": {"Region": "Category"}}, {"field_mappings": {}}, {"field_mappings": {"": "Category"}}])
def test_invalid_mapping_rejected_before_mutation(editor, extra):
    editor.add_worksheet("Button")
    editor.add_dashboard("Dashboard", worksheet_names=["Button"])
    with pytest.raises(ValueError):
        editor.add_dashboard_action("Dashboard", "filter", "Button", "Button", **extra)
    assert editor.root.find("actions") is None


def test_independent_axis_and_dark_map_settings(editor, monkeypatch):
    editor.add_worksheet("Axis")
    editor.configure_chart("Axis", mark_type="Line", rows=["SUM(Sales)"], columns=["MONTH(Order Date)"])
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_worksheet_style("Axis", axis_style={"encodings": [{"field": "SUM(Sales)", "scope": "rows", "class": "0", "range_type": "independent", "domain_expand": False}]}, map_style={"map_style": "dark", "washout": 0})
    rule = editor._find_worksheet("Axis").find("table/style/style-rule[@element='axis']")
    encoding = rule.find("encoding[@range-type='independent']")
    assert encoding.get("domain-expand") == "false"
    assert encoding.get("field").endswith("." + editor.field_registry.parse_expression("SUM(Sales)").instance_name)
    map_rule = editor._find_worksheet("Axis").find("table/style/style-rule[@element='map']")
    assert map_rule.find("format[@attr='map-style']").get("value") == "dark"


def test_subtotals_emit_enabled_dimensions_and_bound_visual_totals(editor):
    editor.add_worksheet("Average")
    editor.configure_chart("Average", mark_type="Text", rows=["Category", "Sub-Category"], label="SUM(Sales)")
    for _ in range(2):
        editor.configure_subtotals("Average", measure_fields=["Sales"], subtotal_fields=["Category", "Sub-Category"], aggregation="Average")
    table = editor._find_worksheet("Average").find("table")
    subtotal_fields = [node.text for node in table.findall("subtotals/column")]
    assert len(subtotal_fields) == len(set(subtotal_fields)) == 2
    instance = table.find("view/datasource-dependencies/column-instance[@visual-totals='Avg']")
    assert ":vtavg:" in instance.get("name")
    label = table.find(".//encodings/text")
    assert label.get("column").endswith("." + instance.get("name"))


def test_dual_axis_palette_has_datasource_local_binding(editor):
    editor.add_worksheet("Palette")
    editor.configure_dual_axis("Palette", columns=["SUM(Sales)", "SUM(Profit)"], rows=["Category"], dual_axis_shelf="columns", color_1="Region", color_map_1={"East": "#123456", "West": "#654321"})
    ci = editor.field_registry.parse_expression("Region")
    encoding = editor._datasource.find(f"style/style-rule/encoding[@field='{ci.instance_name}']")
    assert encoding is not None
    assert encoding.find("map/bucket").text == '"East"'
    assert editor._datasource.find(f"column-instance[@name='{ci.instance_name}']") is not None


def test_subtotal_cell_formats_do_not_leak_into_detail(editor):
    editor.add_worksheet("Average")
    editor.configure_chart("Average", mark_type="Text", rows=["Category"], label="SUM(Sales)")
    editor.configure_subtotals("Average", measure_fields=["Sales"], subtotal_fields=["Category"], aggregation="Average")
    editor.configure_worksheet_style("Average", cell_formats=[{"field": "SUM(Sales)", "text-format": "n0.00", "data-class": "subtotal", "scope": "rows"}], color_style={"field": "SUM(Sales)", "palette": "red_blue_white_diverging_10_0", "center": 0, "include_totals": True})
    table = editor._find_worksheet("Average").find("table")
    fmt = table.find("style/style-rule[@element='cell']/format[@attr='text-format']")
    assert fmt.get("data-class") == "subtotal"
    assert fmt.get("scope") == "rows"
    assert ":vtavg:" in fmt.get("field")
    assert table.find("style/style-rule[@element='cell']/format[@attr='data-class']") is None
    encoding = table.find("style/style-rule[@element='mark']/encoding")
    assert ":vtavg:" in encoding.get("field")
    assert encoding.get("include-totals") == "true"


def test_column_dual_axes_use_one_shared_class(editor):
    editor.add_worksheet("Overlay")
    editor.configure_dual_axis("Overlay", columns=["Region", "SUM(Sales)", "SUM(Profit)"], rows=["Category"], dual_axis_shelf="columns", synchronized=True)
    encodings = editor._find_worksheet("Overlay").findall("table/style/style-rule[@element='axis']/encoding")
    assert [node.get("class") for node in encodings] == ["0", "0"]
    assert encodings[0].get("fold") is None
    assert encodings[1].get("fold") == "true"


def test_date_start_of_week_validates_and_replaces(editor):
    editor.set_date_options(start_of_week="sunday")
    editor.set_date_options(start_of_week="monday")
    options = editor._datasource.findall("date-options")
    assert len(options) == 1
    assert options[0].get("start-of-week") == "monday"
    with pytest.raises(ValueError):
        editor.set_date_options(start_of_week="nonday")


def test_pane_formats_mcp_forwarding_and_selectors(editor, monkeypatch):
    editor.add_worksheet("Pane")
    editor.configure_chart("Pane", rows=["Category"], label="SUM(Sales)")
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_worksheet_style("Pane", pane_formats=[{"height": 25, "scope": "rows", "data_class": "subtotal"}])
    node = editor._find_worksheet("Pane").find("table/style/style-rule[@element='pane']/format[@attr='height']")
    assert node.get("value") == "25"
    assert node.get("scope") == "rows"
    assert node.get("data-class") == "subtotal"
    with pytest.raises(ValueError):
        editor.configure_worksheet_style("Pane", pane_formats=["bad"])


@pytest.mark.parametrize("settings", [{"map_style": "invalid"}, {"washout": -1}, {"washout": 101}, {"unexpected": 0}])
def test_invalid_map_styles_rejected(editor, settings):
    editor.add_worksheet("Map")
    editor.configure_chart("Map", rows=["Category"], label="SUM(Sales)")
    with pytest.raises(ValueError):
        editor.configure_worksheet_style("Map", map_style=settings)


@pytest.mark.parametrize("settings", [{"palette": "test"}, {"field": "Sales"}, {"field": "Sales", "palette": "test", "unexpected": 0}])
def test_invalid_color_styles_rejected(editor, settings):
    editor.add_worksheet("Colors")
    editor.configure_chart("Colors", rows=["Category"], label="SUM(Sales)")
    with pytest.raises(ValueError):
        editor.configure_worksheet_style("Colors", color_style=settings)


def test_width_fit_and_legend_display(editor):
    editor.add_worksheet("Sheet")
    editor.configure_chart("Sheet", rows=["Category"], label="SUM(Sales)", color="Region")
    editor.add_dashboard("Sized", width=500, height=300, layout={"type": "container", "direction": "vertical", "children": [{"type": "worksheet", "name": "Sheet", "fit": "width"}, {"type": "color", "worksheet": "Sheet", "field": "Region", "show_title": False, "mode": "horizontal"}]})
    dashboard = editor.root.find("dashboards/dashboard[@name='Sized']")
    zone = dashboard.find(".//zone[@name='Sheet']/layout-cache")
    assert zone.get("type-h") == "cell"
    assert zone.get("type-w") == "scalable"
    legend = dashboard.find(".//zone[@type-v2='color']")
    assert legend.get("show-title") == "false"
    assert legend.get("leg-item-layout") == "horizontal"



def test_control_caption_preserves_parameter_binding_and_default(editor):
    editor.add_parameter("Timeframe", "string", "Months")
    editor.add_worksheet("Sheet")
    editor.configure_chart("Sheet", rows=["Category"], label="SUM(Sales)")
    editor.add_dashboard("Controls", layout={"type": "container", "children": [{"type": "paramctrl", "parameter": "Timeframe", "caption": "Select Date Timeframe"}, {"type": "paramctrl", "parameter": "Timeframe"}, {"type": "filter", "worksheet": "Sheet", "field": "Category", "caption": "Choose Categories"}]})
    zones = editor.root.findall("dashboards/dashboard[@name='Controls']/.//zone[@type-v2='paramctrl']")
    assert zones[0].findtext("formatted-text/run") == "Select Date Timeframe"
    assert zones[0].get("custom-title") == "true"
    assert zones[0].get("param") == zones[1].get("param")
    assert zones[1].find("formatted-text") is None
    assert editor.root.findtext("dashboards/dashboard[@name='Controls']/.//zone[@type-v2='filter']/formatted-text/run") == "Choose Categories"


def test_rich_title_preserves_alignment_and_dynamic_reference(editor):
    editor.add_worksheet("Title")
    editor.set_worksheet_rich_title("Title", [{"text": "Sales", "fontalignment": "center", "fontsize": 14}])
    run = editor._find_worksheet("Title").find("layout-options/title/formatted-text/run")
    assert run.get("fontalignment") == "center"


def test_layered_chart_builds_rich_labels_with_resolved_fields(editor):
    editor.add_worksheet("Layers")
    editor.configure_layered_chart("Layers", columns=["Category"], rows=["SUM(Sales)"], panes=[{"mark_type": "Area", "axis": "SUM(Sales)", "label": "SUM(Sales)", "label_runs": [{"text": "Sales: ", "bold": True}, {"field": "SUM(Sales)", "fontcolor": "#123456"}]}])
    runs = editor._find_worksheet("Layers").findall("table/panes/pane/customized-label/formatted-text/run")
    assert runs[0].get("bold") == "true"
    assert "Sales:" in runs[0].text
    assert editor.field_registry.parse_expression("SUM(Sales)").instance_name in runs[1].text
    assert runs[1].get("fontcolor") == "#123456"


def test_numeric_palette_buckets_remain_numeric(editor):
    editor.add_calculated_field("Number Bucket", "1", datatype="integer", role="dimension")
    editor.set_datasource_color_palette("Number Bucket", {1: "#123456"})
    ci = editor.field_registry.parse_expression("Number Bucket")
    bucket = editor._datasource.find(f"style/style-rule/encoding[@field='{ci.instance_name}']/map/bucket")
    assert bucket.text == "1"


def test_layered_palette_preserves_nested_table_calc_context_through_mcp(editor, monkeypatch):
    editor.add_calculated_field("Running", "RUNNING_SUM(SUM([Sales]))", datatype="real", table_calc="Rows")
    editor.add_calculated_field("Band", "IF [Running] > 10 THEN 'high' ELSE 'low' END", datatype="string", table_calc="Rows")
    editor.add_worksheet("Palette Context")
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_layered_chart("Palette Context", columns=["Category"], rows=["SUM(Sales)"], panes=[{"axis": "SUM(Sales)", "mark_type": "Area", "color": "Band", "color_map": {"high": "#123456", "low": "#abcdef"}}], table_calc_overrides={"Band": [{"ordering_type": "Columns"}, {"field": "Running", "ordering_type": "Rows"}]})
    ci = editor.field_registry.parse_expression("Band")
    palette = editor._datasource.find(f"column-instance[@name='{ci.instance_name}']")
    bound = editor._find_worksheet("Palette Context").find(f"table/view/datasource-dependencies/column-instance[@name='{ci.instance_name}']")
    assert [dict(n.attrib) for n in palette.findall("table-calc")] == [dict(n.attrib) for n in bound.findall("table-calc")]
    assert len(palette.findall("table-calc")) == 2
    assert palette.findall("table-calc")[1].get("field").endswith(editor.field_registry.parse_expression("Running").column_local_name)
    assert palette.findall("table-calc")[0] is not bound.findall("table-calc")[0]


def test_floating_navigation_is_a_dashboard_object_peer_with_exact_bounds(editor):
    editor.add_dashboard("Target")
    bounds = {"x": 71000, "y": 1000, "w": 27000, "h": 9000}
    editor.add_dashboard("Origin", width=600, height=600, layout={"type": "container", "direction": "floating", "children": [{"type": "navigation_button", "target_dashboard": "Target", "caption": "Return", "absolute": bounds}, {"type": "text", "text": "Heading", "absolute": {"x": 0, "y": 0, "w": 50000, "h": 5000}}]})
    zones = editor.root.find("dashboards/dashboard[@name='Origin']/zones")
    button_zone = zones.find("zone[@type='dashboard-object']")
    assert button_zone is not None
    assert {key: int(button_zone.get(key)) for key in bounds} == bounds
    assert button_zone.findtext("button/button-visual-state/caption") == "Return"
    assert zones.find("zone[@type-v2='layout-basic']/zone[@type-v2='text']") is not None
    assert zones.find("zone[@type-v2='layout-basic']/zone[@type='dashboard-object']") is None


def test_set_field_format_preserves_identity_and_updates_existing_dependencies(editor, monkeypatch):
    editor.add_calculated_field("Money", "SUM([Sales])", datatype="real")
    editor.add_worksheet("Money Sheet")
    editor.configure_chart("Money Sheet", rows=["Category"], label="Money")
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    for field in ["Sales", "Money"]:
        before = editor.field_registry.parse_expression(field).column_local_name
        tools_workbook.set_field_format(field, 'c"$"#,##0.00')
        assert editor.field_registry.parse_expression(field).column_local_name == before
        assert editor._datasource.find(f"column[@name='{before}']").get("default-format") == 'c"$"#,##0.00'
        for node in editor._find_worksheet("Money Sheet").findall(f"table/view/datasource-dependencies/column[@name='{before}']"):
            assert node.get("default-format") == 'c"$"#,##0.00'
    editor.set_field_format("Money", "")
    assert editor._datasource.find("column[@caption='Money']").get("default-format") is None
    with pytest.raises(ValueError):
        editor.set_field_format("Money", None)


def test_parameter_axis_title_mcp_graph_binding_and_idempotence(editor, monkeypatch, tmp_path):
    editor.add_parameter("Period", "string", "month")
    editor.add_parameter("Another", "string", "week")
    editor.add_worksheet("Dynamic Axis")
    editor.configure_chart("Dynamic Axis", columns=["MONTH(Order Date)"], rows=["SUM(Sales)"])
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    for parameter in ["Period", "Another"]:
        tools_workbook.configure_worksheet_style("Dynamic Axis", axis_style={"per_field": [{"field": "MONTH(Order Date)", "scope": "cols", "title_parameter": parameter}]})
    graph = editor.root.find("datagraph/graph")
    assert len(graph.findall("nodes/axis-title-node")) == 1
    assert len(graph.findall("nodes/single-value-field-node")) == 1
    source = graph.find("nodes/single-value-field-node")
    assert source.get("fieldname") == "[Parameters]." + editor._parameters["Another"]["internal_name"]
    axis = graph.find("nodes/axis-title-node")
    assert axis.get("fieldname").endswith(editor.field_registry.parse_expression("MONTH(Order Date)").instance_name)
    assert axis.get("sheet-identifier") == editor._find_worksheet("Dynamic Axis").find("simple-id").get("uuid")
    edge = graph.find("edges/edge")
    assert edge.get("from") == source.get("value-output-guid")
    assert edge.get("to") == axis.get("title-input-guid")
    assert editor.root.find("document-format-change-manifest/DatagraphNodeAxisTitle") is not None
    path = tmp_path / "dynamic.twb"
    editor.save(path, validate=False)
    from lxml import etree
    saved = etree.parse(str(path))
    assert saved.find("datagraph/graph/nodes/axis-title-node") is not None
    assert saved.find("datagraph/graph/nodes/single-value-field-node") is not None
    with pytest.raises(ValueError):
        editor.configure_worksheet_style("Dynamic Axis", axis_style={"per_field": [{"field": "SUM(Sales)", "title_parameter": "Missing"}]})


def test_navigation_button_enables_text_and_action_features_once(editor):
    editor.add_dashboard("Target")
    for name in ["First", "Second"]:
        editor.add_dashboard(name, layout={"type": "container", "direction": "floating", "children": [{"type": "navigation_button", "target_dashboard": "Target"}]})
    manifest = editor.root.find("document-format-change-manifest")
    for feature in ["BasicButtonObject", "BasicButtonObjectTextSupport", "NavigationAction"]:
        assert len(manifest.findall(feature)) == 1
    assert manifest.find("BasicButtonObjectTextSupport").get("ignorable") == "true"


def test_size_encoding_is_field_bound_replaceable_and_exposed_by_mcp(editor, monkeypatch):
    editor.add_worksheet("Size")
    editor.configure_chart("Size", rows=["Category"], size="SUM(Sales)")
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    settings = {"field": "SUM(Sales)", "min": "1", "min_size": "0.00251905", "max_size": 1}
    for _ in range(2):
        tools_workbook.configure_worksheet_style("Size", size_style=settings)
    nodes = editor._find_worksheet("Size").findall("table/style/style-rule[@element='mark']/encoding[@attr='size']")
    assert len(nodes) == 1
    assert nodes[0].get("type") == "rangesize"
    assert nodes[0].get("field").endswith(editor.field_registry.parse_expression("SUM(Sales)").instance_name)
    assert nodes[0].get("min-size") == "0.00251905"
    assert nodes[0].get("max-size") == "1"
    assert nodes[0].get("min") == "1"


@pytest.mark.parametrize("settings", [{"min_size": 1}, {"field": "Sales", "type": "palette"}, {"field": "Sales", "min_size": -1}, {"field": "Sales", "max_size": "nan"}, {"field": "Sales", "max": []}])
def test_invalid_size_encoding_rejected(editor, settings):
    editor.add_worksheet("Size")
    editor.configure_chart("Size", rows=["Category"], size="SUM(Sales)")
    with pytest.raises(ValueError):
        editor.configure_worksheet_style("Size", size_style=settings)


def test_gridlines_are_scoped_and_mcp_updates_idempotently(editor, monkeypatch):
    editor.add_worksheet("Grid")
    editor.configure_chart("Grid", rows=["SUM(Sales)"], columns=["MONTH(Order Date)"])
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    for _ in range(2):
        tools_workbook.configure_worksheet_style("Grid", gridline_style={"rows": {"line_visibility": "on", "stroke_color": "#dddddd"}, "cols": {"line_visibility": "off"}})
    rule = editor._find_worksheet("Grid").find("table/style/style-rule[@element='gridline']")
    assert len(rule.findall("format[@attr='line-visibility']")) == 2
    assert rule.find("format[@scope='rows'][@attr='line-visibility']").get("value") == "on"
    assert rule.find("format[@scope='cols'][@attr='line-visibility']").get("value") == "off"
    assert rule.find("format[@scope='rows'][@attr='stroke-color']").get("value") == "#dddddd"
    with pytest.raises(ValueError):
        editor.configure_worksheet_style("Grid", gridline_style={"bad": {"line_visibility": "off"}})


def test_navigation_targets_window_uuid_not_dashboard_uuid(editor):
    editor.add_dashboard("Destination")
    dashboard_id = editor.root.find("dashboards/dashboard[@name='Destination']/simple-id")
    window_id = editor.root.find("windows/window[@class='dashboard'][@name='Destination']/simple-id")
    dashboard_id.set("uuid", "{DASHBOARD-IDENTITY}")
    window_id.set("uuid", "{WINDOW-IDENTITY}")
    editor.add_dashboard("Origin", layout={"type": "container", "direction": "floating", "children": [{"type": "navigation_button", "target_dashboard": "Destination"}]})
    action = editor.root.find("dashboards/dashboard[@name='Origin']/zones/zone/button").get("action")
    assert action == 'tabdoc:goto-sheet window-id="{WINDOW-IDENTITY}"'
    assert "DASHBOARD-IDENTITY" not in action
