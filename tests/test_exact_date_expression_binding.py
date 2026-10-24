"""Exact-date view bindings must preserve the registered field."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def test_exactdate_normalization_does_not_register_expression_as_column():
    editor = TWBEditor("")
    editor.add_calculated_field(
        "First Order Week",
        "DATE('2020-01-06')",
        datatype="date",
        role="dimension",
        field_type="ordinal",
    )
    editor.add_calculated_field("Revenue", "1", datatype="integer")
    editor.add_worksheet("Timeline")
    editor.configure_chart(
        "Timeline",
        mark_type="Line",
        columns=["EXACTDATE(First Order Week)"],
        rows=["SUM(Revenue)"],
    )
    xml = etree.tostring(editor.root, encoding="unicode")
    assert 'name="[EXACTDATE(First Order Week)]"' not in xml
    columns = editor.root.find("./worksheets/worksheet/table/cols").text
    assert ":qk]" in columns and "EXACTDATE(" not in columns
    assert (
        editor.field_registry.default_view_expression("EXACTDATE(First Order Week)")
        == "EXACTDATE(First Order Week)"
    )


def test_quantitative_calculated_date_has_direct_continuous_binding():
    editor = TWBEditor("")
    editor.add_calculated_field(
        "First Order Week",
        "DATE('2020-01-06')",
        datatype="date",
        role="dimension",
        field_type="quantitative",
    )
    instance = editor.field_registry.parse_expression("[First Order Week]")
    assert instance.derivation == "None"
    assert instance.ci_type == "quantitative"
    assert instance.instance_name.endswith(":qk]")


def test_custom_tooltip_rejects_exactdate_field_run():
    editor = TWBEditor("")
    editor.add_worksheet("Timeline")
    editor.configure_chart(
        "Timeline",
        mark_type="Line",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Sales)"],
    )
    with pytest.raises(ValueError, match="custom tooltip"):
        editor.configure_custom_tooltip(
            "Timeline",
            [{"field": "EXACTDATE(Order Date)"}],
        )
    assert editor.root.find(
        ".//worksheet[@name='Timeline']//customized-tooltip"
    ) is None
