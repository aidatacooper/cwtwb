"""Shared chart helper functions used by chart builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

from .pattern_mapping import normalize_chart_pattern

if TYPE_CHECKING:
    from ..field_registry import ColumnInstance


def apply_chart_macros(
    editor,
    mark_type: str,
    columns: list[str],
    rows: list[str],
    color: str | None,
) -> tuple[str, list[str], list[str]]:
    """Normalize higher-level chart patterns onto builder-compatible values."""

    resolution = normalize_chart_pattern(mark_type, columns=columns, rows=rows, color=color)
    return resolution.actual_mark_type, resolution.columns, resolution.rows


def build_dimension_shelf(editor, instances: dict[str, "ColumnInstance"], exprs: list[str]) -> str:
    """Build Tableau's nested shelf expression for dimensions and measures."""

    parts: list[str] = []
    ci_list: list["ColumnInstance"] = []
    for expr in exprs:
        ci = instances.get(expr)
        if ci:
            parts.append(editor.field_registry.resolve_full_reference(ci.instance_name))
            ci_list.append(ci)

    if not parts:
        return ""

    def build_nested(idx: int) -> str:
        if idx == len(parts) - 1:
            return parts[idx]
        op = " * " if ci_list[idx + 1].ci_type == "quantitative" else " / "
        right_side = build_nested(idx + 1)
        return f"({parts[idx]}{op}{right_side})"

    return build_nested(0)


def setup_table_style(table: etree._Element, mark_type: str) -> None:
    """Ensure table-level style exists and apply mark-specific rules."""

    table_style = _get_or_create_table_style(table)

    if mark_type in ("Tree Map", "Bubble Chart"):
        axis_rule = etree.SubElement(table_style, "style-rule")
        axis_rule.set("element", "axis")
        fmt = etree.SubElement(axis_rule, "format")
        fmt.set("attr", "line-visibility")
        fmt.set("value", "off")

        for el_name in ("gridline", "zeroline"):
            rule = etree.SubElement(table_style, "style-rule")
            rule.set("element", el_name)
            fmt = etree.SubElement(rule, "format")
            fmt.set("attr", "line-visibility")
            fmt.set("value", "off")

        ws_rule = etree.SubElement(table_style, "style-rule")
        ws_rule.set("element", "worksheet")
        for scope in ("cols", "rows"):
            fmt = etree.SubElement(ws_rule, "format")
            fmt.set("attr", "display-field-labels")
            fmt.set("scope", scope)
            fmt.set("value", "false")


def setup_mapsources(editor, view: etree._Element) -> None:
    """Ensure worksheet and workbook map sources exist for map charts."""

    for old_ms in view.findall("mapsources"):
        view.remove(old_ms)
    mapsources = etree.Element("mapsources")
    ms = etree.SubElement(mapsources, "mapsource")
    ms.set("name", "Tableau")
    view_ds = view.find("datasources")
    if view_ds is not None:
        view_ds.addnext(mapsources)
    else:
        view.insert(0, mapsources)

    if editor._parameters and view_ds is not None:
        params_ds_ref = view_ds.find("datasource[@name='Parameters']")
        if params_ds_ref is None:
            pds = etree.SubElement(view_ds, "datasource")
            pds.set("caption", "Parameters")
            pds.set("name", "Parameters")

    root_ms = editor.root.find("mapsources")
    if root_ms is None:
        root_ms = etree.Element("mapsources")
        ds_el = editor.root.find("datasources")
        if ds_el is not None:
            ds_el.addnext(root_ms)
        else:
            editor.root.append(root_ms)
        rms = etree.SubElement(root_ms, "mapsource")
        rms.set("name", "Tableau")


def _get_or_create_table_style(table: etree._Element) -> etree._Element:
    """Get existing or create new <style> element on the table."""
    table_style = table.find("style")
    if table_style is None:
        table_style = etree.Element("style")
        insert_before = None
        for tag in ("panes", "pane", "mark-layout", "rows", "cols", "table-calc-densification"):
            insert_before = table.find(tag)
            if insert_before is not None:
                break
        if insert_before is not None:
            insert_before.addprevious(table_style)
        else:
            table.append(table_style)
    return table_style


def apply_worksheet_style(
    table: etree._Element,
    *,
    background_color: str | None = None,
    hide_axes: bool = False,
    hide_gridlines: bool = False,
    hide_zeroline: bool = False,
    hide_borders: bool = False,
    hide_band_color: bool = False,
    hide_row_label_ref: str | None = None,
    hide_col_field_labels: bool = False,
    hide_row_field_labels: bool = False,
    hide_droplines: bool = False,
    hide_reflines: bool = False,
    hide_table_dividers: bool = False,
    disable_tooltip: bool = False,
    pane_cell_style: dict | None = None,
    pane_datalabel_style: dict | None = None,
    pane_mark_style: dict | None = None,
    pane_trendline_hidden: bool = False,
    resolved_label_formats: list[dict] | None = None,
    resolved_cell_formats: list[dict] | None = None,
    resolved_header_formats: list[dict] | None = None,
    resolved_axis_style: dict | None = None,
) -> None:
    """Apply worksheet-level styling: background, axis/grid/border visibility."""

    # Tooltip disable (goes directly into table)
    if disable_tooltip:
        for old_ts in table.findall("tooltip-style"):
            table.remove(old_ts)
        ts = etree.SubElement(table, "tooltip-style")
        ts.set("tooltip-mode", "none")

    table_style = _get_or_create_table_style(table)

    if background_color:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "table")
        fmt = etree.SubElement(rule, "format")
        fmt.set("attr", "background-color")
        fmt.set("value", background_color)

    if hide_axes:
        # Find existing axis rule (e.g. from dual-axis builder) or create new
        rule = None
        for sr in table_style.findall("style-rule"):
            if sr.get("element") == "axis":
                rule = sr
                break
        if rule is None:
            rule = etree.SubElement(table_style, "style-rule")
            rule.set("element", "axis")
        fmt = etree.SubElement(rule, "format")
        fmt.set("attr", "display")
        fmt.set("value", "false")

    if hide_gridlines:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "gridline")
        fmt = etree.SubElement(rule, "format")
        fmt.set("attr", "line-visibility")
        fmt.set("value", "off")

    if hide_zeroline:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "zeroline")
        fmt = etree.SubElement(rule, "format")
        fmt.set("attr", "line-visibility")
        fmt.set("value", "off")
        fmt2 = etree.SubElement(rule, "format")
        fmt2.set("attr", "stroke-size")
        fmt2.set("value", "0")

    if hide_borders:
        for element_name in ("header", "pane"):
            rule = etree.SubElement(table_style, "style-rule")
            rule.set("element", element_name)
            fmt_w = etree.SubElement(rule, "format")
            fmt_w.set("attr", "border-width")
            fmt_w.set("value", "0")
            fmt_s = etree.SubElement(rule, "format")
            fmt_s.set("attr", "border-style")
            fmt_s.set("value", "none")

    if hide_band_color:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "pane")
        fmt = etree.SubElement(rule, "format")
        fmt.set("attr", "band-color")
        fmt.set("value", "#00000000")

    if hide_row_label_ref:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "label")
        fmt = etree.SubElement(rule, "format")
        fmt.set("attr", "display")
        fmt.set("field", hide_row_label_ref)
        fmt.set("value", "false")

    if hide_col_field_labels:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "worksheet")
        fmt = etree.SubElement(rule, "format")
        fmt.set("attr", "display-field-labels")
        fmt.set("scope", "cols")
        fmt.set("value", "false")

    if hide_row_field_labels:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "worksheet")
        fmt = etree.SubElement(rule, "format")
        fmt.set("attr", "display-field-labels")
        fmt.set("scope", "rows")
        fmt.set("value", "false")

    if hide_droplines:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "dropline")
        for attr, val in [("stroke-size", "0"), ("line-visibility", "off")]:
            fmt = etree.SubElement(rule, "format")
            fmt.set("attr", attr)
            fmt.set("value", val)

    if hide_reflines:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "refline")
        for attr, val in [("stroke-size", "0"), ("line-visibility", "off")]:
            fmt = etree.SubElement(rule, "format")
            fmt.set("attr", attr)
            fmt.set("value", val)

    if hide_table_dividers:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "table-div")
        for scope in ("rows", "cols"):
            for attr, val in [("stroke-size", "0"), ("line-visibility", "off")]:
                fmt = etree.SubElement(rule, "format")
                fmt.set("attr", attr)
                fmt.set("scope", scope)
                fmt.set("value", val)

    # Per-field label formats: each entry has _field_ref + attr→value pairs
    if resolved_label_formats:
        label_rule = None
        for sr in table_style.findall("style-rule"):
            if sr.get("element") == "label":
                label_rule = sr
                break
        if label_rule is None:
            label_rule = etree.SubElement(table_style, "style-rule")
            label_rule.set("element", "label")
        for lf in resolved_label_formats:
            field_ref = lf.get("_field_ref")
            for attr, val in lf.items():
                if attr == "_field_ref":
                    continue
                fmt = etree.SubElement(label_rule, "format")
                fmt.set("attr", attr)
                if field_ref:
                    fmt.set("field", field_ref)
                fmt.set("value", str(val))

    # Per-field table-level cell formats (e.g. font-family, color per field in table/crosstab)
    if resolved_cell_formats:
        cell_rule = None
        for sr in table_style.findall("style-rule"):
            if sr.get("element") == "cell":
                cell_rule = sr
                break
        if cell_rule is None:
            cell_rule = etree.SubElement(table_style, "style-rule")
            cell_rule.set("element", "cell")
        for cf in resolved_cell_formats:
            field_ref = cf.get("_field_ref")
            for attr, val in cf.items():
                if attr == "_field_ref":
                    continue
                fmt = etree.SubElement(cell_rule, "format")
                fmt.set("attr", attr)
                if field_ref:
                    fmt.set("field", field_ref)
                fmt.set("value", str(val))

    # Per-field table-level header formats (height, width per field)
    if resolved_header_formats:
        header_rule = None
        for sr in table_style.findall("style-rule"):
            if sr.get("element") == "header":
                header_rule = sr
                break
        if header_rule is None:
            header_rule = etree.SubElement(table_style, "style-rule")
            header_rule.set("element", "header")
        for hf in resolved_header_formats:
            field_ref = hf.get("_field_ref")
            for attr, val in hf.items():
                if attr == "_field_ref":
                    continue
                fmt = etree.SubElement(header_rule, "format")
                fmt.set("attr", attr)
                if field_ref:
                    fmt.set("field", field_ref)
                fmt.set("value", str(val))

    # Axis style: any field-less formats + per-field formats
    # Find existing axis rule (e.g. from dual-axis builder) or create new one
    if resolved_axis_style:
        axis_rule = None
        for sr in table_style.findall("style-rule"):
            if sr.get("element") == "axis":
                axis_rule = sr
                break
        if axis_rule is None:
            axis_rule = etree.SubElement(table_style, "style-rule")
            axis_rule.set("element", "axis")
        for key, val in resolved_axis_style.items():
            if key == "per_field":
                continue
            fmt = etree.SubElement(axis_rule, "format")
            fmt.set("attr", key)
            fmt.set("value", str(val))
        for pf in resolved_axis_style.get("per_field", []):
            field_ref = pf.get("_field_ref", "")
            attr = pf.get("attr", "")
            val = str(pf.get("value", ""))
            fmt = etree.SubElement(axis_rule, "format")
            fmt.set("attr", attr)
            if field_ref:
                fmt.set("field", field_ref)
            if "class" in pf:
                fmt.set("class", str(pf["class"]))
            if "scope" in pf:
                fmt.set("scope", pf["scope"])
            fmt.set("value", val)

    # Pane-level styles (cell, datalabel, mark, trendline)
    if pane_cell_style or pane_datalabel_style or pane_mark_style or pane_trendline_hidden:
        panes_el = table.find("panes")
        pane = panes_el.find("pane") if panes_el is not None else None
        if pane is None:
            pane = table.find("pane")
        if pane is not None:
            pane_style_el = pane.find("style")
            if pane_style_el is None:
                pane_style_el = etree.SubElement(pane, "style")

            if pane_cell_style:
                rule = etree.SubElement(pane_style_el, "style-rule")
                rule.set("element", "cell")
                for attr, val in pane_cell_style.items():
                    fmt = etree.SubElement(rule, "format")
                    fmt.set("attr", attr)
                    fmt.set("value", str(val))

            if pane_datalabel_style:
                rule = etree.SubElement(pane_style_el, "style-rule")
                rule.set("element", "datalabel")
                for attr, val in pane_datalabel_style.items():
                    fmt = etree.SubElement(rule, "format")
                    fmt.set("attr", attr)
                    fmt.set("value", str(val))

            if pane_mark_style:
                mark_rule = None
                for sr in pane_style_el.findall("style-rule"):
                    if sr.get("element") == "mark":
                        mark_rule = sr
                        break
                if mark_rule is None:
                    mark_rule = etree.SubElement(pane_style_el, "style-rule")
                    mark_rule.set("element", "mark")
                for attr, val in pane_mark_style.items():
                    # Replace existing format with same attr to avoid duplicates
                    for existing_fmt in list(mark_rule.findall("format")):
                        if existing_fmt.get("attr") == attr:
                            mark_rule.remove(existing_fmt)
                    fmt = etree.SubElement(mark_rule, "format")
                    fmt.set("attr", attr)
                    fmt.set("value", str(val))

            if pane_trendline_hidden:
                tl_rule = etree.SubElement(pane_style_el, "style-rule")
                tl_rule.set("element", "trendline")
                for attr, val in [("stroke-size", "0"), ("line-visibility", "off")]:
                    fmt = etree.SubElement(tl_rule, "format")
                    fmt.set("attr", attr)
                    fmt.set("value", val)


def apply_measure_values(
    editor,
    view: etree._Element,
    table: etree._Element,
    pane: etree._Element,
    ds_name: str,
    instances: dict[str, "ColumnInstance"],
    measure_values: list[str],
) -> None:
    """Apply Measure Names / Measure Values text-table behavior."""

    cols_el = table.find("cols")
    if cols_el is not None:
        cols_el.text = f"[{ds_name}].[:Measure Names]"

    rows_el = table.find("rows")
    if rows_el is not None:
        rows_el.text = None

    old_enc = pane.find("encodings")
    if old_enc is not None:
        pane.remove(old_enc)

    enc_el = etree.Element("encodings")
    text_el = etree.SubElement(enc_el, "text")
    text_el.set("column", f"[{ds_name}].[Multiple Values]")

    style_el = pane.find("style")
    if style_el is not None:
        style_el.addprevious(enc_el)
    else:
        pane.append(enc_el)

    user_ns = "{http://www.tableausoftware.com/xml/user}"
    measure_refs: list[str] = []
    for mv_expr in measure_values:
        if mv_expr in instances:
            ci = instances[mv_expr]
            full_ref = editor.field_registry.resolve_full_reference(ci.instance_name)
            measure_refs.append(full_ref)

    if measure_refs:
        filter_el = etree.Element("filter")
        filter_el.set("class", "categorical")
        filter_el.set("column", f"[{ds_name}].[:Measure Names]")

        gf = etree.SubElement(filter_el, "groupfilter")
        gf.set("function", "union")
        gf.set(f"{user_ns}ui-domain", "database")
        gf.set(f"{user_ns}ui-enumeration", "inclusive")
        gf.set(f"{user_ns}ui-marker", "enumerate")

        for ref in measure_refs:
            member = etree.SubElement(gf, "groupfilter")
            member.set("function", "member")
            member.set("level", "[:Measure Names]")
            member.set("member", f'"{ref}"')

        insert_before = None
        for tag in ("sort", "perspectives", "slices", "aggregation"):
            insert_before = view.find(tag)
            if insert_before is not None:
                break
        if insert_before is not None:
            insert_before.addprevious(filter_el)
        else:
            view.append(filter_el)

    table_style = table.find("style")
    if table_style is None:
        table_style = etree.SubElement(table, "style")

    cell_rule = etree.SubElement(table_style, "style-rule")
    cell_rule.set("element", "cell")
    for attr, val in (("text-align", "center"), ("font-weight", "bold"), ("font-size", "12")):
        fmt = etree.SubElement(cell_rule, "format")
        fmt.set("attr", attr)
        fmt.set("value", val)

    label_rule = etree.SubElement(table_style, "style-rule")
    label_rule.set("element", "label")
    for attr, val in (("text-align", "center"), ("font-size", "10")):
        fmt = etree.SubElement(label_rule, "format")
        fmt.set("attr", attr)
        fmt.set("value", val)

    div_rule = etree.SubElement(table_style, "style-rule")
    div_rule.set("element", "table-div")
    for scope in ("rows", "cols"):
        fmt = etree.SubElement(div_rule, "format")
        fmt.set("attr", "line-visibility")
        fmt.set("scope", scope)
        fmt.set("value", "off")

