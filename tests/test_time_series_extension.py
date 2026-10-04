"""Author-free native date-domain extension and densified calculation contracts."""

import pytest
from lxml import etree

from cwtwb import TWBEditor
from cwtwb.time_series import configure_worksheet_time_series


def make():
    editor = TWBEditor("")
    editor.add_calculated_field(
        "Date",
        "MAKEDATE(2020,1,1)",
        datatype="date",
        role="dimension",
        field_type="ordinal",
    )
    editor.add_calculated_field(
        "Other Date",
        "MAKEDATE(2021,1,1)",
        datatype="date",
        role="dimension",
        field_type="ordinal",
    )
    editor.add_calculated_field("Value", "1.0")
    editor.add_worksheet("Series")
    editor.configure_chart(
        "Series", mark_type="Line", columns=["YEARTRUNC(Date)"], rows=["SUM(Value)"]
    )
    return editor


def configure(editor, **changes):
    settings = {"worksheet_name": "Series", "field": "YEARTRUNC(Date)", "periods": 5}
    settings.update(changes)
    return configure_worksheet_time_series(editor, **settings)


def test_extension_binds_base_date_and_keeps_continuous_shelf(tmp_path):
    editor = make()
    before = editor.root.findtext(".//worksheet/table/cols")
    configure(editor)
    table = editor.root.find(".//worksheet/table")
    column = table.find("extend-time-series/extended-column")
    local_name = editor.field_registry._find_field("Date").local_name
    assert column.get("column") == editor.field_registry.resolve_full_reference(
        local_name
    )
    assert column.get("num-periods") == "5" and column.get("period-type") == "year"
    assert table.findtext("cols") == before
    assert table.find("view/calcs-on-densified-marks").get("value") == "true"
    assert (
        editor.root.find("document-format-change-manifest/ExtendTimeSeries") is not None
    )
    assert (
        editor.root.find(
            "document-format-change-manifest/AllowCalculationsForDensifiedMarks"
        )
        is not None
    )
    editor.save(tmp_path / "series.twb")
    saved = etree.parse(str(tmp_path / "series.twb"))
    assert saved.find(".//extend-time-series/extended-column").get("num-periods") == "5"


def test_bare_date_update_is_idempotent_and_supports_false():
    editor = make()
    configure(editor)
    configure(
        editor,
        field="Date",
        periods=2,
        period_type="month",
        calculations_on_densified_marks=False,
    )
    assert len(editor.root.findall(".//extend-time-series/extended-column")) == 1
    column = editor.root.find(".//extend-time-series/extended-column")
    assert column.get("num-periods") == "2" and column.get("period-type") == "month"
    assert editor.root.find(".//calcs-on-densified-marks").get("value") == "false"


@pytest.mark.parametrize(
    "changes",
    [
        {"periods": True},
        {"periods": 0},
        {"periods": -1},
        {"periods": 1.5},
        {"periods": "5"},
        {"period_type": "fortnight"},
        {"period_type": None},
        {"calculations_on_densified_marks": "true"},
        {"field": ""},
        {"field": "Value"},
        {"field": "Other Date"},
        {"worksheet_name": "Missing"},
    ],
)
def test_invalid_settings_do_not_modify_workbook(changes):
    editor = make()
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError):
        configure(editor, **changes)
    assert etree.tostring(editor.root) == before


def test_two_date_extensions_preserve_each_other():
    editor = make()
    editor.configure_chart(
        "Series",
        mark_type="Line",
        columns=["YEARTRUNC(Date)"],
        rows=["MONTHTRUNC(Other Date)", "SUM(Value)"],
    )
    configure(editor)
    configure(editor, field="MONTHTRUNC(Other Date)", periods=3, period_type="month")
    assert len(editor.root.findall(".//extend-time-series/extended-column")) == 2


def test_discrete_date_is_rejected_atomically():
    editor = make()
    editor.configure_chart(
        "Series", mark_type="Line", columns=["YEAR(Date)"], rows=["SUM(Value)"]
    )
    before = etree.tostring(editor.root)
    with pytest.raises(ValueError, match="continuous shelf"):
        configure(editor)
    assert etree.tostring(editor.root) == before


def test_public_facade_and_mcp_forwarding(monkeypatch):
    from cwtwb.mcp import tools_workbook

    editor = make()
    editor.configure_worksheet_time_series("Series", "Date", 4)
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_worksheet_time_series(
        "Series",
        "YEARTRUNC(Date)",
        2,
        period_type="quarter",
        calculations_on_densified_marks=False,
    )
    column = editor.root.find(".//extend-time-series/extended-column")
    assert column.get("num-periods") == "2" and column.get("period-type") == "quarter"
    assert editor.root.find(".//calcs-on-densified-marks").get("value") == "false"


def test_run_spec_time_series_option():
    from cwtwb.commands.run_spec import _apply_worksheets

    editor = make()
    _apply_worksheets(
        editor,
        {
            "worksheets": [
                {
                    "name": "Series",
                    "mark": "Line",
                    "columns": ["YEARTRUNC(Date)"],
                    "rows": ["SUM(Value)"],
                    "time_series": {
                        "field": "Date",
                        "periods": 3,
                        "period_type": "month",
                    },
                }
            ]
        },
    )
    column = editor.root.find(".//extend-time-series/extended-column")
    assert column.get("num-periods") == "3" and column.get("period-type") == "month"


@pytest.mark.parametrize("tooltip", [False, True])
def test_native_schema_order_adds_no_errors_to_synthetic_baseline(tooltip):
    from cwtwb.validator import validate_against_schema

    editor = make()
    if tooltip:
        editor.configure_worksheet_style("Series", disable_tooltip=True)
    baseline = validate_against_schema(editor.root)
    if not baseline.schema_available:
        pytest.skip("Vendored Tableau schema unavailable")
    editor.configure_worksheet_time_series("Series", "Date", 5)
    after = validate_against_schema(editor.root)
    assert after.errors == baseline.errors
    table = editor.root.find(".//worksheet/table")
    tags = [child.tag for child in table]
    assert tags.index("extend-time-series") > tags.index("cols")
    if tooltip:
        assert tags.index("extend-time-series") < tags.index("tooltip-style")
    assert [child.tag for child in table.find("view")][-2:] == [
        "aggregation",
        "calcs-on-densified-marks",
    ]
