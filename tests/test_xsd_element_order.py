"""Regression tests for XSD element ordering that Tableau Desktop enforces.

Tableau Desktop's DOM loader rejects a workbook whose schema-ordered
sequences are out of order, even when the XML is otherwise well formed and
even when every structural contract check passes. Two sequences are commonly
emitted out of order while editing:

* ``<datasource>``: ``column-instance`` belongs to ``Columns-G`` and must
  precede ``drill-paths`` / ``group`` / ``layout`` / ``style`` and the other
  trailing groups.
* ``<actions>``: ``Actions-G`` orders ``action``, ``nav-action``,
  ``edit-group-action``, then ``edit-parameter-action``.

These tests assert the canonical order is restored on save, and that already
valid workbooks are left untouched.
"""

from pathlib import Path

from lxml import etree

from cwtwb.twb_editor import TWBEditor

REFERENCES = Path(__file__).parent.parent / "src" / "cwtwb" / "references"


def _editor() -> TWBEditor:
    return TWBEditor(REFERENCES / "empty_template.twb")


def _datasource(editor: TWBEditor) -> etree._Element:
    return next(
        ds
        for ds in editor.root.findall("datasources/datasource")
        if ds.get("name") != "Parameters"
    )


def test_datasource_column_instance_moves_before_drill_paths() -> None:
    editor = _editor()
    datasource = _datasource(editor)

    drill_paths = etree.SubElement(datasource, "drill-paths")
    etree.SubElement(drill_paths, "drill-path", name="Category Hierarchy")
    # Simulates the SDK appending an instance after the trailing groups.
    etree.SubElement(datasource, "layout")
    etree.SubElement(datasource, "style")
    etree.SubElement(
        datasource,
        "column-instance",
        column="[Calculation_ABC]",
        derivation="None",
        name="[none:Calculation_ABC:nk]",
        pivot="key",
        type="nominal",
    )

    editor._canonicalize_schema_order()

    tags = [child.tag for child in datasource]
    assert tags.index("column-instance") < tags.index("drill-paths")
    assert tags.index("column-instance") < tags.index("layout")
    assert tags.index("column-instance") < tags.index("style")


def test_datasource_column_instance_moves_before_group() -> None:
    """``group`` is the element name; ``Groups-G`` is only the schema group."""
    editor = _editor()
    datasource = _datasource(editor)

    etree.SubElement(datasource, "group", name="[none:Region:nk]")
    etree.SubElement(
        datasource,
        "column-instance",
        column="[Region]",
        derivation="None",
        name="[none:Region:nk]",
        pivot="key",
        type="nominal",
    )

    editor._canonicalize_schema_order()

    tags = [child.tag for child in datasource]
    assert tags.index("column-instance") < tags.index("group")


def test_actions_are_grouped_in_schema_order() -> None:
    editor = _editor()
    actions = etree.SubElement(editor.root, "actions")
    for tag in ("edit-parameter-action", "action", "nav-action", "action"):
        etree.SubElement(actions, tag, name=f"[{tag}]")

    editor._canonicalize_schema_order()

    assert [child.tag for child in actions] == [
        "action",
        "action",
        "nav-action",
        "edit-parameter-action",
    ]


def test_action_order_is_stable_within_a_group() -> None:
    editor = _editor()
    actions = etree.SubElement(editor.root, "actions")
    for name in ("[First]", "[Second]", "[Third]"):
        etree.SubElement(actions, "action", name=name)

    editor._canonicalize_schema_order()

    assert [child.get("name") for child in actions] == ["[First]", "[Second]", "[Third]"]


def test_already_ordered_workbook_is_unchanged() -> None:
    editor = _editor()
    datasource = _datasource(editor)
    etree.SubElement(datasource, "drill-paths")
    etree.SubElement(datasource, "layout")
    before = etree.tostring(editor.root)

    editor._canonicalize_schema_order()

    assert etree.tostring(editor.root) == before


def test_unknown_action_children_are_preserved() -> None:
    """Unexpected children must never be dropped while reordering."""
    editor = _editor()
    actions = etree.SubElement(editor.root, "actions")
    etree.SubElement(actions, "edit-parameter-action", name="[Param]")
    etree.SubElement(actions, "action", name="[Filter]")
    etree.SubElement(actions, "mystery-action", name="[Keep]")

    editor._canonicalize_schema_order()

    tags = [child.tag for child in actions]
    assert "mystery-action" in tags
    assert tags.index("action") < tags.index("edit-parameter-action")


def test_save_emits_canonical_order(tmp_path: Path) -> None:
    """The ordering fix runs on the real save path, not only when called directly."""
    editor = _editor()
    datasource = _datasource(editor)
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
    tags = [child.tag for child in ds]
    assert tags.index("column-instance") < tags.index("drill-paths")
