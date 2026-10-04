"""Computed member sorting precedes INDEX pagination on nested row shelves."""

import pytest
from lxml import etree

from cwtwb import TWBEditor


def editor():
    e = TWBEditor("")
    e.add_calculated_field(
        "Member", "1", datatype="integer", role="dimension", field_type="ordinal"
    )
    e.add_calculated_field(
        "Season", "2020", datatype="integer", role="dimension", field_type="ordinal"
    )
    e.add_calculated_field("Metric", "1.0")
    e.add_calculated_field("Position", "INDEX()", table_calc="Rows")
    e.add_worksheet("Table")
    return e


@pytest.mark.parametrize("mode", ["auto", "shelf", "computed"])
def test_explicit_computed_sort_for_outer_row_dimension(mode, tmp_path):
    e = editor()
    options = {
        "rows": ["Member", "Season"],
        "panes": [{"mark_type": "Text", "label": "SUM(Metric)"}],
        "sort_descending": "SUM(Metric)",
        "sort_field": "Member",
        "sort_mode": mode,
        "filters": [{"column": "Position", "min": "11", "max": "20"}],
    }
    e.configure_layered_chart("Table", **options)
    e.configure_layered_chart("Table", **options)
    computed = e.root.findall(".//computed-sort")
    shelf = e.root.findall(".//shelf-sort-v2")
    if mode == "computed":
        assert len(computed) == 1 and not shelf
        sort = computed[0]
        assert sort.get("column") == e.field_registry.resolve_full_reference(
            e.field_registry.parse_expression("Member").instance_name
        )
        assert sort.get("using").endswith(
            e.field_registry.parse_expression("SUM(Metric)").instance_name
        )
        assert sort.get("direction") == "DESC"
    else:
        assert len(shelf) == 1 and not computed
    e.save(str(tmp_path / "pagination.twb"))
    e.configure_layered_chart(
        "Table",
        **{**options, "sort_mode": "shelf" if mode == "computed" else "computed"},
    )
    assert bool(e.root.findall(".//computed-sort")) != bool(
        e.root.findall(".//shelf-sort-v2")
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"sort_mode": "unknown"},
        {"sort_mode": "computed"},
        {"sort_mode": "computed", "sort_field": "Member"},
    ],
)
def test_invalid_sort_modes_do_not_mutate(changes):
    e = editor()
    before = etree.tostring(e.root)
    with pytest.raises(ValueError):
        e.configure_layered_chart("Table", panes=[{"mark_type": "Text"}], **changes)
    assert etree.tostring(e.root) == before


def test_mcp_and_run_spec_forward_computed_sort(monkeypatch):
    from cwtwb.commands.run_spec import _apply_worksheets
    from cwtwb.mcp import tools_workbook

    e = editor()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    options = {
        "rows": ["Member", "Season"],
        "panes": [{"mark_type": "Text", "label": "SUM(Metric)"}],
        "sort_descending": "SUM(Metric)",
        "sort_field": "Member",
        "sort_mode": "computed",
    }
    tools_workbook.configure_layered_chart("Table", **options)
    assert e.root.find(".//computed-sort") is not None
    _apply_worksheets(e, {"worksheets": [{"name": "Table", "layered": options}]})
    assert len(e.root.findall(".//computed-sort")) == 1
