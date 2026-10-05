"""Regression contracts for measure-values requests on primitive marks.

``configure_chart(measure_values=...)`` is documented for Text/Square charts,
but callers also pass it with Bar/Line/Circle marks.  That request used to be
accepted and then silently dropped: the worksheet ended up with a Measure Names
color encoding pointing at a bogus physical ``[Measure Names]`` column and no
measure on either shelf, so Tableau rendered an empty view.  These tests pin the
two halves of the fix.
"""

from cwtwb import TWBEditor


def _worksheet(editor, sheet):
    return editor.root.find(f"worksheets/worksheet[@name='{sheet}']")


def _view(editor, sheet):
    return _worksheet(editor, sheet).find("table/view")


def _colors(editor, sheet):
    return [
        node.get("column")
        for node in _worksheet(editor, sheet).findall("table/panes/pane/encodings/color")
    ]


def test_bar_measure_values_bind_measures_and_virtual_color(editor_superstore):
    editor_superstore.add_worksheet("Bars")
    editor_superstore.configure_chart(
        "Bars",
        mark_type="Bar",
        rows=["Order ID"],
        measure_values=["SUM(Sales)", "SUM(Quantity)"],
    )

    worksheet = editor_superstore.root.find("worksheets/worksheet[@name='Bars']")
    view = _view(editor_superstore, "Bars")
    cols = worksheet.findtext("table/cols") or ""
    rows = worksheet.findtext("table/rows") or ""

    # Dimensions keep their shelf; the measures own the other shelf.
    assert "Order ID" in rows
    assert "sum:Sales" in cols and "sum:Quantity" in cols
    # Tableau sums independent measures with '+', never multiplies them.
    assert " * " not in cols

    # Color resolves to the virtual Measure Names field, not a physical column.
    datasource = editor_superstore._datasource.get("name")
    assert _colors(editor_superstore, "Bars") == [f"[{datasource}].[:Measure Names]"]
    # The bogus physical column must not be registered in the dependencies.
    assert view.find("datasource-dependencies/column[@name='[Measure Names]']") is None
    assert (
        view.find("datasource-dependencies/column-instance[@name='[none:Measure Names:nk]']")
        is None
    )
    # Measure Names participates in the view slices.
    assert f"[{datasource}].[:Measure Names]" in [
        node.text for node in view.findall("slices/column")
    ]


def test_bar_measure_values_land_on_the_dimension_free_shelf(editor_superstore):
    """With a dimension on rows, requested measures go on columns."""

    editor_superstore.add_worksheet("Horizontal")
    editor_superstore.configure_chart(
        "Horizontal",
        mark_type="Bar",
        rows=["Order ID"],
        measure_values=["SUM(Profit)"],
    )
    worksheet = editor_superstore.root.find("worksheets/worksheet[@name='Horizontal']")
    assert "Order ID" in (worksheet.findtext("table/rows") or "")
    assert "sum:Profit" in (worksheet.findtext("table/cols") or "")


def test_measure_values_do_not_shadow_explicit_measure_columns(editor_superstore):
    """An explicit measure column shelf still wins for its own field."""

    editor_superstore.add_worksheet("Explicit")
    editor_superstore.configure_chart(
        "Explicit",
        mark_type="Bar",
        columns=["SUM(Sales)"],
        rows=["Order ID"],
        measure_values=["SUM(Profit)"],
    )
    worksheet = editor_superstore.root.find("worksheets/worksheet[@name='Explicit']")
    cols = worksheet.findtext("table/cols") or ""
    assert "sum:Sales" in cols
    assert "sum:Profit" in cols


def test_measure_names_color_uses_virtual_field(editor_superstore):
    """A literal 'Measure Names' color must resolve to the virtual reference."""

    editor_superstore.add_worksheet("Colored")
    editor_superstore.configure_chart(
        "Colored",
        mark_type="Bar",
        rows=["Order ID"],
        columns=["SUM(Sales)", "SUM(Quantity)"],
        color="Measure Names",
    )
    view = _view(editor_superstore, "Colored")
    datasource = editor_superstore._datasource.get("name")
    assert _colors(editor_superstore, "Colored") == [f"[{datasource}].[:Measure Names]"]
    assert view.find("datasource-dependencies/column[@name='[Measure Names]']") is None


def test_multiple_values_color_is_still_rejected_without_measure_values(editor_superstore):
    """The virtual Multiple Values guard stays in place for unsupported marks."""

    editor_superstore.add_worksheet("Bad")
    try:
        editor_superstore.configure_chart(
            "Bad",
            mark_type="Bar",
            rows=["Order ID"],
            columns=["SUM(Sales)"],
            color="Multiple Values",
        )
    except ValueError as exc:
        assert "Multiple Values color requires" in str(exc)
    else:  # pragma: no cover - the guard must reject this request
        raise AssertionError("Multiple Values color without measure_values must raise")
