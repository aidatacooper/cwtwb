"""Exact-date view bindings must preserve the registered field."""
from lxml import etree
from cwtwb import TWBEditor

def test_exactdate_normalization_does_not_register_expression_as_column():
    editor=TWBEditor("")
    editor.add_calculated_field("First Order Week","DATE('2020-01-06')",datatype="date",role="dimension",field_type="ordinal")
    editor.add_calculated_field("Revenue","1",datatype="integer")
    editor.add_worksheet("Timeline")
    editor.configure_chart("Timeline",mark_type="Line",columns=["EXACTDATE(First Order Week)"],rows=["SUM(Revenue)"])
    xml=etree.tostring(editor.root,encoding="unicode")
    assert 'name="[EXACTDATE(First Order Week)]"' not in xml
    columns=editor.root.find("./worksheets/worksheet/table/cols").text
    assert ":qk]" in columns and "EXACTDATE(" not in columns
    assert editor.field_registry.default_view_expression("EXACTDATE(First Order Week)")=="EXACTDATE(First Order Week)"
