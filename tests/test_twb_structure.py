"""TWB Structure validation tests using TWBAssert DSL.

Tests cover all supported chart types, parameters, calculated fields,
dashboards, and map features using the structured assertion API.
"""

import pytest
from lxml import etree

from cwtwb.validator import TWBValidationError, validate_workbook_file
from twb_assert import TWBAssert


class TestCategoricalGroup:
    def test_group_serializes_categorical_bin(self, editor_superstore):
        editor_superstore.add_group(
            "Sales Region",
            "Region",
            {
                "Coasts": ["East", "West"],
                "Interior": ["Central", "South"],
            },
        )

        column = editor_superstore._datasource.find("column[@caption='Sales Region']")
        assert column is not None
        calculation = column.find("calculation")
        assert calculation is not None
        assert calculation.get("class") == "categorical-bin"
        assert calculation.get("column") == "[Region (Orders)]"
        assert calculation.get("default") == '"Other"'
        assert [item.get("value") for item in calculation.findall("bin")] == [
            '"Coasts"',
            '"Interior"',
        ]
        assert [item.text for item in calculation.findall("bin/value")] == [
            '"East"',
            '"West"',
            '"Central"',
            '"South"',
        ]

        editor_superstore.add_worksheet("Grouped Sales")
        editor_superstore.configure_chart(
            "Grouped Sales",
            mark_type="Bar",
            rows=["Sales Region"],
            columns=["SUM(Sales)"],
        )
        worksheet = editor_superstore._find_worksheet("Grouped Sales")
        dependencies = worksheet.find(".//datasource-dependencies")
        assert dependencies is not None
        assert dependencies.find("column[@caption='Sales Region']") is not None
        assert dependencies.find("column[@name='[Region (Orders)]']") is not None
        group_local_name = column.get("name")
        assert dependencies.find(
            f"column-instance[@column='{group_local_name}']"
        ) is None
        assert worksheet.find(".//rows").text.endswith(f".{group_local_name}")


class TestAggregateCalculatedFieldTooltip:
    def test_tooltip_uses_user_derivation_for_aggregate_calculation(self, editor):
        editor.add_calculated_field(
            "Distinct Orders",
            "COUNTD([Order ID])",
            datatype="integer",
        )
        editor.add_worksheet("Order Count")
        editor.configure_chart(
            "Order Count",
            mark_type="Text",
            label="Distinct Orders",
            tooltip=["Distinct Orders"],
        )

        worksheet = editor._find_worksheet("Order Count")
        dependencies = worksheet.find(".//datasource-dependencies")
        assert dependencies is not None
        assert dependencies.find(
            "column-instance[@derivation='User']"
        ) is not None
        assert dependencies.find(
            "column-instance[@derivation='Sum']"
        ) is None


class TestBarChart:
    """Bar chart structure validation."""

    def test_basic_bar(self, editor):
        editor.add_worksheet("Sales")
        editor.configure_chart("Sales", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"])

        (TWBAssert(editor)
            .xml_valid()
            .worksheet_exists("Sales")
            .mark_type("Sales", "Bar")
            .has_rows("Sales")
            .has_cols("Sales")
            .rows_contain("Sales", "Category")
            .cols_contain("Sales", "Sales"))

    def test_save_runs_unified_file_validation_chain(self, editor, tmp_path):
        editor.add_worksheet("Sales")
        editor.configure_chart("Sales", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"])

        output = tmp_path / "valid.twb"
        editor.save(output)

        # validate_workbook_file runs structural + XSD validation on the saved file
        result = validate_workbook_file(output)
        assert result.valid or result.compatibility_only

    def test_xsd_validation_catches_unknown_elements(self, editor, tmp_path):
        editor.add_worksheet("Sales")
        editor.configure_chart("Sales", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"])

        output = tmp_path / "strict_invalid.twb"
        editor.save(output, validate=False)

        # Inject an invalid element into the saved file
        from lxml import etree
        tree = etree.parse(str(output))
        tree.getroot().append(etree.Element("cwtwb-invalid-top-level-node"))
        tree.write(str(output), xml_declaration=True, encoding="utf-8")

        with pytest.raises(TWBValidationError, match="XSD validation"):
            validate_workbook_file(output)

    def test_saved_file_validation_allows_known_tableau_tail_warning(self, editor, tmp_path):
        editor.add_worksheet("Sales")
        editor.configure_chart("Sales", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"])

        output = tmp_path / "valid_with_known_tail_warning.twb"
        editor.save(output)

        result = validate_workbook_file(output)
        assert result.errors == []
        assert result.compatibility_only is True

    def test_bar_with_color(self, editor):
        editor.add_worksheet("ColorBar")
        editor.configure_chart("ColorBar", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"],
                              color="Region")

        (TWBAssert(editor)
            .worksheet_exists("ColorBar")
            .mark_type("ColorBar", "Bar")
            .has_encoding("ColorBar", "color"))

    def test_bar_with_sort(self, editor):
        editor.add_worksheet("SortedBar")
        editor.configure_chart("SortedBar", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"],
                              sort_descending="SUM(Sales)")

        (TWBAssert(editor)
            .worksheet_exists("SortedBar")
            .mark_type("SortedBar", "Bar")
            .has_rows("SortedBar"))


class TestLineChart:
    """Line chart structure validation."""

    def test_basic_line(self, editor):
        editor.add_worksheet("Trend")
        editor.configure_chart("Trend", mark_type="Line",
                              columns=["MONTH(Order Date)"],
                              rows=["SUM(Sales)"])

        (TWBAssert(editor)
            .xml_valid()
            .worksheet_exists("Trend")
            .mark_type("Trend", "Line")
            .has_rows("Trend")
            .has_cols("Trend"))


class TestPieChart:
    """Pie chart structure validation."""

    def test_basic_pie(self, editor):
        editor.add_worksheet("Pie")
        editor.configure_chart("Pie", mark_type="Pie",
                              color="Segment", wedge_size="SUM(Sales)")

        (TWBAssert(editor)
            .xml_valid()
            .worksheet_exists("Pie")
            .mark_type("Pie", "Pie")
            .has_encoding("Pie", "color")
            .has_encoding("Pie", "wedge-size"))


class TestAreaChart:
    """Area chart structure validation."""

    def test_basic_area(self, editor):
        editor.add_worksheet("Area")
        editor.configure_chart("Area", mark_type="Area",
                              columns=["MONTH(Order Date)"],
                              rows=["SUM(Sales)"],
                              color="Category")

        (TWBAssert(editor)
            .xml_valid()
            .worksheet_exists("Area")
            .mark_type("Area", "Area")
            .has_encoding("Area", "color"))


class TestMapChart:
    """Map chart structure validation."""

    def test_basic_map(self, editor):
        editor.add_worksheet("Map")
        editor.configure_chart("Map", mark_type="Map",
                              geographic_field="State/Province")

        (TWBAssert(editor)
            .xml_valid()
            .worksheet_exists("Map")
            .mark_type("Map", "Multipolygon")
            .has_rows("Map")
            .has_cols("Map")
            .rows_contain("Map", "Latitude (generated)")
            .cols_contain("Map", "Longitude (generated)")
            .has_mapsources("Map")
            .has_encoding("Map", "geometry"))

    def test_map_with_encodings(self, editor):
        editor.add_worksheet("MapEnc")
        editor.configure_chart("MapEnc", mark_type="Map",
                              geographic_field="State/Province",
                              color="SUM(Profit)", size="SUM(Sales)")

        (TWBAssert(editor)
            .worksheet_exists("MapEnc")
            .has_encoding("MapEnc", "color")
            .has_encoding("MapEnc", "size")
            .encoding_contains("MapEnc", "color", "Profit"))

    def test_map_with_map_fields(self, editor):
        """map_fields parameter adds extra LOD fields."""
        editor.add_worksheet("MapFields")
        editor.configure_chart("MapFields", mark_type="Map",
                              geographic_field="State/Province",
                              color="SUM(Sales)",
                              map_fields=["Country/Region"])

        (TWBAssert(editor)
            .worksheet_exists("MapFields")
            .has_encoding("MapFields", "lod")
            .has_encoding("MapFields", "geometry"))

    def test_map_without_map_fields(self, editor):
        """Map without map_fields should not have Country/Region LOD."""
        editor.add_worksheet("MapNoFields")
        editor.configure_chart("MapNoFields", mark_type="Map",
                              geographic_field="State/Province")

        (TWBAssert(editor)
            .worksheet_exists("MapNoFields")
            .has_encoding("MapNoFields", "geometry"))

    def test_map_layers_accept_spatial_geometry_fields(self, editor):
        editor.add_calculated_field(
            "Route",
            "MAKELINE(MAKEPOINT(1, 2), MAKEPOINT(3, 4))",
            datatype="spatial",
            role="measure",
            field_type="nominal",
        )
        editor.add_calculated_field(
            "Destination",
            "MAKEPOINT(3, 4)",
            datatype="spatial",
            role="measure",
            field_type="nominal",
        )
        editor.add_worksheet("Spatial Layers")
        editor.configure_chart(
            "Spatial Layers",
            mark_type="Map",
            geographic_field="Route",
            map_partition="Category",
            map_layers=[
                {
                    "geometry": "Route",
                    "size": "SUM(Sales)",
                    "detail": "Category",
                    "tooltip": ["Category", "SUM(Sales)"],
                },
                {
                    "geometry": "Destination",
                    "detail": "State/Province",
                    "has_stroke": True,
                    "stroke_color": "#ffffff",
                },
            ],
        )

        worksheet = editor._find_worksheet("Spatial Layers")
        panes = worksheet.findall(".//panes/pane")
        assert len(panes) == 3
        assert panes[0].find("encodings/geometry") is None
        route_geometry = panes[1].find("encodings/geometry").get("column")
        destination_geometry = panes[2].find("encodings/geometry").get("column")
        assert ".[clct:" in route_geometry
        assert ".[clct:" in destination_geometry
        spatial_instances = worksheet.findall(
            ".//datasource-dependencies/column-instance[@derivation='Collect']"
        )
        assert len(spatial_instances) == 2
        assert route_geometry != destination_geometry
        assert panes[1].find("encodings/lod") is not None
        assert (
            panes[2].find("style/style-rule/format[@attr='has-stroke']")
            is not None
        )
        assert "none:Category" in worksheet.findtext(".//cols")
        assert worksheet.findtext(".//cols").count("Longitude (generated)") == 2


class TestKPICard:
    """KPI card (measure values) structure validation."""

    def test_measure_values(self, editor):
        editor.add_worksheet("KPI")
        editor.configure_chart("KPI", mark_type="Text",
                              measure_values=["SUM(Sales)", "SUM(Profit)"])

        (TWBAssert(editor)
            .xml_valid()
            .worksheet_exists("KPI")
            .mark_type("KPI", "Text")
            .has_encoding("KPI", "text")
            .encoding_contains("KPI", "text", "Multiple Values")
            .cols_contain("KPI", "Measure Names")
            .has_filter("KPI", "Measure Names"))


class TestParameters:
    """Parameter structure validation."""

    def test_add_parameter(self, editor):
        editor.add_parameter(name="Target", datatype="real",
                            default_value="10000",
                            domain_type="range",
                            min_value="0", max_value="100000")

        (TWBAssert(editor)
            .has_parameter("Target")
            .parameter_datasource_exists())

    def test_multiple_parameters(self, editor):
        editor.add_parameter(name="Param A", default_value="1")
        editor.add_parameter(name="Param B", default_value="2")

        (TWBAssert(editor)
            .has_parameter("Param A")
            .has_parameter("Param B")
            .parameter_datasource_exists())


class TestCalculatedFields:
    """Calculated field structure validation."""

    def test_add_calculated_field(self, editor):
        editor.add_calculated_field("Profit Ratio",
                                   "SUM([Profit])/SUM([Sales])", "real")

        (TWBAssert(editor)
            .has_calculated_field("Profit Ratio"))

    def test_calculated_field_in_chart(self, editor):
        editor.add_calculated_field("Profit Ratio",
                                   "SUM([Profit])/SUM([Sales])", "real")
        editor.add_worksheet("Ratios")
        editor.configure_chart("Ratios", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"],
                              color="Profit Ratio")

        (TWBAssert(editor)
            .worksheet_exists("Ratios")
            .has_encoding("Ratios", "color"))


class TestDashboard:
    """Dashboard structure validation."""

    def test_simple_dashboard(self, editor):
        editor.add_worksheet("Sheet A")
        editor.configure_chart("Sheet A", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"])
        editor.add_worksheet("Sheet B")
        editor.configure_chart("Sheet B", mark_type="Pie",
                              color="Segment", wedge_size="SUM(Sales)")
        editor.add_dashboard("Overview",
                            worksheet_names=["Sheet A", "Sheet B"],
                            layout="horizontal")

        (TWBAssert(editor)
            .xml_valid()
            .dashboard_exists("Overview")
            .dashboard_contains("Overview", "Sheet A")
            .dashboard_contains("Overview", "Sheet B"))

    def test_dashboard_with_filter_zone(self, editor):
        editor.add_worksheet("Filtered")
        editor.configure_chart("Filtered", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"],
                              filters=[{"column": "Region"}])

        layout = {
            "type": "container",
            "direction": "horizontal",
            "children": [
                {"type": "worksheet", "name": "Filtered"},
                {"type": "container", "direction": "vertical",
                 "fixed_size": 200,
                 "children": [
                     {"type": "filter", "worksheet": "Filtered",
                      "field": "Region", "mode": "dropdown"}
                 ]}
            ]
        }
        editor.add_dashboard("FilterDB",
                            worksheet_names=["Filtered"], layout=layout)

        (TWBAssert(editor)
            .dashboard_exists("FilterDB")
            .dashboard_has_zone_type("FilterDB", "filter"))

    def test_add_dashboard_replaces_existing_dashboard_name(self, editor):
        editor.add_worksheet("Sheet A")
        editor.configure_chart("Sheet A", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"])
        editor.add_worksheet("Sheet B")
        editor.configure_chart("Sheet B", mark_type="Pie",
                              color="Segment", wedge_size="SUM(Sales)")
        editor.add_worksheet("Sheet C")
        editor.configure_chart("Sheet C", mark_type="Line",
                              columns=["MONTH(Order Date)"], rows=["SUM(Sales)"])

        editor.add_dashboard(
            "Overview",
            worksheet_names=["Sheet A", "Sheet B"],
            layout="horizontal",
        )
        editor.add_dashboard(
            "Overview",
            worksheet_names=["Sheet A", "Sheet C"],
            layout="vertical",
        )

        dashboards = editor.root.findall(".//dashboards/dashboard[@name='Overview']")
        windows = editor.root.findall(".//windows/window[@class='dashboard'][@name='Overview']")

        assert len(dashboards) == 1
        assert len(windows) == 1

        zone_names = [
            zone.get("name")
            for zone in dashboards[0].findall(".//zone[@name]")
            if zone.get("name")
        ]
        assert "Sheet A" in zone_names
        assert "Sheet C" in zone_names
        assert "Sheet B" not in zone_names


class TestFilters:
    """Filter structure validation."""

    def test_categorical_filter(self, editor):
        editor.add_worksheet("FilterTest")
        editor.configure_chart("FilterTest", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"],
                              filters=[{"column": "Region",
                                       "values": ["East", "West"]}])

        (TWBAssert(editor)
            .has_filter("FilterTest", "Region"))

    def test_quantitative_filter(self, editor):
        editor.add_worksheet("QFilter")
        editor.configure_chart("QFilter", mark_type="Bar",
                              rows=["Category"], columns=["SUM(Sales)"],
                              filters=[{"column": "Order Date",
                                       "type": "quantitative"}])

        (TWBAssert(editor)
            .has_filter("QFilter", "Order Date"))

    def test_bounded_date_filter_uses_exact_date(self, editor):
        editor.add_worksheet("DateRangeFilter")
        editor.configure_chart(
            "DateRangeFilter",
            mark_type="Bar",
            rows=["Category"],
            columns=["SUM(Sales)"],
            filters=[
                {
                    "column": "Order Date",
                    "type": "quantitative",
                    "min": "#2025-07-11#",
                    "max": "#2025-07-23#",
                }
            ],
        )

        worksheet = editor._find_worksheet("DateRangeFilter")
        filter_el = worksheet.find(".//filter")
        assert filter_el is not None
        assert "tdy:" in filter_el.get("column")
        exact_date = worksheet.find(".//column-instance[@derivation='Day-Trunc']")
        assert exact_date is not None


class TestLayeredCharts:
    """Declarative multi-pane worksheet structure."""

    def test_layered_chart_builds_multiple_values_axis(self, editor):
        editor.add_worksheet("Layered")
        editor.configure_layered_chart(
            "Layered",
            columns=["Category"],
            rows=["SUM(Sales)", "Multiple Values"],
            panes=[
                {
                    "mark_type": "Area",
                    "axis": "SUM(Sales)",
                    "color": "Category",
                },
                {
                    "mark_type": "Line",
                    "axis": "Multiple Values",
                    "color": "Region",
                    "color_map": {"East": "#112233"},
                    "measure_values": ["SUM(Sales)", "SUM(Profit)"],
                    "mark_sizing_off": True,
                },
            ],
            hide_axes=True,
            table_calc_overrides={
                "SUM(Sales)": [
                    {"ordering_type": "Rows"},
                    {"field": "Profit", "ordering_type": "Rows"},
                    {
                        "ordering_field": "Category",
                        "ordering_type": "Field",
                    },
                ]
            },
        )

        worksheet = editor._find_worksheet("Layered")
        panes = worksheet.findall("table/panes/pane")
        assert [pane.find("mark").get("class") for pane in panes] == [
            "Area",
            "Line",
        ]
        assert panes[1].get("y-axis-name").endswith(".[Multiple Values]")
        assert "Multiple Values" in worksheet.findtext("table/rows")
        measure_names_filter = worksheet.find(
            "table/view/filter[@column][@class='categorical']"
        )
        assert measure_names_filter is not None
        assert measure_names_filter.get("column").endswith(".[:Measure Names]")
        assert worksheet.findtext("table/view/slices/column").endswith(
            ".[:Measure Names]"
        )
        sales_instance = worksheet.find(
            ".//column-instance[@column='[Sales (Orders)]']"
        )
        assert sales_instance is not None
        table_calcs = sales_instance.findall("table-calc")
        assert len(table_calcs) == 3
        assert table_calcs[1].get("field").endswith(".[Profit (Orders)]")
        assert "none:Category" in table_calcs[2].get("ordering-field")
        palette_map = editor._datasource.find(
            ".//style-rule[@element='mark']/encoding[@attr='color']/map"
        )
        assert palette_map is not None
        assert palette_map.get("to") == "#112233"
        assert palette_map.findtext("bucket") == '"East"'

    def test_worksheet_title_is_authored_from_public_api(self, editor):
        editor.add_worksheet("Titled")
        editor.set_worksheet_title("Titled", "A generated title")
        worksheet = editor._find_worksheet("Titled")
        assert (
            worksheet.findtext("layout-options/title/formatted-text/run")
            == "A generated title"
        )
        editor.set_worksheet_title("Titled", "")
        assert worksheet.find("layout-options/title") is None
