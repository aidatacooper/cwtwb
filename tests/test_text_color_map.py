from lxml import etree

from cwtwb import TWBEditor
from cwtwb.validator import validate_against_schema


def test_text_chart_serializes_requested_color_map(tmp_path):
    baseline = TWBEditor("")
    baseline.add_calculated_field(
        "Flag",
        "SUM([Sales]) > 0",
        datatype="boolean",
        role="dimension",
        field_type="nominal",
    )
    baseline.add_worksheet("Labels")
    baseline.configure_chart(
        "Labels",
        mark_type="Text",
        rows=["Category"],
        label="Category",
        color="Flag",
    )

    editor = TWBEditor("")
    editor.add_calculated_field(
        "Flag",
        "SUM([Sales]) > 0",
        datatype="boolean",
        role="dimension",
        field_type="nominal",
    )
    editor.add_worksheet("Labels")
    editor.configure_chart(
        "Labels",
        mark_type="Text",
        rows=["Category"],
        label="Category",
        color="Flag",
        color_map={True: "#00aa00", False: "#aa0000"},
    )

    instance = editor.field_registry.parse_expression("Flag")
    palette = editor.root.find(
        ".//datasource/style/style-rule[@element='mark']/encoding"
        f"[@attr='color'][@field='{instance.instance_name}']"
    )
    assert palette is not None
    assert {
        mapping.findtext("bucket"): mapping.get("to")
        for mapping in palette.findall("map")
    } == {"true": "#00aa00", "false": "#aa0000"}

    color = editor.root.find(
        ".//worksheet[@name='Labels']//pane/encodings/color"
    )
    assert color is not None
    assert color.get("column").endswith(f".{instance.instance_name}")
    assert validate_against_schema(editor.root).errors == validate_against_schema(
        baseline.root
    ).errors
    output = tmp_path / "text-color-map.twb"
    editor.save(output)
    assert validate_against_schema(etree.parse(str(output)).getroot()).errors == []
