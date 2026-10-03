from pathlib import Path
import zipfile

import pytest
from lxml import etree

from cwtwb.twb_editor import TWBEditor


def test_multiple_hyper_sources_keep_independent_fields_and_package(tmp_path):
    hyper = pytest.importorskip("tableauhyperapi")
    paths = []
    with hyper.HyperProcess(hyper.Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
        for index, field in enumerate(("First Value", "Second Value")):
            path = tmp_path / f"source{index}.hyper"
            with hyper.Connection(hp.endpoint, str(path), hyper.CreateMode.CREATE_AND_REPLACE) as connection:
                connection.catalog.create_schema("Extract")
                table = hyper.TableDefinition(hyper.TableName("Extract", "Extract"), [hyper.TableDefinition.Column(field, hyper.SqlType.int())])
                connection.catalog.create_table(table)
                with hyper.Inserter(connection, table) as inserter:
                    inserter.add_row([index + 1])
                    inserter.execute()
            paths.append(path)
    editor = TWBEditor("")
    editor.set_hyper_connection(str(paths[0]))
    first = editor.select_datasource(editor.field_registry.datasource_name)
    editor.add_worksheet("First")
    editor.configure_chart("First", mark_type="Text", label="SUM(First Value)")
    second = editor.add_hyper_datasource("Second Source", str(paths[1]))
    editor.add_worksheet("Second")
    editor.configure_chart("Second", mark_type="Text", label="SUM(Second Value)")
    assert first != second
    assert editor.select_datasource(first) == first
    editor.add_calculated_field("Double First", "[First Value]*2")
    with pytest.raises(ValueError):
        editor.select_datasource("Parameters")
    with pytest.raises(ValueError):
        editor.add_hyper_datasource("Second Source", str(paths[1]))
    with pytest.raises(Exception):
        editor.add_hyper_datasource("Failed", str(tmp_path / "missing.hyper"))
    assert editor.field_registry.datasource_name == first
    assert not editor.root.xpath("//datasources/datasource[@caption='Failed']")
    output = tmp_path / "independent.twbx"
    editor.save(str(output))
    with zipfile.ZipFile(output) as archive:
        assert all(p.name in archive.namelist() for p in paths)
        root = etree.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('.twb'))))
    for sheet, datasource in (("First", first), ("Second", second)):
        view = root.xpath("//worksheet[@name=$name]/table/view", name=sheet)[0]
        assert view.find("datasource-dependencies").get("datasource") == datasource


def test_embedded_sheet_tooltip_creates_native_field_filter(editor, tmp_path):
    for name in ("Source", "Details"):
        editor.add_worksheet(name)
        editor.configure_chart(name, mark_type="Text", rows=["Category"], label="SUM(Sales)")
    editor.configure_custom_tooltip("Source", [{"text": "Detail\n"}, {"sheet": {"name": "Details", "filter_fields": ["Category"], "maxwidth": 400}}])
    editor.configure_custom_tooltip("Source", [{"sheet": {"name": "Details", "filter_fields": ["Category"]}}])
    source = editor.root.xpath("//worksheet[@name='Source']")[0]
    text = source.find(".//customized-tooltip/formatted-text/run").text
    assert '<Sheet name="Details"' in text
    assert 'filter="<[' in text and 'none:Category' in text
    assert '&lt;' not in text
    assert len(editor.root.xpath("//datasources/datasource/group[@hidden='true']")) == 1
    target = editor.root.xpath("//worksheet[@name='Details']/table/view")[0]
    assert len(target.findall("filter")) == 1
    assert target.find("filter/groupfilter").get("{http://www.tableausoftware.com/xml/user}ui-enumeration") == "all"
    assert '[Tooltip (Category' in target.find("slices/column").text
    path = tmp_path / 'tooltip.twb'
    editor.save(str(path))
    assert etree.parse(str(path)).find("document-format-change-manifest/VizInTooltipHideWorksheet") is not None


@pytest.mark.parametrize('sheet', [{"name": "Missing", "filter_fields": ["Category"]}, {"name": "Source", "filter_fields": []}, {"name": "Source", "filter_fields": ["Category"], "maxwidth": -1}])
def test_invalid_tooltip_sheet_rejected(editor, sheet):
    editor.add_worksheet("Source")
    editor.configure_chart("Source", rows=["Category"])
    with pytest.raises(ValueError):
        editor.configure_custom_tooltip("Source", [{"sheet": sheet}])


def test_native_toggle_targets_shared_container_and_window(editor, tmp_path):
    for name in ("Selector", "List", "Main"):
        editor.add_worksheet(name)
        editor.configure_chart(name, rows=["Category"], label="SUM(Sales)")
    editor.add_dashboard("Dashboard", width=700, height=700, layout={"type": "container", "direction": "floating", "children": [
        {"type": "worksheet", "name": "Main", "absolute": {"x": 0, "y": 0, "w": 100000, "h": 100000}},
        {"type": "container", "direction": "vertical", "absolute": {"x": 1000, "y": 6000, "w": 50000, "h": 50000}, "children": [{"type": "worksheet", "name": "Selector"}, {"type": "worksheet", "name": "List"}]},
    ]})
    editor.add_dashboard_toggle_button("Dashboard", ["Selector", "List"], initially_hidden=True, position={"x": 7, "y": 7, "w": 350, "h": 30})
    dashboard = editor.root.xpath("//dashboard[@name='Dashboard']")[0]
    selector = dashboard.xpath(".//zone[@name='Selector']")[0]
    parent = selector.getparent()
    button_zone = dashboard.xpath(".//zone[button]")[0]
    action = button_zone.find("button/toggle-action").text
    window_id = editor.root.xpath("//window[@name='Dashboard']/simple-id")[0].get("uuid")
    assert f'window-id="{window_id}"' in action
    assert f'zone-ids=[{parent.get("id")}]' in action
    assert all(z.get("hidden-by-user") == "true" for z in parent.iter("zone"))
    assert dashboard.xpath(".//zone[@name='Main']")[0].get("hidden-by-user") is None
    assert button_zone.find("button").get("active-visual-state-index") == "1"
    path = tmp_path / 'toggle.twb'
    editor.save(str(path))
    assert etree.parse(str(path)).xpath("//button/toggle-action")
    with pytest.raises(ValueError):
        editor.add_dashboard_toggle_button("Dashboard", ["Main"])


def test_axis_unit_bar_sizing_and_breakdown(editor):
    editor.add_worksheet("Bars")
    editor.configure_layered_chart("Bars", columns=["MONTH(Order Date)"], panes=[{"axis": "SUM(Sales)", "mark_type": "Bar", "breakdown": "off", "mark_sizing": {"mark-sizing-setting": "marks-scaling-on", "mark-alignment": "mark-alignment-center", "use-custom-mark-size": False, "custom-mark-size-in-axis-units": 1.0}}])
    pane = editor.root.xpath("//worksheet[@name='Bars']/table/panes/pane[1]")[0]
    assert pane.find("view/breakdown").get("value") == "off"
    sizing = pane.find("mark-sizing")
    assert sizing.get("custom-mark-size-in-axis-units") == "1.0"
    assert sizing.get("use-custom-mark-size") == "false"


@pytest.mark.parametrize('sizing', [{'custom-mark-size-in-axis-units': float('nan')}, {'use-custom-mark-size': 'false'}, {'mark-sizing-setting': 'invalid'}, {'unexpected': True}])
def test_invalid_axis_unit_mark_sizing_rejected(editor, sizing):
    editor.add_worksheet('Bars')
    with pytest.raises(ValueError):
        editor.configure_layered_chart('Bars', panes=[{'axis': 'SUM(Sales)', 'mark_sizing': sizing}])


def test_measure_names_palette_uses_actual_measure_instances(editor):
    editor.add_calculated_field('Forecast', 'SUM([Sales])*1.1')
    editor.add_worksheet('Metrics')
    editor.configure_layered_chart('Metrics', panes=[{'axis': 'Multiple Values', 'measure_values': ['SUM(Sales)', 'Forecast'], 'mark_type': 'Bar', 'color': 'Measure Names', 'color_map': {'SUM(Sales)': '#4e79a7', 'Forecast': '#76b7b2'}, 'breakdown': 'off'}])
    encoding = editor.root.xpath("//datasources/datasource/style/style-rule/encoding[@field='[:Measure Names]']")[0]
    buckets = [item.text for item in encoding.findall('map/bucket')]
    assert len(buckets) == 2 and all(value.startswith('"[federated.') and value.endswith('"') for value in buckets)
    assert any('.[sum:Sales' in value for value in buckets)
    forecast = editor.field_registry.parse_expression('Forecast')
    assert any(editor.field_registry.resolve_full_reference(forecast.instance_name) in value for value in buckets)
    assert not editor.root.xpath("//datasources/datasource/column[@caption='Measure Names']")


def test_shape_and_colour_palettes_share_ordinal_calculation_identity(editor):
    editor.add_calculated_field('Event', 'IF SUM([Sales])>100 THEN 1 ELSE 0 END', datatype='integer', role='dimension', field_type='ordinal')
    editor.add_worksheet('Events')
    editor.configure_layered_chart('Events', panes=[{'axis': 'SUM(Sales)', 'mark_type': 'Shape', 'color': 'Event', 'shape': 'Event', 'color_map': {'0': '#ff9900', '1': '#0066aa', '%null%': '#000000'}, 'shape_map': {'0': ':filled/diamond', '1': ':filled/diamond', '%null%': ':filled/right-triangle'}}])
    pane = editor.root.xpath("//worksheet[@name='Events']/table/panes/pane")[0]
    assert pane.find('encodings/shape').get('column') == pane.find('encodings/color').get('column')
    shape_encoding = editor.root.xpath("//datasources/datasource/style/style-rule/encoding[@attr='shape']")[0]
    assert [(m.find('bucket').text, m.get('to')) for m in shape_encoding.findall('map')] == [('0', ':filled/diamond'), ('1', ':filled/diamond'), ('%null%', ':filled/right-triangle')]


def test_continuous_colour_and_size_can_be_reversed(editor):
    editor.add_worksheet('Points')
    editor.configure_chart('Points', mark_type='Circle', color='SUM(Sales)', size='SUM(Sales)')
    editor.configure_worksheet_style('Points', color_style={'field':'SUM(Sales)','palette':'red_10_0','reverse':True}, size_style={'field':'SUM(Sales)','reverse':True})
    encodings = editor.root.xpath("//worksheet[@name='Points']/table/style/style-rule/encoding[@attr='color' or @attr='size']")
    assert len(encodings) == 2 and all(e.get('reverse') == 'true' for e in encodings)
    with pytest.raises(ValueError):
        editor.configure_worksheet_style('Points', size_style={'field':'SUM(Sales)','reverse':'true'})
