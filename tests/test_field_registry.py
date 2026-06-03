"""Tests for FieldRegistry lookup and unknown-field behavior."""

from __future__ import annotations

import logging

import pytest

from cwtwb.field_registry import FieldRegistry
from cwtwb.field_registry import default_measure_expression, default_view_expression


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
