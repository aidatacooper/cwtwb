from lxml import etree
import pytest
from cwtwb import TWBEditor
from cwtwb.mcp import tools_workbook


def test_measure_aliases_use_actual_table_calculation_instances(monkeypatch):
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Running Sales", "RUNNING_SUM(SUM([Sales]))", table_calc="Rows"
    )
    editor.add_worksheet("Summary")
    editor.configure_layered_chart(
        "Summary",
        rows=["Category"],
        columns=["Measure Names"],
        panes=[
            {
                "mark_type": "Text",
                "label": "Multiple Values",
                "measure_values": ["Running Sales", "SUM(Profit)"],
            }
        ],
    )
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.set_measure_name_aliases(
        "Summary", {"Running Sales": "Sales", "SUM(Profit)": "Profit"}
    )
    editor.set_measure_name_aliases("Summary", {"Running Sales": "Total Sales"})
    aliases = editor.root.findall(
        "datasources/datasource/column[@name='[:Measure Names]']/aliases/alias"
    )
    assert len(aliases) == 2
    instance = editor.root.find(
        ".//worksheet[@name='Summary']//column-instance[@derivation='User']"
    )
    assert instance.get("name") in aliases[0].get("key")
    assert aliases[0].get("value") == "Total Sales"
    assert aliases[1].get("value") == "Profit"
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        editor.set_measure_name_aliases("Summary", {"SUM(Sales)": "Unused"})
    assert etree.tostring(editor.root) == before
