"""An explicit table-calc override must keep nested dependency metadata.

Passing ``table_calc_overrides`` for a calculated field used to replace every
``<table-calc>`` child on the worksheet ``<column-instance>``, including the
auto-generated nested dependency entries (``field="[ds].[Calculation_...]"``).
Those entries are what let Tableau resolve ``RUNNING_SUM``/``WINDOW_SUM``/
``LOOKUP`` across the sorted marks; without them the cumulative curve collapses
to a flat 100%.

Synthetic fixture only; no author data.
"""

from __future__ import annotations

import pytest

from cwtwb import TWBEditor

ADDRESSING = {"ordering_type": "Field", "ordering_field": "Order ID"}


def _editor() -> TWBEditor:
    editor = TWBEditor("")
    editor.add_calculated_field("Count Orders", "COUNTD([Order ID])", datatype="integer")
    editor.add_calculated_field(
        "Cumulative Order Count",
        "RUNNING_SUM([Count Orders])",
        datatype="integer",
        table_calc=ADDRESSING,
    )
    editor.add_calculated_field(
        "Total Order Count",
        "WINDOW_SUM([Count Orders])",
        datatype="integer",
        table_calc=ADDRESSING,
    )
    editor.add_calculated_field(
        "Cumulative Pct",
        "[Cumulative Order Count]/[Total Order Count]",
        datatype="real",
        table_calc=ADDRESSING,
    )
    editor.add_worksheet("Viz")
    return editor


def _own_and_nested(editor: TWBEditor, expression: str):
    instance = editor.field_registry.parse_expression(expression)
    ci = editor._find_worksheet("Viz").find(
        f".//datasource-dependencies/column-instance[@name='{instance.instance_name}']"
    )
    assert ci is not None
    entries = ci.findall("table-calc")
    own = [e for e in entries if not e.get("field")]
    nested = [e for e in entries if e.get("field")]
    return own, nested


def test_override_keeps_nested_table_calc_dependencies() -> None:
    editor = _editor()
    editor.configure_chart(
        "Viz",
        mark_type="Bar",
        rows=["Order ID"],
        columns=["Cumulative Pct"],
        table_calc_overrides={"Cumulative Pct": [dict(ADDRESSING)]},
    )

    own, nested = _own_and_nested(editor, "Cumulative Pct")
    assert len(own) == 1
    assert own[0].get("ordering-type") == "Field"
    # Two nested dependencies: Cumulative Order Count and Total Order Count.
    assert len(nested) == 2
    for entry in nested:
        assert entry.get("field", "").startswith("[federated.")
        assert entry.get("field", "").count("Calculation_") == 1


def test_override_entry_precedes_nested_dependencies() -> None:
    editor = _editor()
    editor.configure_chart(
        "Viz",
        mark_type="Bar",
        rows=["Order ID"],
        columns=["Cumulative Pct"],
        table_calc_overrides={"Cumulative Pct": [dict(ADDRESSING)]},
    )

    instance = editor.field_registry.parse_expression("Cumulative Pct")
    ci = editor._find_worksheet("Viz").find(
        f".//datasource-dependencies/column-instance[@name='{instance.instance_name}']"
    )
    entries = ci.findall("table-calc")
    assert entries[0].get("field") is None
    assert all(entry.get("field") for entry in entries[1:])


def test_without_override_auto_metadata_is_unchanged() -> None:
    editor = _editor()
    editor.configure_chart(
        "Viz",
        mark_type="Bar",
        rows=["Order ID"],
        columns=["Cumulative Pct"],
    )

    own, nested = _own_and_nested(editor, "Cumulative Pct")
    assert len(own) == 1
    assert len(nested) == 2


def test_override_is_idempotent(tmp_path) -> None:
    editor = _editor()
    options = {
        "mark_type": "Bar",
        "rows": ["Order ID"],
        "columns": ["Cumulative Pct"],
        "table_calc_overrides": {"Cumulative Pct": [dict(ADDRESSING)]},
    }
    for _ in range(2):
        editor.configure_chart("Viz", **options)

    own, nested = _own_and_nested(editor, "Cumulative Pct")
    assert len(own) == 1
    assert len(nested) == 2
    editor.save(str(tmp_path / "nested-metadata.twb"))
