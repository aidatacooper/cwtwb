"""Regression: bare ``PERCENTILE(expr, number)`` fields are aggregates.

A calculated field whose formula is a bare ``PERCENTILE(...)`` must register as
a measure with ``User`` column-instance derivation, not as an unknown dimension
that renders an empty pane. Synthetic fixture only; no author data.
"""

from __future__ import annotations

import pytest

from cwtwb import TWBEditor
from cwtwb.validator import validate_workbook_file


@pytest.fixture
def editor():
    return TWBEditor("")


def test_percentile_expression_registers_user_derivation(editor):
    editor.add_calculated_field(
        "Lower Quartile",
        "PERCENTILE([Sales],0.25)",
        datatype="real",
        role="measure",
        field_type="quantitative",
    )

    instance = editor.field_registry.parse_expression("Lower Quartile")
    assert instance.derivation == "User"
    assert instance.ci_type == "quantitative"
    assert instance.instance_name.startswith("[usr:Calculation_")
    assert instance.instance_name.endswith(":qk]")


def test_percentile_field_binds_user_instance_on_shelf(editor):
    editor.add_calculated_field(
        "Lower Quartile",
        "PERCENTILE([Sales],0.25)",
        datatype="real",
        role="measure",
        field_type="quantitative",
    )
    editor.add_worksheet("Quartiles")
    editor.configure_chart(
        "Quartiles",
        mark_type="Bar",
        rows=["Category"],
        columns=["Lower Quartile"],
    )

    worksheet = editor._find_worksheet("Quartiles")
    dependencies = worksheet.find(".//datasource-dependencies")
    assert dependencies is not None

    column = dependencies.find(
        "column[@caption='Lower Quartile']"
    )
    assert column is not None
    local_name = column.get("name")

    instance = dependencies.find(f"column-instance[@column='{local_name}']")
    assert instance is not None
    assert instance.get("derivation") == "User"
    assert instance.get("name").startswith("[usr:")

    cols = worksheet.find(".//cols").text
    assert instance.get("name") in cols


def test_percentile_second_argument_is_not_treated_as_field(editor):
    """The numeric percentile argument must not be parsed as a field name."""

    editor.add_calculated_field(
        "Upper Quartile",
        "PERCENTILE([Sales], 0.75)",
        datatype="real",
        role="measure",
        field_type="quantitative",
    )

    instance = editor.field_registry.parse_expression("Upper Quartile")
    assert instance.derivation == "User"
    assert instance.column_local_name == editor.field_registry._find_field(
        "Upper Quartile"
    ).local_name


def test_percentile_workbook_saves_and_validates(editor, tmp_path):
    editor.add_calculated_field(
        "Lower Quartile",
        "PERCENTILE([Sales],0.25)",
        datatype="real",
        role="measure",
        field_type="quantitative",
    )
    editor.add_worksheet("Quartiles")
    editor.configure_chart(
        "Quartiles",
        mark_type="Bar",
        rows=["Category"],
        columns=["Lower Quartile"],
    )

    output = tmp_path / "percentile.twb"
    editor.save(output)
    validate_workbook_file(str(output))
