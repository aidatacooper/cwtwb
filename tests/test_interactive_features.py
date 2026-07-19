import unittest
import lxml.etree as etree
from pathlib import Path
from cwtwb.twb_editor import TWBEditor

class TestInteractiveFeatures(unittest.TestCase):
    def setUp(self):
        template_path = Path(__file__).parent.parent / "src" / "cwtwb" / "references" / "superstore.twb"
        self.editor = TWBEditor(template_path)
        
    def test_tooltip(self):
        self.editor.add_worksheet("TestTooltip")
        self.editor.configure_chart(
             "TestTooltip",
             mark_type="Bar",
             columns=["SUM(Sales)"],
             rows=["Category"],
             tooltip=["SUM(Profit)", "Discount"]
        )
        ws = self.editor._find_worksheet("TestTooltip")
        pane = ws.find(".//pane")
        encodings = pane.find("encodings")
        self.assertIsNotNone(encodings)
        
        tooltips = encodings.findall("tooltip")
        self.assertEqual(len(tooltips), 2)
        self.assertTrue(any("Profit" in tt.get("column", "") for tt in tooltips))
        self.assertTrue(any("Discount" in tt.get("column", "") for tt in tooltips))

    def test_filters(self):
        self.editor.add_worksheet("TestFilter")
        filters = [
            {"column": "Region", "values": ["East", "West"]}
        ]
        self.editor.configure_chart(
             "TestFilter",
             mark_type="Bar",
             columns=["SUM(Sales)"],
             rows=["Category"],
             filters=filters
        )
        
        ws = self.editor._find_worksheet("TestFilter")
        view = ws.find("table/view")
        filter_el = view.find("filter")
        self.assertIsNotNone(filter_el)
        self.assertEqual(filter_el.get("class"), "categorical")
        self.assertTrue("Region" in filter_el.get("column", ""))
        
        gf_union = filter_el.find("groupfilter")
        self.assertIsNotNone(gf_union)
        self.assertEqual(gf_union.get("function"), "union")
        
        members = gf_union.findall("groupfilter")
        self.assertEqual(len(members), 2)
        self.assertEqual(members[0].get("member"), '"East"')
        self.assertEqual(members[1].get("member"), '"West"')

if __name__ == "__main__":
    unittest.main()
