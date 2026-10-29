import pytest
from lxml import etree
from cwtwb import TWBEditor


def make():
    e = TWBEditor("")
    for name in ("Earlier", "Later", "Spacer", "Anchor"):
        e.add_calculated_field(name, "1.0")
    e.add_worksheet("Chart")
    return e


def options():
    return dict(columns=["Multiple Values"], rows=["Measure Names"], axis_shelf="columns",
                panes=[dict(axis="Multiple Values", mark_type="Bar",
                            measure_values=["SUM(Earlier)", "SUM(Later)", "SUM(Spacer)"])])


def test_independent_order_dependencies_and_bindings(tmp_path):
    e = make()
    e.configure_layered_chart("Chart", **options())
    table = e.root.find(".//worksheet/table")
    before = [etree.tostring(table.find(tag)) for tag in ("rows", "cols", "panes")]
    order = ["SUM(Earlier)", "SUM(Later)", "SUM(Anchor)", "SUM(Spacer)"]
    e.configure_layered_chart("Chart", **options(), measure_names_order=order)
    table = e.root.find(".//worksheet/table")
    view = table.find("view")
    refs = [e.field_registry.resolve_full_reference(e.field_registry.parse_expression(x).instance_name) for x in order]
    assert view.xpath("manual-sort/dictionary/bucket/text()") == ['"'+r+'"' for r in refs]
    members = view.xpath("filter/groupfilter/groupfilter/@member")
    assert members == ['"'+refs[i]+'"' for i in (0, 1, 3)]
    assert before == [etree.tostring(table.find(tag)) for tag in ("rows", "cols", "panes")]
    ci = e.field_registry.parse_expression("SUM(Anchor)")
    assert view.find("datasource-dependencies/column-instance[@name='"+ci.instance_name+"']") is not None
    assert view.find("datasource-dependencies/column[@name='"+ci.column_local_name+"']") is not None
    e.save(str(tmp_path / "order.twb"))
    e.configure_layered_chart("Chart", **options())
    assert len(e.root.findall(".//manual-sort/dictionary/bucket")) == 3


@pytest.mark.parametrize("order", ["SUM(Earlier)", [""], [None], ["Measure Names"], ["SUM(Earlier)", "SUM([Earlier])"]])
def test_invalid_order(order):
    e = make()
    with pytest.raises(ValueError):
        e.configure_layered_chart("Chart", **options(), measure_names_order=order)


def test_unknown_order_rejected_in_compatibility_mode():
    e = make()
    e.field_registry.allow_unknown_fields = True
    with pytest.raises(KeyError):
        e.configure_layered_chart("Chart", **options(), measure_names_order=["SUM(Missing)"])
    assert e.field_registry.allow_unknown_fields is True


def test_mcp_and_run_spec_forward_order(monkeypatch):
    from cwtwb.commands.run_spec import _apply_worksheets
    from cwtwb.mcp import tools_workbook
    e = make()
    monkeypatch.setattr(tools_workbook, "get_editor", lambda: e)
    kw = dict(**options(), measure_names_order=["SUM(Earlier)", "SUM(Later)", "SUM(Anchor)", "SUM(Spacer)"])
    tools_workbook.configure_layered_chart("Chart", **kw)
    assert len(e.root.findall(".//manual-sort/dictionary/bucket")) == 4
    _apply_worksheets(e, {"worksheets": [{"name": "Chart", "layered": kw}]})
    assert len(e.root.findall(".//manual-sort/dictionary/bucket")) == 4
    assert len(e.root.findall(".//filter/groupfilter/groupfilter")) == 3
