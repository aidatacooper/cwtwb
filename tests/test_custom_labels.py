"""Synthetic regressions for labels on existing panes and calculation contexts."""

import inspect

import pytest
from lxml import etree

from cwtwb import TWBEditor


def build_editor():
    editor = TWBEditor("")
    editor.add_calculated_field("Anchor", "MIN(0)")
    editor.add_calculated_field(
        "Window Total", "WINDOW_SUM(SUM([Sales]))", table_calc="Rows"
    )
    editor.add_worksheet("Synthetic")
    editor.configure_layered_chart(
        "Synthetic",
        rows=["Category"],
        columns=["Anchor"],
        axis_shelf="columns",
        panes=[{"axis": "Anchor", "mark_type": "Text", "labels": ["Window Total"]}],
        table_calc_context=True,
        table_calc_overrides={
            "Window Total": [{"ordering_type": "Field", "order": ["Category"]}]
        },
    )
    editor.configure_custom_tooltip("Synthetic", [{"text": "Keep tooltip"}])
    return editor


def test_rich_label_keeps_context_and_tooltip_and_is_idempotent(tmp_path):
    editor = build_editor()
    worksheet = editor.root.find(".//worksheet[@name='Synthetic']")
    contextual = worksheet.find(".//pane/encodings/text").get("column")
    before_tooltip = etree.tostring(worksheet.find(".//customized-tooltip"))
    before_calc = etree.tostring(worksheet.find(".//column-instance/table-calc"))
    specification = [
        {"text": "TOTAL", "fontname": "Times New Roman", "fontsize": 16, "bold": True},
        {"text": "\n"},
        {
            "field": "Window Total",
            "fontsize": 16,
            "fontcolor": "#123456",
            "italic": True,
        },
        {"text": " HOURS", "fontsize": 9, "fontalignment": "2", "underline": False},
    ]
    editor.configure_custom_label("Synthetic", specification)
    first = etree.tostring(editor.root)
    editor.configure_custom_label("Synthetic", specification)
    assert etree.tostring(editor.root) == first
    worksheet = editor.root.find(".//worksheet[@name='Synthetic']")
    runs = worksheet.findall(".//customized-label/formatted-text/run")
    assert runs[2].text == f"<{contextual}>"
    assert runs[1].text == "\u00c6\n"
    assert runs[2].get("italic") == "true"
    assert runs[3].get("underline") == "false"
    assert etree.tostring(worksheet.find(".//customized-tooltip")) == before_tooltip
    assert (
        etree.tostring(worksheet.find(".//column-instance/table-calc")) == before_calc
    )
    dependency = worksheet.find(".//column-instance[table-calc]")
    assert (
        len(
            worksheet.findall(
                f".//column-instance[@column='{dependency.get('column')}']"
            )
        )
        == 1
    )
    output = tmp_path / "label.twb"
    editor.save(str(output))
    assert contextual in etree.parse(str(output)).findtext(
        ".//customized-label/formatted-text/run[3]"
    )


def test_new_label_registers_recursive_dependencies_and_text_encoding():
    editor = build_editor()
    editor.add_calculated_field("Late Intermediate", "SUM([Profit])+SUM([Sales])")
    editor.add_calculated_field("Late Label", "[Late Intermediate]*2")
    editor.configure_custom_label("Synthetic", [{"field": "Late Label", "prefix": "$"}])
    worksheet = editor.root.find(".//worksheet[@name='Synthetic']")
    captions = {
        column.get("caption")
        for column in worksheet.findall(".//datasource-dependencies/column")
    }
    assert {"Late Label", "Late Intermediate"} <= captions
    profit = editor.field_registry.parse_expression("SUM(Profit)").column_local_name
    assert (
        worksheet.find(f".//datasource-dependencies/column[@name='{profit}']")
        is not None
    )
    label_reference = worksheet.findtext(".//customized-label/formatted-text/run")
    assert label_reference.startswith("$<[federated.")
    assert any(
        node.get("column") in label_reference
        for node in worksheet.findall(".//pane/encodings/text")
    )


def test_native_dual_zero_based_pane_index_preserves_other_panes():
    editor = TWBEditor("")
    editor.add_worksheet("Dual")
    editor.configure_dual_axis("Dual", rows=["SUM(Sales)", "SUM(Profit)"])
    panes = editor.root.findall(".//worksheet[@name='Dual']/table/panes/pane")
    before = etree.tostring(panes[2])
    editor.configure_custom_label(
        "Dual", [{"field": "SUM(Sales)", "fontsize": 16}], pane_index=1
    )
    panes = editor.root.findall(".//worksheet[@name='Dual']/table/panes/pane")
    assert panes[0].get("id") is None
    assert panes[0].find("customized-label") is None
    assert panes[1].find("customized-label") is not None
    assert etree.tostring(panes[2]) == before


@pytest.mark.parametrize(
    "runs,pane_index",
    [
        ([], 0),
        ([{"text": "x", "field": "Sales"}], 0),
        ([{"sheet": {"name": "No"}}], 0),
        ([{"text": 42}], 0),
        ([{"field": ""}], 0),
        ([{"text": "x", "fontsize": 0}], 0),
        ([{"text": "x", "fontsize": "nan"}], 0),
        ([{"text": "x", "font_size": 16}], 0),
        ([{"text": "x", "bold": "true"}], 0),
        ([{"text": "x"}], -1),
        ([{"text": "x"}], 99),
        ([{"text": "x"}], True),
        ([{"text": "x"}], 0.5),
        ([{"field": "No Such Registered Field"}], 0),
        ([{"field": "SUM(Sales)"}, {"field": "Unknown"}], 0),
    ],
)
def test_invalid_requests_are_atomic(runs, pane_index):
    editor = build_editor()
    before = etree.tostring(editor.root)
    with pytest.raises((ValueError, KeyError)):
        editor.configure_custom_label("Synthetic", runs, pane_index=pane_index)
    assert etree.tostring(editor.root) == before


def test_mcp_and_run_spec_forward_pane_and_runs(monkeypatch):
    from cwtwb.commands.run_spec import _apply_worksheets
    from cwtwb.mcp import tools_workbook

    editor = build_editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: editor)
    tools_workbook.configure_custom_label("Synthetic", [{"text": "MCP"}], pane_index=0)
    assert editor.root.findtext(".//customized-label/formatted-text/run") == "MCP"
    _apply_worksheets(
        editor,
        {
            "worksheets": [
                {
                    "name": "Spec",
                    "mark": "Text",
                    "rows": ["Category"],
                    "custom_labels": [
                        {
                            "runs": [{"field": "SUM(Sales)", "fontsize": 9}],
                            "pane_index": 0,
                        }
                    ],
                }
            ]
        },
    )
    assert editor.root.find(".//worksheet[@name='Spec']//customized-label") is not None
    assert (
        inspect.signature(TWBEditor.configure_custom_label)
        .parameters["pane_index"]
        .kind
        == inspect.Parameter.KEYWORD_ONLY
    )
