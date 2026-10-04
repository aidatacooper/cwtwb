"""Author-free field-backed reference bands and endpoint validation."""

import pytest
from lxml import etree
from cwtwb import TWBEditor


def editor():
    e = TWBEditor("")
    e.add_calculated_field(
        "Category", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Value", "7")
    e.add_calculated_field(
        "Lower", "WINDOW_AVG(SUM([Value])) - WINDOW_STDEV(SUM([Value]))"
    )
    e.add_calculated_field(
        "Upper", "WINDOW_AVG(SUM([Value])) + WINDOW_STDEV(SUM([Value]))"
    )
    e.add_worksheet("Plot")
    e.configure_chart(
        "Plot", mark_type="Bar", columns=["SUM(Value)"], rows=["Category"]
    )
    return e


def band(e, **changes):
    options = dict(
        axis_field="SUM(Value)", lower_field="AGG(Lower)", upper_field="AGG(Upper)"
    )
    options.update(changes)
    return e.add_reference_band("Plot", **options)


def test_field_band_registers_dynamic_endpoints_and_survives_save(tmp_path):
    e = editor()
    band(e)
    lines = e.root.findall(".//reference-line")
    lower, upper = lines
    assert lower.get("formula") == "min" and upper.get("formula") == "max"
    assert all(line.get("value") is None for line in lines)
    assert lower.get("paired-id") == upper.get("id") and upper.get(
        "paired-id"
    ) == lower.get("id")
    assert lower.get("value-column") != upper.get("value-column")
    dependencies = e.root.find(".//worksheet/table/view/datasource-dependencies")
    assert (
        dependencies.find("column[@caption='Lower']/calculation")
        .get("formula")
        .startswith("WINDOW_AVG")
    )
    assert dependencies.find("column[@caption='Upper']/calculation") is not None
    for line in lines:
        reference = line.get("value-column").split("].", 1)[1]
        assert dependencies.find(f"column-instance[@name='{reference}']") is not None
    output = tmp_path / "band.twb"
    e.save(str(output))
    saved = etree.parse(str(output))
    assert saved.find(".//style-rule[@element='refband']/format").get(
        "id"
    ) == lower.get("id")
    assert all(line.get("value") is None for line in saved.findall(".//reference-line"))


@pytest.mark.parametrize(
    "changes",
    [
        {"lower_value": 1},
        {"upper_value": 3},
        {"lower_field": None},
        {"upper_field": None},
        {"lower_field": "Missing"},
        {"upper_field": "Missing"},
        {"lower_field": "Category"},
        {"upper_field": "Category"},
        {"lower_field": ""},
        {"upper_field": 3},
        {"lower_formula": "invalid"},
        {"upper_formula": "constant"},
    ],
)
def test_invalid_endpoints_preserve_workbook(changes):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises((ValueError, KeyError)):
        band(e, **changes)
    assert etree.tostring(e.root) == before


def test_mixed_constant_and_dynamic_endpoint():
    e = editor()
    band(e, lower_field=None, lower_value=0)
    lower, upper = e.root.findall(".//reference-line")
    assert lower.get("formula") == "constant" and lower.get("value") == "0"
    assert upper.get("formula") == "max" and upper.get("value") is None


def test_mcp_forwards_field_endpoint_options(monkeypatch):
    from cwtwb.mcp import tools_workbook

    e = editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    tools_workbook.add_reference_band(
        "Plot",
        "SUM(Value)",
        lower_field="AGG(Lower)",
        upper_field="AGG(Upper)",
        lower_formula="average",
    )
    assert e.root.find(".//reference-line").get("formula") == "average"


def test_run_spec_registers_field_backed_band():
    from cwtwb.commands.run_spec import _apply_worksheets

    e = editor()
    _apply_worksheets(
        e,
        {
            "worksheets": [
                {
                    "name": "Plot",
                    "mark_type": "Bar",
                    "columns": ["SUM(Value)"],
                    "rows": ["Category"],
                    "reference_bands": [
                        {
                            "axis_field": "SUM(Value)",
                            "lower_field": "AGG(Lower)",
                            "upper_field": "AGG(Upper)",
                        }
                    ],
                }
            ]
        },
    )
    assert len(e.root.findall(".//reference-line")) == 2


def test_band_preserves_synthetic_table_calculation_metadata():
    e = editor()
    column = e.root.find("datasources/datasource/column[@caption='Lower']")
    etree.SubElement(
        column.find("calculation"), "table-calc", ordering="Rows", aggregation="Sum"
    )
    band(e)
    dependency = e.root.find(".//worksheet/table/view/datasource-dependencies")
    instance = next(
        ci
        for ci in dependency.findall("column-instance")
        if ci.get("column") == column.get("name")
    )
    assert instance.find("table-calc").get("ordering") == "Rows"
    before = (
        dict(instance.attrib),
        [(child.tag, dict(child.attrib)) for child in instance],
    )
    band(e)
    dependency = e.root.find(".//worksheet/table/view/datasource-dependencies")
    instances = [
        ci
        for ci in dependency.findall("column-instance")
        if ci.get("column") == column.get("name")
    ]
    assert len(instances) == 1
    assert (
        dict(instances[0].attrib),
        [(child.tag, dict(child.attrib)) for child in instances[0]],
    ) == before
