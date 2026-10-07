"""Manifest-flag reconciliation for gated elements and attributes.

Tableau Desktop refuses to open a workbook whose tree contains certain
elements or attributes without the matching ``document-format-change-manifest``
entry, even though the XML passes the TWB XSD (error ``d2e8da72``). These
tests pin the reconciliation pass that derives the flags from the finished
tree, so any builder path that emits the gated content is covered.
"""

from lxml import etree

from cwtwb import TWBEditor


def _manifest(editor: TWBEditor) -> set[str]:
    manifest = editor.root.find("document-format-change-manifest")
    if manifest is None:
        return set()
    return {child.tag for child in manifest}


def _inject(editor: TWBEditor, markup: str) -> None:
    worksheet = editor._find_worksheet(editor.root.findall("worksheets/worksheet")[0].get("name"))
    worksheet.find("table/view").append(etree.fromstring(markup))


def test_computed_sort_requires_sort_tag_cleanup() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    assert "SortTagCleanup" not in _manifest(editor)
    _inject(
        editor,
        '<computed-sort column="[federated.x].[none:A:nk]" direction="DESC" '
        'using="[federated.x].[sum:B:qk]"/>',
    )
    editor._sanitize_workbook_tree()
    assert "SortTagCleanup" in _manifest(editor)


def test_manual_sort_requires_sort_tag_cleanup() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    _inject(
        editor,
        '<manual-sort column="[federated.x].[:Measure Names]" direction="ASC">'
        "<dictionary/></manual-sort>",
    )
    editor._sanitize_workbook_tree()
    assert "SortTagCleanup" in _manifest(editor)


def test_hide_sort_controls_requires_its_flag() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    _inject(editor, "<hide-sort-controls/>")
    editor._sanitize_workbook_tree()
    assert "HideSortControls" in _manifest(editor)


def test_generated_title_requires_layers() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    pane = editor._find_worksheet("Viz").find("table/panes/pane")
    pane.set("generated-title", "Destination")
    editor._sanitize_workbook_tree()
    assert "Layers" in _manifest(editor)


def test_device_layouts_require_phone_layout_flag() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    root = editor.root
    dashboards = root.find("dashboards")
    if dashboards is None:
        dashboards = etree.SubElement(root, "dashboards")
    dashboard = etree.SubElement(dashboards, "dashboard", name="D")
    etree.SubElement(dashboard, "devicelayouts")
    editor._sanitize_workbook_tree()
    assert "AutoCreateAndUpdateDSDPhoneLayouts" in _manifest(editor)


def test_button_requires_collapsible_pane_flag() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    root = editor.root
    dashboards = root.find("dashboards")
    if dashboards is None:
        dashboards = etree.SubElement(root, "dashboards")
    dashboard = etree.SubElement(dashboards, "dashboard", name="D")
    zones = etree.SubElement(dashboard, "zones")
    etree.SubElement(zones, "button", **{"button-type": "text"})
    editor._sanitize_workbook_tree()
    assert "CollapsiblePane" in _manifest(editor)


def test_text_button_requires_object_model_and_text_support() -> None:
    """A text button needs CollapsiblePane plus the two BasicButtonObject flags.

    Tableau-authored workbooks pair all three. Adding only CollapsiblePane (the
    older rule) leaves Desktop refusing the workbook; this reproduces ww10 and
    ww39 before the fix.
    """
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    root = editor.root
    dashboards = root.find("dashboards")
    if dashboards is None:
        dashboards = etree.SubElement(root, "dashboards")
    dashboard = etree.SubElement(dashboards, "dashboard", name="D")
    zones = etree.SubElement(dashboard, "zones")
    etree.SubElement(zones, "button", **{"button-type": "text"})
    editor._sanitize_workbook_tree()
    manifest = editor.root.find("document-format-change-manifest")
    assert manifest.find("CollapsiblePane") is not None
    assert manifest.find("BasicButtonObject") is not None
    text_support = manifest.find("BasicButtonObjectTextSupport")
    assert text_support is not None
    assert text_support.get("ignorable") == "true"
    assert text_support.get("predowngraded") == "true"


def test_non_text_button_does_not_require_text_support() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    root = editor.root
    dashboards = root.find("dashboards")
    if dashboards is None:
        dashboards = etree.SubElement(root, "dashboards")
    dashboard = etree.SubElement(dashboards, "dashboard", name="D")
    zones = etree.SubElement(dashboard, "zones")
    etree.SubElement(zones, "button", **{"button-type": "image"})
    editor._sanitize_workbook_tree()
    assert "BasicButtonObject" not in _manifest(editor)
    assert "BasicButtonObjectTextSupport" not in _manifest(editor)


def test_absent_content_adds_no_flag() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    editor._sanitize_workbook_tree()
    manifest = _manifest(editor)
    assert "SortTagCleanup" not in manifest
    assert "HideSortControls" not in manifest
    assert "Layers" not in manifest


def test_reconciliation_is_idempotent() -> None:
    editor = TWBEditor("")
    editor.add_worksheet("Viz")
    _inject(editor, "<hide-sort-controls/>")
    editor._sanitize_workbook_tree()
    editor._sanitize_workbook_tree()
    manifest = editor.root.find("document-format-change-manifest")
    assert len(manifest.findall("HideSortControls")) == 1
