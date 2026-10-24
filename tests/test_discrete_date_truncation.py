"""Discrete date truncations retain native date-domain completion."""

import pytest
from lxml import etree

from cwtwb import TWBEditor
from cwtwb.validator import validate_against_schema


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
    "expression", ["DISCRETE(Date)", "DISCRETE(YEAR(Date))"]
)
def test_discrete_wrapper_rejects_nontruncation(expression):
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Date", "#2020-01-01#", datatype="date", role="dimension", field_type="ordinal"
    )
    editor.add_calculated_field("Value", "1.0")
    with pytest.raises(ValueError, match="date truncation or aggregate"):
        editor.field_registry.parse_expression(expression)


@pytest.mark.parametrize(
    "aggregate,derivation,prefix",
    [
        ("SUM", "Sum", "sum"),
        ("AVG", "Avg", "avg"),
        ("MIN", "Min", "min"),
        ("MAX", "Max", "max"),
        ("MEDIAN", "Median", "med"),
        ("COUNT", "Count", "cnt"),
        ("COUNTD", "CountD", "cntd"),
        ("ATTR", "Attribute", "attr"),
    ],
)
def test_discrete_aggregate_preserves_native_derivation(
    aggregate, derivation, prefix, tmp_path
):
    baseline = TWBEditor("")
    baseline.add_worksheet("Headers")
    baseline.configure_chart(
        "Headers",
        mark_type="Text",
        rows=[f"{aggregate}(Sales)"],
        label="Category",
    )

    editor = TWBEditor("")
    editor.add_worksheet("Headers")
    expression = f"DISCRETE({aggregate}(Sales))"

    editor.configure_chart(
        "Headers",
        mark_type="Text",
        rows=[expression],
        label="Category",
    )

    instance = editor.field_registry.parse_expression(expression)
    assert instance.derivation == derivation
    assert instance.ci_type == "ordinal"
    assert instance.instance_name.startswith(f"[{prefix}:")
    assert instance.instance_name.endswith(":ok]")
    native = editor.root.find(
        ".//worksheet[@name='Headers']//datasource-dependencies/column-instance"
        f"[@name='{instance.instance_name}']"
    )
    assert native is not None
    assert native.get("derivation") == derivation
    assert native.get("type") == "ordinal"
    assert instance.instance_name in editor.root.findtext(
        ".//worksheet[@name='Headers']/table/rows"
    )
    assert validate_against_schema(editor.root).errors == validate_against_schema(
        baseline.root
    ).errors
    if aggregate == "SUM":
        output = tmp_path / "discrete-aggregate.twb"
        editor.save(output)
        assert validate_against_schema(etree.parse(str(output)).getroot()).errors == []
