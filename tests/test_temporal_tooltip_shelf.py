"""A temporal shelf field must not be redundantly encoded as a tooltip mark."""
from cwtwb import TWBEditor


def test_month_year_tooltip_keeps_shelf_reference_without_extra_mark_encoding():
    editor = TWBEditor("")
    editor.add_worksheet("Sales")
    editor.configure_chart("Sales", "Bar", columns=["MY(Order Date)"], rows=["SUM(Sales)"],
                           tooltip=["MY(Order Date)", "SUM(Sales)", "SUM(Profit)"])
    editor.configure_custom_tooltip("Sales", [{"field": "MY(Order Date)"}, {"field": "SUM(Sales)"}])
    table = editor.root.find("worksheets/worksheet/table")
    assert ".[my:" in table.findtext("cols")
    encodings = table.findall(".//pane/encodings/tooltip")
    assert len(encodings) == 1
    assert "Profit" in encodings[0].get("column")
    assert "[my:" in "".join(table.find(".//pane/customized-tooltip").itertext())
