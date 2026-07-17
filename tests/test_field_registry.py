"""Tests for FieldRegistry lookup and unknown-field behavior."""

from __future__ import annotations

import logging

import pytest

from cwtwb.field_registry import FieldRegistry
from cwtwb.field_registry import (
    default_measure_expression,
    default_view_expression,
    looks_like_column_instance_name,
)


def _build_registry(*, allow_unknown_fields: bool = False) -> FieldRegistry:
    registry = FieldRegistry("federated.test", allow_unknown_fields=allow_unknown_fields)
    registry.register(
        display_name="Category",
        local_name="[Category (Orders)]",
        datatype="string",
        role="dimension",
        field_type="nominal",
    )
    registry.register(
        display_name="Sales",
        local_name="[Sales (Orders)]",
        datatype="real",
        role="measure",
        field_type="quantitative",
    )
    return registry


def test_parse_expression_raises_for_unknown_field_by_default() -> None:
    registry = _build_registry()

    with pytest.raises(KeyError, match="Unknown field 'Unknown Metric'"):
        registry.parse_expression("Unknown Metric")


def test_set_unknown_field_policy_allows_legacy_autoregistration(caplog: pytest.LogCaptureFixture) -> None:
    registry = _build_registry()
    registry.set_unknown_field_policy(allow_unknown_fields=True)

    with caplog.at_level(logging.WARNING):
        ci = registry.parse_expression("Gross Amount")

    field = registry.get("Gross Amount")
    assert field is not None
    assert field.local_name == "[Gross Amount]"
    assert field.role == "measure"
    assert field.field_type == "quantitative"
    assert ci.instance_name == "[none:Gross Amount:qk]"
    assert "Auto-registered unknown field 'Gross Amount'" in caplog.text


def test_case_insensitive_lookup_still_works() -> None:
    registry = _build_registry()

    ci = registry.parse_expression("SUM(sales)")
    assert ci.column_local_name == "[Sales (Orders)]"
    assert ci.derivation == "Sum"


def test_date_like_measures_preserve_date_binding_not_sum() -> None:
    assert default_measure_expression("Order Date") == "MONTH(Order Date)"
    assert default_measure_expression("YEAR(Order Date)") == "YEAR(Order Date)"
    assert default_view_expression("Order Date", role="measure") == "MONTH(Order Date)"
    assert default_view_expression("YEAR(Order Date)", role="measure") == "YEAR(Order Date)"


def test_column_instance_names_are_rejected_as_user_expressions() -> None:
    registry = _build_registry(allow_unknown_fields=True)

    copied_from_reference_twb = (
        "sum:Number of Tasks:qk",
        "[sum:Number of Tasks:qk]",
        "[federated.test].[sum:Number of Tasks:qk]",
        "[sum:Calculation_5C4D6E84CFF94328944FB4E96F3388D1:qk]",
        "[avg:Calculation_AE65EE94E7904542848145621864194A:qk]",
        "[mn:Calculation_7233B4F87A9E44CC95DA97DDDA414443:ok]",
        "[none:Task Status:nk]",
        "[none:Zone name:nk]",
        "[attr:Task Status:nk]",
        "[usr:Calculation_ABCDEF123456:qk]",
        "[sum:Sales:qk:1]",
        "[federated.0ahyg8e1xelf3914bag3r0yukuro].[avg:Calculation_AE65EE94E7904542848145621864194A:qk]",
        "[federated.0ahyg8e1xelf3914bag3r0yukuro].[mn:Calculation_7233B4F87A9E44CC95DA97DDDA414443:ok]",
        "[federated.0ahyg8e1xelf3914bag3r0yukuro].[none:Task Status:nk]",
    )

    for expr in copied_from_reference_twb:
        assert looks_like_column_instance_name(expr)
        with pytest.raises(ValueError, match="column-instance"):
            registry.parse_expression(expr)


def test_column_instance_names_are_rejected_inside_aggregations() -> None:
    registry = _build_registry(allow_unknown_fields=True)

    for expr in (
        "SUM([sum:Number of Tasks:qk])",
        "AVG([avg:Calculation_AE65EE94E7904542848145621864194A:qk])",
        "SUM([federated.0ahyg8e1xelf3914bag3r0yukuro].[sum:Calculation_5C4D6E84CFF94328944FB4E96F3388D1:qk])",
    ):
        with pytest.raises(ValueError, match="column-instance"):
            registry.parse_expression(expr)
