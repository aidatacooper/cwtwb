"""Synthetic public API regressions for patterned line feature declarations."""

import pytest
from lxml import etree

from cwtwb import TWBEditor
from cwtwb.validator import load_workbook_root, validate_against_schema


def synthetic_line():
    editor = TWBEditor("")
    editor.add_calculated_field("Value", "1.0", datatype="real")
    editor.add_worksheet("Line")
    return editor


@pytest.mark.parametrize("extension", [".twb", ".twbx"])
@pytest.mark.parametrize("pattern", ["solid", "dashed", "dotted"])
@pytest.mark.parametrize("style_api", ["layered", "worksheet", "panes"])
def test_patterned_line_manifest_on_save(tmp_path, extension, pattern, style_api):
    editor = synthetic_line()
    style = {"mark_line_pattern": pattern}
    pane = {"axis": "SUM(Value)", "mark_type": "Line"}
    if style_api == "layered":
        pane["mark_style"] = {"mark-line-pattern": pattern}
    editor.configure_layered_chart("Line", rows=["SUM(Value)"], panes=[pane])
    if style_api == "worksheet":
        editor.configure_worksheet_style("Line", pane_mark_style=style)
    elif style_api == "panes":
        pane_id = editor.root.find(".//panes/pane").get("id")
        editor.configure_worksheet_style(
            "Line", panes_style={pane_id: {"mark_style": style}}
        )

    output = tmp_path / f"patterned{extension}"
    editor.save(output)
    root = load_workbook_root(output)
    formats = root.findall(
        ".//style-rule[@element='mark']/format[@attr='mark-line-pattern']"
    )
    assert formats
    assert all(element.get("value") == pattern for element in formats)
    entries = root.findall("document-format-change-manifest/PatternedLineMarks")
    assert len(entries) == 1
    schema = validate_against_schema(root)
    assert schema.schema_available
    assert not schema.errors

    reopened = TWBEditor.open_existing(output)
    reopened.save(output)
    assert len(load_workbook_root(output).findall(
        "document-format-change-manifest/PatternedLineMarks"
    )) == 1


def test_unpatterned_line_does_not_add_manifest(tmp_path):
    editor = synthetic_line()
    editor.configure_layered_chart(
        "Line", rows=["SUM(Value)"],
        panes=[{"axis": "SUM(Value)", "mark_type": "Line",
                "trendline": {"fit": "linear"},
                "trendline_style": {"line-pattern-only": "dashed"}}],
    )
    output = tmp_path / "unpatterned.twb"
    editor.save(output)
    assert load_workbook_root(output).find(
        "document-format-change-manifest/PatternedLineMarks"
    ) is None


@pytest.mark.parametrize("representation", ["format", "attribute"])
def test_existing_patterned_workbook_reconciles_on_open(tmp_path, representation):
    editor = synthetic_line()
    editor.configure_layered_chart(
        "Line", rows=["SUM(Value)"],
        panes=[{"axis": "SUM(Value)", "mark_type": "Line"}],
    )
    output = tmp_path / "existing.twb"
    editor.save(output)
    root = load_workbook_root(output)
    if representation == "format":
        style = root.find(".//panes/pane/style")
        rule = etree.SubElement(style, "style-rule", element="mark")
        etree.SubElement(rule, "format", attr="mark-line-pattern", value="dashed")
    else:
        view = root.find(".//worksheet/table/view")
        etree.SubElement(view, "page-trail-options", **{"mark-line-pattern": "dotted"})
    etree.ElementTree(root).write(str(output), encoding="utf-8", xml_declaration=True)

    reopened = TWBEditor.open_existing(output)
    assert reopened.root.find(
        "document-format-change-manifest/PatternedLineMarks"
    ) is not None
    reopened.save(output)
    assert len(load_workbook_root(output).findall(
        "document-format-change-manifest/PatternedLineMarks"
    )) == 1
