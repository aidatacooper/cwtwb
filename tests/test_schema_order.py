"""Tests for schema-derived child reordering.

Tableau Desktop enforces ordered XSD sequences in its DOM loader. These tests
cover the generic reorder, which derives the order from the vendored official
schema rather than hardcoding per-container rules.
"""

from pathlib import Path

from lxml import etree

from cwtwb.schema_order import canonical_child_order, reorder_to_schema
from cwtwb.twb_editor import TWBEditor

REFERENCES = Path(__file__).parent.parent / "src" / "cwtwb" / "references"


def test_datasource_order_comes_from_schema() -> None:
    # <datasource> has several content models, so the helper reports no single
    # order; the container-specific reorder still places column-instance right.
    from cwtwb.schema_order import _best_order

    present = {"connection", "aliases", "column", "column-instance", "group", "layout"}
    order = _best_order("datasource", present, None)
    assert order is not None
    # column-instance belongs to Columns-G, before the trailing groups.
    assert order.index("column") < order.index("column-instance")
    assert order.index("column-instance") < order.index("group")
    assert order.index("group") < order.index("layout")


def test_pane_order_places_tooltip_before_label() -> None:
    order = canonical_child_order("pane")
    assert order is not None
    assert order.index("customized-tooltip") < order.index("customized-label")
    assert order.index("customized-label") < order.index("style")


def test_choice_branches_are_not_merged() -> None:
    """xs:choice alternatives must stay separate, not concatenated."""
    from cwtwb.schema_order import _order_index, _schema_path

    index = _order_index(str(_schema_path(None)))
    window_orders = index["window"]
    assert len(window_orders) >= 2
    # A worksheet window ends with simple-id; a dashboard window also has
    # simple-id last but lists viewpoints first. A merged model would put
    # simple-id before viewpoints.
    dashboard = next(o for o in window_orders if "viewpoints" in o)
    assert dashboard.index("viewpoints") < dashboard.index("simple-id")


def test_reorder_moves_column_instance_before_group() -> None:
    root = etree.fromstring(
        b'<workbook version="18.1"><datasources><datasource name="d">'
        b"<column name='[A]'/><group name='g'/><column-instance name='ci'/>"
        b"</datasource></datasources></workbook>"
    )
    changed = reorder_to_schema(root)
    assert changed is not None
    datasource = root.find("datasources/datasource")
    assert [c.tag for c in datasource] == ["column", "column-instance", "group"]


def test_reorder_keeps_duplicate_children_stable() -> None:
    root = etree.fromstring(
        b'<workbook version="18.1"><datasources><datasource name="d">'
        b"<group name='g1'/><column name='a'/><column name='b'/><group name='g2'/>"
        b"</datasource></datasources></workbook>"
    )
    reorder_to_schema(root)
    datasource = root.find("datasources/datasource")
    assert [c.tag for c in datasource] == ["column", "column", "group", "group"]
    # relative order within a repeated tag must be preserved
    assert [c.get("name") for c in datasource if c.tag == "column"] == ["a", "b"]
    assert [c.get("name") for c in datasource if c.tag == "group"] == ["g1", "g2"]


def test_unknown_children_are_left_untouched() -> None:
    root = etree.fromstring(
        b'<workbook version="18.1"><datasources><datasource name="d">'
        b"<totally-unknown/><column name='a'/>"
        b"</datasource></datasources></workbook>"
    )
    before = etree.tostring(root)
    reorder_to_schema(root)
    assert etree.tostring(root) == before


def test_comments_do_not_break_reordering() -> None:
    root = etree.fromstring(
        b'<workbook version="18.1"><datasources><datasource name="d">'
        b"<group name='g'/><!-- note --><column name='a'/>"
        b"</datasource></datasources></workbook>"
    )
    # A comment child makes the container ambiguous; it must not crash.
    reorder_to_schema(root)
    assert root.find("datasources/datasource") is not None


def test_save_applies_schema_order(tmp_path: Path) -> None:
    editor = TWBEditor(REFERENCES / "empty_template.twb")
    datasource = next(
        ds
        for ds in editor.root.findall("datasources/datasource")
        if ds.get("name") != "Parameters"
    )
    etree.SubElement(datasource, "drill-paths")
    etree.SubElement(
        datasource,
        "column-instance",
        column="[Region]",
        derivation="None",
        name="[none:Region:nk]",
        pivot="key",
        type="nominal",
    )

    out = tmp_path / "ordered.twb"
    editor.save(out, validate=False)

    root = etree.parse(str(out)).getroot()
    ds = next(
        d for d in root.findall("datasources/datasource") if d.get("name") != "Parameters"
    )
    tags = [c.tag for c in ds]
    assert tags.index("column-instance") < tags.index("drill-paths")
