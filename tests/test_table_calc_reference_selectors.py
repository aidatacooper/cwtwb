"""Explicit references distinguish a bound view instance from its source column."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def editor_fixture():
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Cols", "0", datatype="integer", role="dimension", field_type="ordinal"
    )
    editor.add_calculated_field(
        "Rows", "1", datatype="integer", role="dimension", field_type="ordinal"
    )
    editor.add_calculated_field(
        "Date", "#2020-01-01#", datatype="date", role="dimension", field_type="ordinal"
    )
    editor.add_calculated_field("Running", "WINDOW_SUM(SUM(1.0))", table_calc="Rows")
    editor.add_worksheet("Series")
    return editor


@pytest.mark.parametrize("field", ["Cols", "DAY(Date)", "EXACTDATE(Date)"])
def test_mixed_instance_and_column_references_are_exact(field, tmp_path):
    editor = editor_fixture()
    selector = {"field": field, "reference": "instance"}
    spec = {
        "ordering_type": "Field",
        "level_address": selector,
        "order": [selector, {"field": "Rows", "reference": "column"}],
    }
    for _ in range(2):
        editor.configure_layered_chart(
            "Series",
            columns=[field],
            rows=["Rows"],
            panes=[{"axis": "Running", "mark_type": "Text"}],
            table_calc_overrides={"Running": [spec]},
            table_calc_context=True,
        )
    instance = editor.field_registry.parse_expression(field)
    table_calc = editor.root.find(
        "worksheets/worksheet/table/view/datasource-dependencies/column-instance/table-calc[@ordering-type='Field']"
    )
    assert table_calc.get("level-address").endswith(instance.instance_name)
    orders = table_calc.findall("order")
    assert orders[0].get("field") == table_calc.get("level-address")
    assert (
        orders[1]
        .get("field")
        .endswith(editor.field_registry._find_field("Rows").local_name)
    )
    path = tmp_path / "references.twb"
    editor.save(str(path))
    assert (
        len(etree.parse(str(path)).findall(".//table-calc[@ordering-type='Field']"))
        == 1
    )


@pytest.mark.parametrize(
    "selector",
    [
        {"field": "Cols", "reference": "other"},
        {"field": "Cols"},
        {"field": "", "reference": "instance"},
        {"field": 1, "reference": "instance"},
        {"field": "Cols", "reference": None},
        {"field": "Cols", "reference": "instance", "extra": True},
    ],
)
def test_invalid_selector_preserves_configured_worksheet(selector):
    editor = editor_fixture()
    editor.configure_layered_chart(
        "Series", columns=["Cols"], panes=[{"axis": "Running", "mark_type": "Text"}]
    )
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError, match="reference"):
        editor.configure_layered_chart(
            "Series",
            columns=["Cols"],
            panes=[{"axis": "Running", "mark_type": "Text"}],
            table_calc_overrides={
                "Running": [{"ordering_type": "Field", "order": [selector]}]
            },
        )
    assert etree.tostring(editor.root) == before
