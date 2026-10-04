"""Addressing preserves temporal grains and distinguishes dimension ordering."""

import pytest

from cwtwb import TWBEditor


@pytest.mark.parametrize(
    "grain", ["YEAR", "MONTH", "DAYTRUNC", "MONTHTRUNC", "QUARTERTRUNC", "YEARTRUNC"]
)
def test_table_calc_order_retains_temporal_instance_grain(grain, tmp_path):
    e = TWBEditor("")
    e.add_calculated_field(
        "Observed Date",
        "#2020-01-01#",
        datatype="date",
        role="dimension",
        field_type="ordinal",
    )
    e.add_calculated_field("Metric", "1.0")
    e.add_calculated_field("Average", "WINDOW_AVG(SUM([Metric]))", table_calc="Columns")
    expression = f"{grain}(Observed Date)"
    e.add_worksheet("Line")
    e.configure_layered_chart(
        "Line",
        columns=[expression],
        panes=[{"axis": "Average", "mark_type": "Line"}],
        table_calc_overrides={
            "Average": [{"ordering_type": "Field", "order": [expression]}]
        },
    )
    order = e.root.find(".//column-instance/table-calc/order")
    ci = e.field_registry.parse_expression(expression)
    assert order.get("field") == e.field_registry.resolve_full_reference(
        ci.instance_name
    )
    assert e.root.find(f".//column-instance[@name='{ci.instance_name}']") is not None
    e.save(str(tmp_path / "temporal-address.twb"))


@pytest.mark.parametrize("aggregate", [False, True])
def test_ordering_field_uses_raw_dimension_and_bound_aggregate(aggregate, tmp_path):
    e = TWBEditor("")
    e.add_calculated_field(
        "Group", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Metric", "1.0")
    e.add_calculated_field("Rank", "RANK(SUM([Metric]))", table_calc="Rows")
    field = "SUM(Metric)" if aggregate else "Group"
    e.add_worksheet("Rank")
    e.configure_layered_chart(
        "Rank",
        rows=["Group"],
        panes=[{"axis": "Rank", "mark_type": "Bar", "tooltip": ["SUM(Metric)"]}],
        table_calc_overrides={
            "Rank": [{"ordering_type": "Field", "ordering_field": field}]
        },
    )
    native = e.root.find(".//column-instance/table-calc")
    ci = e.field_registry.parse_expression(field)
    expected = ci.instance_name if aggregate else ci.column_local_name
    assert native.get("ordering-field") == e.field_registry.resolve_full_reference(
        expected
    )
    e.save(str(tmp_path / "dimension-ordering.twb"))
