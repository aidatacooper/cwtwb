import pytest

from cwtwb import TWBEditor


def test_rejects_multiple_top_level_field_addressing_specs():
    editor = TWBEditor("")
    editor.add_calculated_field("Running", "INDEX()", table_calc="Rows")
    editor.add_worksheet("Sequence")

    with pytest.raises(ValueError, match="one top-level Field"):
        editor.configure_layered_chart(
            "Sequence",
            rows=["Running"],
            panes=[{"axis": "Running", "mark_type": "Text"}],
            table_calc_overrides={
                "Running": [
                    {"ordering_type": "Field", "ordering_field": "Category"},
                    {"ordering_type": "Field", "ordering_field": "Region"},
                ]
            },
        )


def test_accepts_one_ordered_field_addressing_spec():
    editor = TWBEditor("")
    editor.add_calculated_field("Running", "INDEX()", table_calc="Rows")
    editor.add_worksheet("Sequence")
    editor.configure_layered_chart(
        "Sequence",
        rows=["Running"],
        panes=[{"axis": "Running", "mark_type": "Text"}],
        table_calc_overrides={
            "Running": [
                {"ordering_type": "Field", "order": ["Category", "Region"]}
            ]
        },
    )

    calculation = editor.root.find(
        ".//worksheet[@name='Sequence']//column-instance/table-calc"
    )
    assert calculation.get("ordering-type") == "Field"
    assert len(calculation.findall("order")) == 2
