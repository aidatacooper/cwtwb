"""Qualified custom parameter IDs must never become physical data fields."""

import pytest

from cwtwb import TWBEditor


@pytest.mark.parametrize("route", ["basic", "dual", "layered"])
def test_custom_parameter_dependency_stays_in_parameters_datasource(route, tmp_path):
    e = TWBEditor("")
    e.add_parameter(
        "Metric Choice",
        datatype="integer",
        default_value="1",
        internal_name="[ThresholdControl]",
    )
    e.add_calculated_field("Amount", "1.0")
    e.add_calculated_field(
        "Selected Amount", "IF [Metric Choice] = 1 THEN SUM([Amount]) ELSE 0 END"
    )
    e.add_calculated_field("Derived", "[Selected Amount] * 2")
    e.add_worksheet("Plot")
    if route == "layered":
        e.configure_layered_chart(
            "Plot", panes=[{"axis": "AGG(Derived)", "mark_type": "Bar"}]
        )
    elif route == "dual":
        e.configure_dual_axis("Plot", rows=["AGG(Derived)", "AGG(Selected Amount)"])
    else:
        e.configure_chart("Plot", rows=["AGG(Derived)"])
    dependencies = e.root.findall(
        "worksheets/worksheet/table/view/datasource-dependencies"
    )
    parameters = next(d for d in dependencies if d.get("datasource") == "Parameters")
    assert parameters.find("column[@name='[ThresholdControl]']") is not None
    for data in dependencies:
        if data is not parameters:
            assert data.find("column[@name='[ThresholdControl]']") is None
            assert data.find("column[@name='[Parameters]']") is None
    e.save(str(tmp_path / "custom-parameter.twb"))
