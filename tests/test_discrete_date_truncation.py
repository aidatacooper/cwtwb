"""Discrete date truncations retain native date-domain completion."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


@pytest.mark.parametrize(
    "grain,prefix",
    [
        ("DAYTRUNC", "tdy"),
        ("MONTHTRUNC", "tmn"),
        ("QUARTERTRUNC", "tqr"),
        ("YEARTRUNC", "tyr"),
    ],
)
def test_explicit_discrete_truncation_keeps_domain_and_order(grain, prefix, tmp_path):
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Date", "#2020-01-01#", datatype="date", role="dimension", field_type="ordinal"
    )
    editor.add_calculated_field(
        "Running", "RUNNING_SUM(SUM(1.0))", table_calc="Columns"
    )
    expression = f"DISCRETE({grain}(Date))"
    editor.add_worksheet("Series")
    editor.configure_layered_chart(
        "Series",
        rows=[expression],
        panes=[{"axis": "Running", "mark_type": "Text"}],
        table_calc_overrides={
            "Running": [{"ordering_type": "Field", "order": [expression]}]
        },
    )
    editor.configure_worksheet_domain_range("Series", ["Date"])
    instance = editor.field_registry.parse_expression(expression)
    assert instance.instance_name.startswith(f"[{prefix}:")
    assert instance.instance_name.endswith(":ok]")
    assert instance.ci_type == "ordinal"
    continuous = editor.field_registry.parse_expression(f"{grain}(Date)")
    assert continuous.ci_type == "quantitative" and continuous.instance_name.endswith(
        ":qk]"
    )
    output = tmp_path / "discrete.twb"
    editor.save(str(output))
    tree = etree.parse(str(output))
    view = tree.find("worksheets/worksheet/table/view")
    native = view.find(
        f"datasource-dependencies/column-instance[@name='{instance.instance_name}']"
    )
    assert (
        native.get("type") == "ordinal"
        and native.get("derivation") == instance.derivation
    )
    assert instance.instance_name in tree.findtext("worksheets/worksheet/table/rows")
    assert instance.instance_name in view.find(
        "datasource-dependencies/column-instance/table-calc/order"
    ).get("field")
    assert tree.find("worksheets/worksheet/table/show-full-range") is not None


@pytest.mark.parametrize(
    "expression", ["DISCRETE(Date)", "DISCRETE(YEAR(Date))", "DISCRETE(SUM(Value))"]
)
def test_discrete_wrapper_rejects_nontruncation(expression):
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Date", "#2020-01-01#", datatype="date", role="dimension", field_type="ordinal"
    )
    editor.add_calculated_field("Value", "1.0")
    with pytest.raises(ValueError, match="date truncation"):
        editor.field_registry.parse_expression(expression)
