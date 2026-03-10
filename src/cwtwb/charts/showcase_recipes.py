"""Shared helpers for showcase recipe charts.

The public entrypoint is ``configure_chart_recipe(...)``. Individual recipe
builders remain private so new recipes can be registered without expanding the
MCP surface area.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from lxml import etree


DEFAULT_CALENDAR_YEAR_MONTH = "202208"
DEFAULT_LOLLIPOP_BAR_SIZE = "0.15292817354202271"
DEFAULT_LOLLIPOP_CIRCLE_SIZE = "3.5690608024597168"
DEFAULT_DONUT_OUTER_SIZE = "1.8"
DEFAULT_DONUT_INNER_SIZE = "1.263370156288147"
DEFAULT_CALENDAR_MARK_SIZE = "1.8790607452392578"
DEFAULT_CALENDAR_CELL_HEIGHT = "38"
DEFAULT_DONUT_MIN_ZERO_FIELD = "min 0"
DEFAULT_CALENDAR_COLOR_FIELD = "Sales Over 400"
DEFAULT_CALENDAR_COLOR_FORMULA = 'IF SUM([Sales]) > 500 THEN "Yes" ELSE "No" END'


@dataclass(frozen=True)
class _RecipeSpec:
    required_args: tuple[str, ...]
    defaults: dict[str, str]
    auto_ensure: Callable[[object, dict[str, str]], None] | None
    builder: Callable[[object, str, dict[str, str]], str]


def configure_chart_recipe(
    editor,
    worksheet_name: str,
    recipe_name: str,
    recipe_args: dict[str, str] | None = None,
    auto_ensure_prerequisites: bool = True,
) -> str:
    """Configure a showcase recipe chart through the shared registry."""

    recipe_key = recipe_name.strip().lower()
    recipe = _RECIPE_REGISTRY.get(recipe_key)
    if recipe is None:
        supported = ", ".join(sorted(_RECIPE_REGISTRY))
        raise ValueError(f"Unknown chart recipe '{recipe_name}'. Supported recipes: {supported}")

    resolved_args = dict(recipe.defaults)
    if recipe_args:
        resolved_args.update(recipe_args)

    missing = [name for name in recipe.required_args if not resolved_args.get(name)]
    if missing:
        missing_csv = ", ".join(missing)
        raise ValueError(f"Chart recipe '{recipe_key}' is missing required args: {missing_csv}")

    if auto_ensure_prerequisites and recipe.auto_ensure is not None:
        recipe.auto_ensure(editor, resolved_args)

    return recipe.builder(editor, worksheet_name, resolved_args)


def _configure_lollipop_recipe(
    editor,
    worksheet_name: str,
    dimension: str,
    measure: str,
) -> str:
    """Configure the showcase lollipop chart recipe."""

    return editor.configure_dual_axis(
        worksheet_name,
        mark_type_1="Bar",
        mark_type_2="Circle",
        columns=[measure, measure],
        rows=[dimension],
        dual_axis_shelf="columns",
        synchronized=True,
        show_labels=False,
        mark_sizing_off=True,
        size_value_1=DEFAULT_LOLLIPOP_BAR_SIZE,
        size_value_2=DEFAULT_LOLLIPOP_CIRCLE_SIZE,
        hide_axes=True,
    )


def _configure_donut_recipe(
    editor,
    worksheet_name: str,
    category: str,
    measure: str,
    *,
    min_zero_field: str = "min 0",
) -> str:
    """Configure the showcase donut chart recipe."""

    return editor.configure_dual_axis(
        worksheet_name,
        mark_type_1="Pie",
        mark_type_2="Pie",
        columns=[],
        rows=[min_zero_field, min_zero_field],
        dual_axis_shelf="rows",
        color_1=category,
        wedge_size_1=measure,
        label_2=measure,
        synchronized=False,
        show_labels=True,
        hide_axes=True,
        hide_zeroline=True,
        mark_sizing_off=True,
        size_value_1=DEFAULT_DONUT_OUTER_SIZE,
        size_value_2=DEFAULT_DONUT_INNER_SIZE,
        mark_color_2="#ffffff",
    )


def _configure_butterfly_recipe(
    editor,
    worksheet_name: str,
    dimension: str,
    left_measure: str,
    right_measure: str,
) -> str:
    """Configure the showcase butterfly chart recipe."""

    return editor.configure_dual_axis(
        worksheet_name,
        mark_type_1="Bar",
        mark_type_2="Bar",
        columns=[left_measure, right_measure],
        rows=[dimension],
        dual_axis_shelf="columns",
        show_labels=True,
        hide_zeroline=True,
        synchronized=False,
        reverse_axis_1=True,
    )


def _configure_calendar_recipe(
    editor,
    worksheet_name: str,
    *,
    date_field: str = "Order Date",
    color: str,
    label: str,
    year_month: str = DEFAULT_CALENDAR_YEAR_MONTH,
) -> str:
    """Configure the showcase calendar chart recipe."""

    date_expr = date_field
    result = editor.configure_chart(
        worksheet_name,
        mark_type="Square",
        rows=[f"WEEK({date_expr})"],
        columns=[f"WEEKDAY({date_expr})"],
        color=color,
        label=label,
    )
    _apply_calendar_recipe_layout(
        editor,
        worksheet_name,
        date_field=date_expr,
        year_month=year_month,
    )
    return result


def _apply_calendar_recipe_layout(
    editor,
    worksheet_name: str,
    *,
    date_field: str = "Order Date",
    year_month: str = DEFAULT_CALENDAR_YEAR_MONTH,
) -> None:
    """Apply the XML-only tweaks used by the showcase calendar chart."""

    ws = editor._find_worksheet(worksheet_name)
    table = ws.find("table")
    if table is None:
        raise ValueError(f"Worksheet '{worksheet_name}' is malformed: missing <table>")
    view = table.find("view")
    if view is None:
        raise ValueError(f"Worksheet '{worksheet_name}' is malformed: missing <view>")

    my_ci = editor.field_registry.parse_expression(f"MY({date_field})")
    my_ref = editor.field_registry.resolve_full_reference(my_ci.instance_name)
    _ensure_column_instance(view, my_ci)

    agg = view.find("aggregation")
    _upsert_calendar_filter(view, agg, my_ci.instance_name, my_ref, year_month)
    _upsert_calendar_slices(view, agg, my_ref)

    day_ci = editor.field_registry.parse_expression(f"DAYTRUNC({date_field})")
    day_ref = editor.field_registry.resolve_full_reference(day_ci.instance_name)
    week_ci = editor.field_registry.parse_expression(f"WEEK({date_field})")
    week_ref = editor.field_registry.resolve_full_reference(week_ci.instance_name)
    weekday_ci = editor.field_registry.parse_expression(f"WEEKDAY({date_field})")
    weekday_ref = editor.field_registry.resolve_full_reference(weekday_ci.instance_name)

    old_style = table.find("style")
    if old_style is not None:
        table.remove(old_style)

    style = etree.Element("style")
    cell_rule = etree.SubElement(style, "style-rule", {"element": "cell"})
    etree.SubElement(
        cell_rule,
        "format",
        {"attr": "text-format", "field": day_ref, "value": "*d"},
    )
    etree.SubElement(
        cell_rule,
        "format",
        {"attr": "height", "field": week_ref, "value": DEFAULT_CALENDAR_CELL_HEIGHT},
    )

    label_rule = etree.SubElement(style, "style-rule", {"element": "label"})
    etree.SubElement(
        label_rule,
        "format",
        {"attr": "display", "field": week_ref, "value": "false"},
    )
    etree.SubElement(
        label_rule,
        "format",
        {"attr": "display", "field": weekday_ref, "value": "false"},
    )

    panes = table.find("panes")
    if panes is not None:
        panes.addprevious(style)
    else:
        table.append(style)

    pane = table.find(".//pane")
    if pane is None:
        return

    pane.set("selection-relaxation-option", "selection-relaxation-disallow")
    _ensure_mark_sizing_after_mark(pane)

    pane_style = pane.find("style")
    if pane_style is None:
        pane_style = etree.SubElement(pane, "style")

    cell_sr = etree.SubElement(pane_style, "style-rule", {"element": "cell"})
    etree.SubElement(cell_sr, "format", {"attr": "text-align", "value": "center"})
    etree.SubElement(cell_sr, "format", {"attr": "vertical-align", "value": "center"})

    _upsert_mark_size(pane_style, DEFAULT_CALENDAR_MARK_SIZE)

    pane_sr = etree.SubElement(pane_style, "style-rule", {"element": "pane"})
    etree.SubElement(pane_sr, "format", {"attr": "minheight", "value": "-1"})
    etree.SubElement(pane_sr, "format", {"attr": "maxheight", "value": "-1"})


def _ensure_default_donut_prerequisites(editor, recipe_args: dict[str, str]) -> None:
    min_zero_field = recipe_args.get("min_zero_field", DEFAULT_DONUT_MIN_ZERO_FIELD)
    recipe_args["min_zero_field"] = min_zero_field
    if min_zero_field != DEFAULT_DONUT_MIN_ZERO_FIELD:
        return
    if _field_exists(editor, min_zero_field):
        return
    editor.add_calculated_field(min_zero_field, "MIN(0)", datatype="integer")


def _ensure_default_calendar_prerequisites(editor, recipe_args: dict[str, str]) -> None:
    color = recipe_args.get("color", DEFAULT_CALENDAR_COLOR_FIELD)
    recipe_args["color"] = color
    if color != DEFAULT_CALENDAR_COLOR_FIELD:
        return
    if _field_exists(editor, color):
        return
    editor.add_calculated_field(
        DEFAULT_CALENDAR_COLOR_FIELD,
        DEFAULT_CALENDAR_COLOR_FORMULA,
        datatype="string",
    )


def _field_exists(editor, field_name: str) -> bool:
    if editor.field_registry.get(field_name) is not None:
        return True

    field_name_lower = field_name.lower()
    for field in editor.field_registry.all_fields():
        if field.display_name.lower() == field_name_lower:
            return True
    return False


def _build_lollipop(editor, worksheet_name: str, recipe_args: dict[str, str]) -> str:
    return _configure_lollipop_recipe(
        editor,
        worksheet_name,
        recipe_args["dimension"],
        recipe_args["measure"],
    )


def _build_donut(editor, worksheet_name: str, recipe_args: dict[str, str]) -> str:
    return _configure_donut_recipe(
        editor,
        worksheet_name,
        recipe_args["category"],
        recipe_args["measure"],
        min_zero_field=recipe_args["min_zero_field"],
    )


def _build_butterfly(editor, worksheet_name: str, recipe_args: dict[str, str]) -> str:
    return _configure_butterfly_recipe(
        editor,
        worksheet_name,
        recipe_args["dimension"],
        recipe_args["left_measure"],
        recipe_args["right_measure"],
    )


def _build_calendar(editor, worksheet_name: str, recipe_args: dict[str, str]) -> str:
    return _configure_calendar_recipe(
        editor,
        worksheet_name,
        date_field=recipe_args["date_field"],
        color=recipe_args["color"],
        label=recipe_args["label"],
        year_month=recipe_args["year_month"],
    )


_RECIPE_REGISTRY: dict[str, _RecipeSpec] = {
    "lollipop": _RecipeSpec(
        required_args=("dimension", "measure"),
        defaults={},
        auto_ensure=None,
        builder=_build_lollipop,
    ),
    "donut": _RecipeSpec(
        required_args=("category", "measure"),
        defaults={"min_zero_field": DEFAULT_DONUT_MIN_ZERO_FIELD},
        auto_ensure=_ensure_default_donut_prerequisites,
        builder=_build_donut,
    ),
    "butterfly": _RecipeSpec(
        required_args=("dimension", "left_measure", "right_measure"),
        defaults={},
        auto_ensure=None,
        builder=_build_butterfly,
    ),
    "calendar": _RecipeSpec(
        required_args=(),
        defaults={
            "date_field": "Order Date",
            "color": DEFAULT_CALENDAR_COLOR_FIELD,
            "label": "DAYTRUNC(Order Date)",
            "year_month": DEFAULT_CALENDAR_YEAR_MONTH,
        },
        auto_ensure=_ensure_default_calendar_prerequisites,
        builder=_build_calendar,
    ),
}


def _ensure_column_instance(view, column_instance) -> None:
    deps = view.find("datasource-dependencies")
    if deps is None:
        return

    for existing in deps.findall("column-instance"):
        if existing.get("name") == column_instance.instance_name:
            return

    ci_el = etree.SubElement(deps, "column-instance")
    ci_el.set("column", column_instance.column_local_name)
    ci_el.set("derivation", column_instance.derivation)
    ci_el.set("name", column_instance.instance_name)
    ci_el.set("pivot", column_instance.pivot)
    ci_el.set("type", column_instance.ci_type)


def _upsert_calendar_filter(view, aggregation, instance_name: str, ref_name: str, year_month: str) -> None:
    for existing in view.findall("filter"):
        if existing.get("column") == ref_name:
            groupfilter = existing.find("groupfilter")
            if groupfilter is not None:
                groupfilter.set("member", year_month)
            return

    filt = etree.Element("filter")
    filt.set("class", "categorical")
    filt.set("column", ref_name)
    gf = etree.SubElement(filt, "groupfilter")
    gf.set("function", "member")
    gf.set("level", instance_name)
    gf.set("member", year_month)
    gf.set("{http://www.tableausoftware.com/xml/user}ui-domain", "database")
    gf.set("{http://www.tableausoftware.com/xml/user}ui-enumeration", "inclusive")
    gf.set("{http://www.tableausoftware.com/xml/user}ui-marker", "enumerate")

    if aggregation is not None:
        aggregation.addprevious(filt)
    else:
        view.append(filt)


def _upsert_calendar_slices(view, aggregation, ref_name: str) -> None:
    existing = view.find("slices")
    if existing is not None:
        column = existing.find("column")
        if column is None:
            column = etree.SubElement(existing, "column")
        column.text = ref_name
        return

    slices = etree.Element("slices")
    column = etree.SubElement(slices, "column")
    column.text = ref_name
    if aggregation is not None:
        aggregation.addprevious(slices)
    else:
        view.append(slices)


def _ensure_mark_sizing_after_mark(pane) -> None:
    mark_el = pane.find("mark")
    if mark_el is None:
        return

    next_el = mark_el.getnext()
    if next_el is not None and next_el.tag == "mark-sizing":
        next_el.set("mark-sizing-setting", "marks-scaling-off")
        return

    ms = etree.Element("mark-sizing")
    ms.set("mark-sizing-setting", "marks-scaling-off")
    mark_el.addnext(ms)


def _upsert_mark_size(style, size_value: str) -> None:
    mark_rule = None
    for style_rule in style.findall("style-rule"):
        if style_rule.get("element") == "mark":
            mark_rule = style_rule
            break
    if mark_rule is None:
        mark_rule = etree.SubElement(style, "style-rule", {"element": "mark"})

    for fmt in mark_rule.findall("format"):
        if fmt.get("attr") == "size":
            fmt.set("value", size_value)
            return
    etree.SubElement(mark_rule, "format", {"attr": "size", "value": size_value})
