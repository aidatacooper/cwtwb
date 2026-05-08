import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from cwtwb.twb_editor import TWBEditor

@pytest.fixture
def empty_editor():
    template_path = Path(__file__).parent.parent / "templates" / "twb" / "superstore.twb"
    return TWBEditor(str(template_path))

def test_simplified_chart_types(empty_editor, tmp_path):
    editor = empty_editor
    
    def get_worksheet(ed, name):
        for ws in ed.root.findall(".//worksheet"):
            if ws.get("name") == name:
                return ws
        return None

    def check_mark(ed, ws_name, expected_class):
        ws = get_worksheet(ed, ws_name)
        assert ws is not None
        mark = ws.find(".//pane/mark")
        assert mark is not None
        assert mark.get("class") == expected_class
        
    def check_display_labels_off(ed, ws_name, scopes):
        ws = get_worksheet(ed, ws_name)
        assert ws is not None
        formats = ws.findall(".//style-rule[@element='worksheet']/format[@attr='display-field-labels']")
        found_scopes = [f.get("scope") for f in formats if f.get("value") == "false"]
        for scope in scopes:
            assert scope in found_scopes

    # Setup test data connection to prevent datasource errors
    editor.set_mysql_connection("127.0", "db", "user", "table")
    
    # Test Scatterplot (mapped to Circle)
    editor.add_worksheet("Scatter")
    editor.configure_chart("Scatter", mark_type="Scatterplot", columns=["SUM(Sales)"], rows=["SUM(Profit)"])
    check_mark(editor, "Scatter", "Circle")
    
    # Test Heatmap (mapped to Square)
    editor.add_worksheet("Heat")
    editor.configure_chart("Heat", mark_type="Heatmap", columns=["Category"], rows=["Region"], color="SUM(Sales)")
    check_mark(editor, "Heat", "Square")
    
    # Test Tree Map (mapped to Square, removes axes)
    editor.add_worksheet("Tree")
    editor.configure_chart("Tree", mark_type="Tree Map", size="SUM(Sales)", color="SUM(Profit)")
    check_mark(editor, "Tree", "Square")
    check_display_labels_off(editor, "Tree", ["cols", "rows"])
    
    # Test Bubble Chart (mapped to Circle, removes axes)
    editor.add_worksheet("Bubble")
    editor.configure_chart("Bubble", mark_type="Bubble Chart", size="SUM(Sales)", color="Category")
    check_mark(editor, "Bubble", "Circle")
    check_display_labels_off(editor, "Bubble", ["cols", "rows"])


def test_raw_measure_defaults_to_sum_on_view_bindings(empty_editor):
    editor = empty_editor
    editor.add_worksheet("Raw Measure Sum")
    editor.configure_chart(
        "Raw Measure Sum",
        mark_type="Bar",
        rows=["Category"],
        columns=["Sales"],
    )

    ws = editor._find_worksheet("Raw Measure Sum")
    cols_text = ws.findtext(".//cols") or ""
    deps = ws.findall(".//datasource-dependencies/column-instance")

    assert "sum:Sales (Orders):qk" in cols_text
    assert any(ci.get("derivation") == "Sum" and "Sales (Orders)" in (ci.get("column") or "") for ci in deps)
