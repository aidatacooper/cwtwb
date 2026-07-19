"""Unit tests for Level 1 features: Parameters, Map, Filter/ParamCtrl Zones."""

import unittest
from pathlib import Path

import lxml.etree as etree

from cwtwb.twb_editor import TWBEditor


class TestParameters(unittest.TestCase):
    """Test add_parameter functionality."""

    def setUp(self):
        template_path = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"
        self.editor = TWBEditor(template_path)

    def test_add_parameter_range(self):
        """Range parameter creates correct XML structure."""
        result = self.editor.add_parameter(
            name="Target Profit",
            datatype="real",
            default_value="10000.0",
            domain_type="range",
            min_value="-30000.0",
            max_value="100000.0",
            granularity="10000.0",
        )
        self.assertIn("Target Profit", result)

        # Verify Parameters datasource was created
        params_ds = None
        for ds in self.editor.root.findall(".//datasource"):
            if ds.get("name") == "Parameters":
                params_ds = ds
                break
        self.assertIsNotNone(params_ds, "Parameters datasource should exist")
        self.assertEqual(params_ds.get("inline"), "true")
        self.assertEqual(params_ds.get("hasconnection"), "false")

        # Verify column structure
        col = params_ds.find("column")
        self.assertIsNotNone(col)
        self.assertEqual(col.get("caption"), "Target Profit")
        self.assertEqual(col.get("datatype"), "real")
        self.assertEqual(col.get("param-domain-type"), "range")
        self.assertEqual(col.get("role"), "measure")
        self.assertEqual(col.get("value"), "10000.0")

        # Verify calculation node
        calc = col.find("calculation")
        self.assertIsNotNone(calc)
        self.assertEqual(calc.get("class"), "tableau")
        self.assertEqual(calc.get("formula"), "10000.0")

        # Verify range node
        range_el = col.find("range")
        self.assertIsNotNone(range_el)
        self.assertEqual(range_el.get("min"), "-30000.0")
        self.assertEqual(range_el.get("max"), "100000.0")
        self.assertEqual(range_el.get("granularity"), "10000.0")

    def test_add_parameter_list(self):
        """List parameter creates correct XML structure."""
        self.editor.add_parameter(
            name="Region Selector",
            datatype="string",
            default_value="East",
            domain_type="list",
            allowed_values=["East", "West", "Central", "South"],
        )

        params_ds = None
        for ds in self.editor.root.findall(".//datasource"):
            if ds.get("name") == "Parameters":
                params_ds = ds
                break

        col = params_ds.find("column")
        self.assertEqual(col.get("param-domain-type"), "list")

        members = col.find("members")
        self.assertIsNotNone(members)
        member_list = members.findall("member")
        self.assertEqual(len(member_list), 4)
        self.assertEqual(member_list[0].get("value"), '"East"')

    def test_add_multiple_parameters(self):
        """Adding multiple parameters creates separate columns."""
        self.editor.add_parameter(name="Param A", default_value="1")
        self.editor.add_parameter(name="Param B", default_value="2")

        params_ds = None
        for ds in self.editor.root.findall(".//datasource"):
            if ds.get("name") == "Parameters":
                params_ds = ds
                break

        columns = params_ds.findall("column")
        self.assertEqual(len(columns), 2)
        self.assertEqual(columns[0].get("caption"), "Param A")
        self.assertEqual(columns[1].get("caption"), "Param B")

        # Verify internal names are unique
        self.assertEqual(columns[0].get("name"), "[Parameter 1]")
        self.assertEqual(columns[1].get("name"), "[Parameter 2]")

    def test_parameter_tracking(self):
        """Parameters are tracked in _parameters dict."""
        self.editor.add_parameter(name="Test Param", default_value="5")
        self.assertIn("Test Param", self.editor._parameters)
        self.assertEqual(self.editor._parameters["Test Param"]["internal_name"], "[Parameter 1]")


class TestMapChart(unittest.TestCase):
    """Test Map chart type in configure_chart."""

    def setUp(self):
        template_path = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"
        self.editor = TWBEditor(template_path)

    def test_configure_map_basic(self):
        """Map chart sets Latitude/Longitude and mapsources."""
        self.editor.add_worksheet("TestMap")
        result = self.editor.configure_chart(
            "TestMap",
            mark_type="Map",
            geographic_field="State/Province",
        )
        self.assertIn("Map", result)

        ws = self.editor._find_worksheet("TestMap")
        table = ws.find("table")

        # Should use generated Latitude/Longitude
        rows_el = table.find("rows")
        cols_el = table.find("cols")
        self.assertIn("Latitude (generated)", rows_el.text)
        self.assertIn("Longitude (generated)", cols_el.text)

        # Mark type should be Automatic (Tableau maps use Automatic)
        pane = table.find(".//pane")
        mark = pane.find("mark")
        self.assertEqual(mark.get("class"), "Multipolygon")

        # Mapsources should be present in view
        view = table.find("view")
        mapsources = view.find("mapsources")
        self.assertIsNotNone(mapsources)
        ms = mapsources.find("mapsource")
        self.assertEqual(ms.get("name"), "Tableau")

    def test_configure_map_with_encodings(self):
        """Map chart supports color and size encodings."""
        self.editor.add_worksheet("TestMap2")
        self.editor.configure_chart(
            "TestMap2",
            mark_type="Map",
            geographic_field="State/Province",
            color="SUM(Profit)",
            size="SUM(Sales)",
        )

        ws = self.editor._find_worksheet("TestMap2")
        pane = ws.find(".//pane")
        encodings = pane.find("encodings")
        self.assertIsNotNone(encodings)

        # Check color encoding exists
        color_el = encodings.find("color")
        self.assertIsNotNone(color_el)
        self.assertIn("Profit", color_el.get("column", ""))

        # Check size encoding exists
        size_el = encodings.find("size")
        self.assertIsNotNone(size_el)
        self.assertIn("Sales", size_el.get("column", ""))

        # Check geographic_field is added as lod encoding
        lod_els = encodings.findall("lod")
        self.assertTrue(len(lod_els) >= 1)


class TestFilterZones(unittest.TestCase):
    """Test filter and paramctrl zone types in layout."""

    def setUp(self):
        template_path = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"
        self.editor = TWBEditor(template_path)

    def test_dashboard_with_filter_zone(self):
        """Dashboard layout with filter zone generates correct XML."""
        self.editor.add_worksheet("Sales Chart")
        layout = {
            "type": "container",
            "direction": "horizontal",
            "children": [
                {"type": "worksheet", "name": "Sales Chart"},
                {
                    "type": "container",
                    "direction": "vertical",
                    "fixed_size": 200,
                    "children": [
                        {"type": "filter", "worksheet": "Sales Chart",
                         "field": "Region", "mode": "dropdown"},
                    ]
                }
            ]
        }
        self.editor.add_dashboard("TestDB", worksheet_names=["Sales Chart"], layout=layout)

        # Find the filter zone in the XML
        db = self.editor.root.find(".//dashboards/dashboard[@name='TestDB']")
        zones = db.find("zones")
        filter_zones = zones.findall(".//zone[@type-v2='filter']")
        self.assertEqual(len(filter_zones), 1)
        fz = filter_zones[0]
        self.assertEqual(fz.get("name"), "Sales Chart")
        self.assertEqual(fz.get("mode"), "dropdown")
        # param should contain Region reference
        self.assertIn("Region", fz.get("param", ""))

    def test_dashboard_with_paramctrl_zone(self):
        """Dashboard layout with paramctrl zone generates correct XML."""
        self.editor.add_worksheet("Profit Chart")
        self.editor.add_parameter(
            name="Target Profit",
            datatype="real",
            default_value="10000",
            domain_type="range",
            min_value="0",
            max_value="100000",
            granularity="5000",
        )

        layout = {
            "type": "container",
            "direction": "horizontal",
            "children": [
                {"type": "worksheet", "name": "Profit Chart"},
                {
                    "type": "container",
                    "direction": "vertical",
                    "fixed_size": 180,
                    "children": [
                        {"type": "paramctrl", "parameter": "Target Profit", "mode": "slider"},
                    ]
                }
            ]
        }
        self.editor.add_dashboard("ParamDB", worksheet_names=["Profit Chart"], layout=layout)

        db = self.editor.root.find(".//dashboards/dashboard[@name='ParamDB']")
        zones = db.find("zones")
        paramctrl_zones = zones.findall(".//zone[@type-v2='paramctrl']")
        self.assertEqual(len(paramctrl_zones), 1)
        pz = paramctrl_zones[0]
        self.assertEqual(pz.get("mode"), "slider")
        # param should contain the parameter internal reference
        self.assertIn("[Parameters]", pz.get("param", ""))
        self.assertIn("[Parameter 1]", pz.get("param", ""))

    def test_mixed_filter_and_paramctrl(self):
        """Dashboard can contain both filter and paramctrl zones."""
        self.editor.add_worksheet("Mixed Chart")
        self.editor.add_parameter(name="Growth Rate", default_value="0.1")

        layout = {
            "type": "container",
            "direction": "horizontal",
            "children": [
                {"type": "worksheet", "name": "Mixed Chart"},
                {
                    "type": "container",
                    "direction": "vertical",
                    "fixed_size": 200,
                    "children": [
                        {"type": "filter", "worksheet": "Mixed Chart",
                         "field": "Category", "mode": "checkdropdown"},
                        {"type": "paramctrl", "parameter": "Growth Rate",
                         "mode": "type_in"},
                    ]
                }
            ]
        }
        self.editor.add_dashboard("MixedDB", worksheet_names=["Mixed Chart"], layout=layout)

        db = self.editor.root.find(".//dashboards/dashboard[@name='MixedDB']")
        zones = db.find("zones")
        filter_zones = zones.findall(".//zone[@type-v2='filter']")
        paramctrl_zones = zones.findall(".//zone[@type-v2='paramctrl']")
        self.assertEqual(len(filter_zones), 1)
        self.assertEqual(len(paramctrl_zones), 1)
        self.assertEqual(paramctrl_zones[0].get("mode"), "type_in")


if __name__ == "__main__":
    unittest.main()
