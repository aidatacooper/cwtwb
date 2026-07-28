from pathlib import Path

import pytest

from cwtwb.mcp import tools_workbook
from cwtwb.twb_editor import TWBEditor


def _superstore_editor() -> TWBEditor:
    template = Path(__file__).parents[1] / "src" / "cwtwb" / "references" / "superstore.twb"
    return TWBEditor(str(template))


def _calculation(editor: TWBEditor, caption: str):
    return editor.root.find(f".//datasource/column[@caption='{caption}']/calculation")


def _column_instance(editor: TWBEditor, worksheet: str, column_local_name: str):
    ws = editor._find_worksheet(worksheet)
    return ws.find(
        f".//datasource-dependencies/column-instance[@column='{column_local_name}']"
    )


def test_table_calculation_rows_propagates_to_column_instance():
    editor = _superstore_editor()
    editor.add_calculated_field(
        "Moving Average",
        "WINDOW_AVG(SUM([Sales]), -2, 0)",
        table_calc="Rows",
    )
    editor.add_worksheet("Moving Average")
    editor.configure_chart(
        "Moving Average",
        mark_type="Line",
        columns=["Order Date"],
        rows=["Moving Average"],
    )

    calculation = _calculation(editor, "Moving Average")
    source_tc = calculation.find("table-calc")
    local_name = calculation.getparent().get("name")
    instance = _column_instance(editor, "Moving Average", local_name)
    instance_tc = instance.find("table-calc")

    assert source_tc.get("ordering-type") == "Rows"
    assert instance_tc.get("ordering-type") == "Rows"


def test_table_calculation_mapping_accepts_python_style_attributes():
    editor = _superstore_editor()
    editor.add_calculated_field(
        "Rank by Date",
        "RANK_DENSE(SUM([Sales]))",
        datatype="integer",
        table_calc={
            "ordering_type": "Field",
            "ordering_field": "[Sample - Superstore].[Order Date]",
            "rank_options": "Competition",
        },
    )

    table_calc = _calculation(editor, "Rank by Date").find("table-calc")
    assert table_calc.attrib == {
        "ordering-type": "Field",
        "ordering-field": "[Sample - Superstore].[Order Date]",
        "rank-options": "Competition",
    }


def test_nested_table_calculation_dependency_is_emitted():
    editor = _superstore_editor()
    editor.add_calculated_field(
        "Latest Date",
        "WINDOW_MAX(MAX([Order Date]))",
        datatype="date",
        table_calc="Rows",
        internal_name="[Calculation_LatestDate]",
    )
    editor.add_calculated_field(
        "Date to Display",
        "MIN([Order Date]) > DATEADD('month', -24, [Latest Date])",
        datatype="boolean",
        table_calc="Rows",
        internal_name="[Calculation_DateToDisplay]",
    )
    editor.add_worksheet("Moving Average")
    editor.configure_chart(
        "Moving Average",
        mark_type="Line",
        columns=["Order Date"],
        rows=["Sales"],
        filters=[
            {
                "column": "Date to Display",
                "type": "categorical",
                "values": [True],
            }
        ],
    )

    instance = _column_instance(
        editor,
        "Moving Average",
        "[Calculation_DateToDisplay]",
    )
    table_calcs = instance.findall("table-calc")

    assert table_calcs[0].attrib == {"ordering-type": "Rows"}
    assert table_calcs[1].get("ordering-type") == "Rows"
    assert table_calcs[1].get("field", "").endswith(".[Calculation_LatestDate]")


def test_table_calculation_survives_save_and_reopen(tmp_path):
    editor = _superstore_editor()
    editor.add_calculated_field(
        "Moving Average",
        "WINDOW_AVG(SUM([Sales]), -2, 0)",
        table_calc="Rows",
    )
    editor.add_worksheet("Moving Average")
    editor.configure_chart(
        "Moving Average",
        mark_type="Line",
        columns=["Order Date"],
        rows=["Moving Average"],
    )
    local_name = _calculation(editor, "Moving Average").getparent().get("name")
    output = tmp_path / "table-calculation.twb"
    editor.save(str(output))

    reopened = TWBEditor.open_existing(output)
    calculation = _calculation(reopened, "Moving Average")
    instance = _column_instance(reopened, "Moving Average", local_name)

    assert calculation.find("table-calc").get("ordering-type") == "Rows"
    assert instance.find("table-calc").get("ordering-type") == "Rows"


@pytest.mark.parametrize("ordering_type", ["Sideways", "", "rows"])
def test_invalid_table_calculation_ordering_type_is_rejected(ordering_type):
    editor = _superstore_editor()
    with pytest.raises(ValueError, match="table_calc"):
        editor.add_calculated_field(
            "Bad Table Calc",
            "WINDOW_SUM(SUM([Sales]))",
            table_calc=ordering_type,
        )


def test_mcp_add_calculated_field_exposes_table_calculation(monkeypatch):
    editor = _superstore_editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)

    tools_workbook.add_calculated_field(
        "Moving Average",
        "WINDOW_AVG(SUM([Sales]), -2, 0)",
        table_calc={"ordering_type": "Rows"},
    )

    table_calc = _calculation(editor, "Moving Average").find("table-calc")
    assert table_calc.get("ordering-type") == "Rows"


def test_dynamic_moving_average_case_matches_reference_metadata():
    """The first Donna Coles pilot requires Rows ordering on both calculations."""

    editor = _superstore_editor()
    editor.add_parameter(
        "pMoveAvg",
        datatype="integer",
        default_value="3",
        domain_type="range",
        min_value="3",
        max_value="12",
        granularity="3",
    )
    editor.add_calculated_field(
        "Moving Average",
        "WINDOW_AVG(SUM([Sales]), -1*([pMoveAvg]-1), 0)",
        table_calc="Rows",
    )
    editor.add_calculated_field(
        "Latest Date",
        "WINDOW_MAX(MAX([Order Date]))",
        datatype="date",
        table_calc="Rows",
    )

    assert _calculation(editor, "Moving Average").find("table-calc").attrib == {
        "ordering-type": "Rows"
    }
    assert _calculation(editor, "Latest Date").find("table-calc").attrib == {
        "ordering-type": "Rows"
    }
