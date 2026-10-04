"""Continuous date grains preserve years unlike discrete date-part shelves."""

import pytest

from cwtwb import TWBEditor
from cwtwb.field_registry import is_expression, looks_like_column_instance_name


@pytest.mark.parametrize("datatype", ["date", "datetime"])
@pytest.mark.parametrize(
    "function,derivation,prefix",
    [
        ("MONTHTRUNC", "Month-Trunc", "tmn"),
        ("QUARTERTRUNC", "Quarter-Trunc", "tqr"),
        ("YEARTRUNC", "Year-Trunc", "tyr"),
    ],
)
def test_continuous_date_shelves_keep_grain_and_quantitative_type(
    datatype, function, derivation, prefix, tmp_path
):
    e = TWBEditor("")
    e.add_calculated_field(
        "Report Date",
        "#2020-01-01#",
        datatype=datatype,
        role="dimension",
        field_type="ordinal",
    )
    e.add_calculated_field("Value", "1.0")
    expression = f"{function}(Report Date)"
    assert is_expression(expression)
    e.add_worksheet("Trend")
    e.configure_layered_chart(
        "Trend",
        columns=[expression],
        panes=[{"axis": "SUM(Value)", "mark_type": "Line"}],
    )
    instance = e.field_registry.parse_expression(expression)
    assert instance.derivation == derivation and instance.ci_type == "quantitative"
    assert instance.instance_name.startswith(f"[{prefix}:")
    assert looks_like_column_instance_name(instance.instance_name)
    with pytest.raises(ValueError, match="generated"):
        e.field_registry.parse_expression(instance.instance_name)
    native = e.root.find(
        f"worksheets/worksheet/table/view/datasource-dependencies/column-instance[@name='{instance.instance_name}']"
    )
    assert (
        native.get("derivation") == derivation and native.get("type") == "quantitative"
    )
    e.save(str(tmp_path / "dates.twb"))


@pytest.mark.parametrize("function", ["MONTHTRUNC", "QUARTERTRUNC", "YEARTRUNC"])
def test_numeric_fields_cannot_use_date_truncation(function):
    e = TWBEditor("")
    e.add_calculated_field("Value", "1.0")
    with pytest.raises(ValueError, match="date or datetime"):
        e.field_registry.parse_expression(f"{function}(Value)")
