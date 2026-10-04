"""Explicit worksheet calculation contexts bind every consumer consistently."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def editor():
    e = TWBEditor("")
    e.add_calculated_field(
        "District", "'A'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_calculated_field("Metric", "1.0")
    e.add_calculated_field(
        "Percentile", "RANK_PERCENTILE(SUM([Metric]))", table_calc="Columns"
    )
    e.add_worksheet("Map")
    return e


@pytest.mark.parametrize("measure_values", [False, True])
def test_contextual_instances_are_local_and_all_consumers_bind_them(
    measure_values, tmp_path
):
    e = editor()
    base = e.field_registry.parse_expression("Percentile").instance_name
    pane = {
        "mark_type": "Circle",
        "detail": "District",
        "color": "Percentile",
        "mark_style": {"mark-labels-range-field": "Percentile"},
    }
    if measure_values:
        pane.update(
            mark_type="Text",
            label="Multiple Values",
            measure_values=["Percentile", "SUM(Metric)"],
        )
    options = {
        "panes": [pane],
        "table_calc_context": True,
        "table_calc_overrides": {
            "Percentile": [{"ordering_type": "Field", "order": ["District"]}]
        },
    }
    e.configure_layered_chart("Map", **options)
    e.configure_layered_chart("Map", **options)
    native = e.root.find("worksheets/worksheet/table/view/datasource-dependencies")
    ci = next(
        ci
        for ci in native.findall("column-instance")
        if ci.get("column")
        == e.field_registry.parse_expression("Percentile").column_local_name
    )
    assert ci.get("name") == base[:-1] + ":1]"
    assert ci.find("table-calc").get("ordering-type") == "Field"
    reference = e.field_registry.resolve_full_reference(ci.get("name"))
    assert e.root.find(".//panes/pane/encodings/color").get("column") == reference
    assert (
        e.root.find(
            ".//panes/pane/style/style-rule/format[@attr='mark-labels-range-field']"
        ).get("value")
        == reference
    )
    assert e.field_registry.parse_expression("Percentile").instance_name == base
    e.configure_worksheet_style(
        "Map", color_style={"field": "Percentile", "palette": "green_gold_10_0"}
    )
    assert (
        e.root.find(".//table/style/style-rule/encoding[@attr='color']").get("field")
        == reference
    )
    e.add_dashboard(
        "Dashboard",
        width=400,
        height=300,
        layout={
            "type": "vertical",
            "children": [
                {"type": "worksheet", "name": "Map"},
                {
                    "type": "color",
                    "field": "Percentile",
                    "worksheet": "Map",
                    "pane_index": 1,
                },
            ],
        },
    )
    assert (
        e.root.find(".//dashboards/dashboard/zones//zone[@type-v2='color']").get(
            "param"
        )
        == reference
    )
    e.save(str(tmp_path / "context.twb"))


@pytest.mark.parametrize("context,overrides", [("true", {}), (True, {}), (1, {})])
def test_invalid_context_options_fail_before_mutation(context, overrides):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError, match="table_calc_context"):
        e.configure_layered_chart(
            "Map",
            panes=[{"mark_type": "Circle"}],
            table_calc_context=context,
            table_calc_overrides=overrides,
        )
    assert etree.tostring(e.root) == before


def test_mcp_and_run_spec_forward_context_flag(monkeypatch):
    from cwtwb.commands.run_spec import _apply_worksheets
    from cwtwb.mcp import tools_workbook

    e = editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    options = {
        "panes": [{"mark_type": "Circle", "detail": "District", "color": "Percentile"}],
        "table_calc_context": True,
        "table_calc_overrides": {
            "Percentile": [{"ordering_type": "Field", "order": ["District"]}]
        },
    }
    tools_workbook.configure_layered_chart("Map", **options)
    _apply_worksheets(e, {"worksheets": [{"name": "Map", "layered": options}]})
    assert e.root.find(".//encodings/color").get("column").endswith(":1]")


def test_different_worksheet_contexts_do_not_collide_when_dashboard_merges_dependencies(
    tmp_path,
):
    e = editor()
    e.add_calculated_field(
        "Region", "'R'", datatype="string", role="dimension", field_type="nominal"
    )
    e.add_worksheet("Table")
    for sheet, dimension in [("Map", "District"), ("Table", "Region")]:
        options = {
            "panes": [
                {"mark_type": "Circle", "detail": dimension, "color": "Percentile"}
            ],
            "table_calc_context": True,
            "table_calc_overrides": {
                "Percentile": [{"ordering_type": "Field", "order": [dimension]}]
            },
        }
        e.configure_layered_chart(sheet, **options)
        e.configure_layered_chart(sheet, **options)
    names = [
        e.root.find(
            f"worksheets/worksheet[@name='{sheet}']/table/panes/pane/encodings/color"
        ).get("column")
        for sheet in ["Map", "Table"]
    ]
    assert names[0].endswith(":1]") and names[1].endswith(":2]")
    e.add_dashboard(
        "Both",
        width=400,
        height=300,
        layout={
            "type": "vertical",
            "children": [
                {"type": "worksheet", "name": sheet} for sheet in ["Map", "Table"]
            ],
        },
    )
    instances = e.root.findall(
        "worksheets/worksheet/table/view/datasource-dependencies/column-instance"
    )
    for name in names:
        assert any(name.endswith("." + ci.get("name")) for ci in instances)
    e.save(str(tmp_path / "merged-contexts.twb"))
