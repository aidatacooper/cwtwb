"""Shared XML and shelf helpers used by all chart builders.

This module contains stateless utility functions called by builders and by
ChartsMixin directly.  Nothing here mutates the editor root — callers apply
the returned values themselves.

Key helpers:

  apply_chart_macros(editor, mark_type, columns, rows, color)
    → Normalises higher-level patterns (e.g. "Lollipop", "Bubble Chart")
      into primitive mark_type + adjusted shelf lists via pattern_mapping.
      Returns (actual_mark_type, columns, rows).

  build_dimension_shelf(editor, instances, exprs)
    → Builds Tableau's nested shelf expression string from a list of field
      expressions.  Dimensions are joined with "/" (cross-product), measures
      with "*" (inner join).  Example: "(Region / (SUM(Sales) * YEAR(Date)))".

  apply_measure_values(editor, worksheet_name, measure_values)
    → Writes <measure-values-column> declarations into the worksheet view
      when using Measure Names / Measure Values patterns.

  apply_worksheet_style(editor, worksheet_name, **style_kwargs)
    → Top-level dispatcher for all worksheet-level styling options
      (background color, axis/grid/border visibility, cell formats, etc.).
      Delegates to _apply_style_* helpers within this module.

  setup_table_style(table, options)
    → Writes <style> / <style-rule> elements directly into a <table> element.

  setup_mapsources(editor, worksheet_name)
    → Writes the <mapsource> element required for geographic worksheets.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lxml import etree

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
    from .dispatcher import normalize_chart_pattern

    resolution = normalize_chart_pattern(mark_type, columns=columns, rows=rows, color=color)
    return resolution.actual_mark_type, resolution.columns, resolution.rows


def build_dimension_shelf(editor, instances: dict[str, "ColumnInstance"], exprs: list[str]) -> str:
    """Build Tableau's nested shelf expression for dimensions and measures."""

    parts: list[str] = []
    ci_list: list["ColumnInstance"] = []
    for expr in exprs:
        ci = instances.get(expr)
        if ci is None:
            normalized_expr = editor.field_registry.default_view_expression(expr)
            ci = instances.get(normalized_expr)
        if ci:
            parts.append(editor.field_registry.resolve_full_reference(ci.instance_name))
            ci_list.append(ci)

    if not parts:
        return ""

    def build_nested(idx: int) -> str:
        """Recursively build nested shelf text using Tableau operator semantics."""
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


# Keys inside a style specification that select the target of a <format>
# element rather than naming a style attribute. They must never be emitted as
# the ``attr`` name, which produced values outside the XSD enumeration.
_STYLE_NON_ATTR_KEYS = frozenset({"_field_ref", "field", "scope", "data_class", "data-class"})


def _style_attr_value_pairs(spec: dict) -> list[tuple[str, object]]:
    """Return (attr, value) pairs for a style specification.

    Two shapes are accepted, matching the documented API:

    * explicit: ``{"attr": "height", "value": 19}`` — the attr/value keys
      name the attribute, they are not themselves attributes.
    * shorthand: ``{"height": 19, "font-weight": "bold"}`` — every
      non-selector key is an attribute name.
    """
    if "attr" in spec and "value" in spec:
        return [(str(spec["attr"]), spec["value"])]
    return [
        (str(key), value)
        for key, value in spec.items()
        if key not in _STYLE_NON_ATTR_KEYS
    ]


def _style_selectors(spec: dict) -> dict[str, str]:
    """Return the non-attr selectors for a style specification as attributes."""
    selectors: dict[str, str] = {}
    for key in ("scope", "data_class", "data-class"):
        value = spec.get(key)
        if value is not None:
            selectors[key.replace("_", "-")] = str(value)
    return selectors


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
    hide_sort_controls: bool | None = None,
    hide_droplines: bool = False,
    hide_reflines: bool = False,
    hide_table_dividers: bool = False,
    table_dividers: list[dict] | None = None,
    disable_tooltip: bool = False,
    show_column_totals: bool = False,
    show_row_totals: bool = False,
    pane_cell_style: dict | None = None,
    pane_datalabel_style: dict | None = None,
    pane_mark_style: dict | None = None,
    pane_trendline_hidden: bool = False,
    panes_style: dict[str | int, dict] | list[dict] | None = None,
    resolved_label_formats: list[dict] | None = None,
    resolved_cell_formats: list[dict] | None = None,
    pane_formats: list[dict] | None = None,
    resolved_header_formats: list[dict] | None = None,
    table_formats: list[dict] | None = None,
    legend_style: dict | None = None,
    resolved_axis_style: dict | None = None,
) -> None:
    """Apply worksheet-level styling: background, axis/grid/border visibility."""

    if hide_sort_controls is not None:
        if not isinstance(hide_sort_controls, bool):
            raise ValueError("hide_sort_controls must be boolean")
        view = table.find("view")
        if view is not None:
            for control in view.findall("hide-sort-controls"):
                view.remove(control)
            if hide_sort_controls:
                control = etree.Element("hide-sort-controls")
                anchor = next((view.find(tag) for tag in ("slices", "aggregation") if view.find(tag) is not None), None)
                if anchor is None:
                    view.append(control)
                else:
                    anchor.addprevious(control)

    # Column / Row totals visibility
    if show_column_totals:
        cols_el = table.find("cols")
        if cols_el is not None:
            cols_el.set("total", "true")
    if show_row_totals:
        rows_el = table.find("rows")
        if rows_el is not None:
            rows_el.set("total", "true")

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

    if table_formats:
        rule = next((item for item in table_style.findall("style-rule") if item.get("element") == "table"), None)
        if rule is None:
            rule = etree.SubElement(table_style, "style-rule", element="table")
        for specification in table_formats:
            attr = str(specification["attr"]).replace("_", "-")
            scope = specification.get("scope")
            for old in list(rule.findall("format")):
                if old.get("attr") == attr and old.get("scope") == scope:
                    rule.remove(old)
            fmt = etree.SubElement(rule, "format", attr=attr, value=str(specification["value"]))
            if scope:
                fmt.set("scope", scope)

    if legend_style:
        rule = next((item for item in table_style.findall("style-rule") if item.get("element") == "legend"), None)
        if rule is None:
            rule = etree.SubElement(table_style, "style-rule", element="legend")
        for key, value in legend_style.items():
            attr = key.replace("_", "-")
            for old in list(rule.findall("format")):
                if old.get("attr") == attr:
                    rule.remove(old)
            etree.SubElement(rule, "format", attr=attr, value=str(value).lower() if isinstance(value, bool) else str(value))

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
    elif table_dividers:
        rule = etree.SubElement(table_style, "style-rule")
        rule.set("element", "table-div")
        for div_spec in table_dividers:
            scope = div_spec.get("scope")
            for attr, val in div_spec.items():
                if attr in ("scope", "_field_ref"):
                    continue
                fmt = etree.SubElement(rule, "format")
                fmt.set("attr", attr.replace("_", "-"))
                if scope:
                    fmt.set("scope", scope)
                fmt.set("value", str(val))

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
            selectors = _style_selectors(lf)
            for attr, val in _style_attr_value_pairs(lf):
                fmt = etree.SubElement(label_rule, "format", **selectors)
                fmt.set("attr", attr.replace("_", "-"))
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
            selectors = _style_selectors(cf)
            for attr, val in _style_attr_value_pairs(cf):
                fmt = etree.SubElement(cell_rule, "format", **selectors)
                fmt.set("attr", attr.replace("_", "-"))
                if field_ref:
                    fmt.set("field", field_ref)
                fmt.set("value", str(val))

    if pane_formats:
        pane_rule = table_style.find("style-rule[@element='pane']")
        if pane_rule is None:
            pane_rule = etree.SubElement(table_style, "style-rule", element="pane")
        for spec in pane_formats:
            selectors = {key.replace("_", "-"): str(value) for key, value in spec.items() if key in ("scope", "data_class", "data-class")}
            values = {spec["attr"]: spec["value"]} if "attr" in spec and "value" in spec else {key: value for key, value in spec.items() if key not in ("scope", "data_class", "data-class")}
            for attr, value in values.items():
                fmt = etree.SubElement(pane_rule, "format", **selectors)
                fmt.set("attr", str(attr).replace("_", "-"))
                fmt.set("value", str(value))

    # Table-level header formats (height, width, total-label, etc.)
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
            scope = hf.get("scope")
            data_class = hf.get("data_class") or hf.get("data-class")
            attr = hf.get("attr")
            value = hf.get("value")

            if attr is not None and value is not None:
                fmt = etree.SubElement(header_rule, "format")
                fmt.set("attr", str(attr).replace("_", "-"))
                if field_ref:
                    fmt.set("field", field_ref)
                if scope:
                    fmt.set("scope", scope)
                if data_class:
                    fmt.set("data-class", data_class)
                fmt.set("value", str(value))
            else:
                for k, v in hf.items():
                    if k in ("_field_ref", "scope", "data_class", "data-class"):
                        continue
                    fmt = etree.SubElement(header_rule, "format")
                    fmt.set("attr", str(k).replace("_", "-"))
                    if field_ref:
                        fmt.set("field", field_ref)
                    if scope:
                        fmt.set("scope", scope)
                    if data_class:
                        fmt.set("data-class", data_class)
                    fmt.set("value", str(v))

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
            if key in ("per_field", "encodings"):
                continue
            fmt = etree.SubElement(axis_rule, "format")
            fmt.set("attr", key)
            fmt.set("value", str(val))
        for specification in resolved_axis_style.get("encodings", []):
            attributes = {"attr": "space", "field-type": "quantitative", "type": "space", **specification}
            for existing in list(axis_rule.findall("encoding")):
                if existing.get("field") == attributes["field"] and existing.get("scope", "") == attributes.get("scope", "") and existing.get("class", "") == attributes.get("class", ""):
                    axis_rule.remove(existing)
            etree.SubElement(axis_rule, "encoding", attributes)
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

    def _apply_pane_element_style(pane_el: etree._Element, p_spec: dict) -> None:
        mark_class = p_spec.get("mark_class")
        if mark_class:
            m_el = pane_el.find("mark")
            if m_el is None:
                m_el = etree.SubElement(pane_el, "mark")
            m_el.set("class", mark_class)

        p_style = pane_el.find("style")
        if p_style is None:
            p_style = etree.SubElement(pane_el, "style")

        cell_style = p_spec.get("cell_style") or p_spec.get("pane_cell_style")
        if cell_style:
            c_rule = etree.SubElement(p_style, "style-rule")
            c_rule.set("element", "cell")
            for attr, val in cell_style.items():
                fmt = etree.SubElement(c_rule, "format")
                fmt.set("attr", str(attr).replace("_", "-"))
                fmt.set("value", str(val))

        datalabel_style = p_spec.get("datalabel_style") or p_spec.get("pane_datalabel_style")
        if datalabel_style:
            dl_rule = etree.SubElement(p_style, "style-rule")
            dl_rule.set("element", "datalabel")
            for attr, val in datalabel_style.items():
                fmt = etree.SubElement(dl_rule, "format")
                fmt.set("attr", str(attr).replace("_", "-"))
                fmt.set("value", str(val))

        mark_style = p_spec.get("mark_style") or p_spec.get("pane_mark_style")
        if mark_style:
            m_rule = None
            for sr in p_style.findall("style-rule"):
                if sr.get("element") == "mark":
                    m_rule = sr
                    break
            if m_rule is None:
                m_rule = etree.SubElement(p_style, "style-rule")
                m_rule.set("element", "mark")
            for attr, val in mark_style.items():
                attr_name = str(attr).replace("_", "-")
                for existing_fmt in list(m_rule.findall("format")):
                    if existing_fmt.get("attr") == attr_name:
                        m_rule.remove(existing_fmt)
                fmt = etree.SubElement(m_rule, "format")
                fmt.set("attr", attr_name)
                fmt.set("value", str(val))

    # Single-pane styles (cell, datalabel, mark, trendline)
    if pane_cell_style or pane_datalabel_style or pane_mark_style or pane_trendline_hidden:
        panes_el = table.find("panes")
        pane = panes_el.find("pane") if panes_el is not None else None
        if pane is None:
            pane = table.find("pane")
        if pane is not None:
            _apply_pane_element_style(
                pane,
                {
                    "pane_cell_style": pane_cell_style,
                    "pane_datalabel_style": pane_datalabel_style,
                    "pane_mark_style": pane_mark_style,
                },
            )
            if pane_trendline_hidden:
                pane_style_el = pane.find("style")
                if pane_style_el is None:
                    pane_style_el = etree.SubElement(pane, "style")
                tl_rule = etree.SubElement(pane_style_el, "style-rule")
                tl_rule.set("element", "trendline")
                for attr, val in [("stroke-size", "0"), ("line-visibility", "off")]:
                    fmt = etree.SubElement(tl_rule, "format")
                    fmt.set("attr", attr)
                    fmt.set("value", val)

    # Multi-pane styling support: dict keyed by pane id ("0", "1", 0, etc.) or list of dicts with 'id' or matching order
    if panes_style:
        all_panes = table.findall(".//panes/pane")
        if not all_panes:
            all_panes = table.findall(".//pane")

        if isinstance(panes_style, dict):
            for pid_key, spec in panes_style.items():
                target_pane = None
                str_pid = str(pid_key)
                for p in all_panes:
                    if p.get("id") == str_pid:
                        target_pane = p
                        break
                if target_pane is None and str_pid.isdigit():
                    idx = int(str_pid)
                    if 0 <= idx < len(all_panes):
                        target_pane = all_panes[idx]
                if target_pane is not None:
                    _apply_pane_element_style(target_pane, spec)
        elif isinstance(panes_style, list):
            for i, spec in enumerate(panes_style):
                target_pane = None
                if "id" in spec:
                    spec_id = str(spec["id"])
                    for p in all_panes:
                        if p.get("id") == spec_id:
                            target_pane = p
                            break
                elif i < len(all_panes):
                    target_pane = all_panes[i]
                if target_pane is not None:
                    _apply_pane_element_style(target_pane, spec)


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
    # Measure Values adds the measure-name shelf; it must not erase an
    # existing row dimension. Clearing rows makes a text table collapse into
    # one aggregate instead of one row per dimension member.

    old_enc = pane.find("encodings")
    enc_el = old_enc if old_enc is not None else etree.Element("encodings")
    for old in list(enc_el.findall("text")):
        if old.get("column") == f"[{ds_name}].[Multiple Values]":
            enc_el.remove(old)
    text_el = etree.SubElement(enc_el, "text")
    text_el.set("column", f"[{ds_name}].[Multiple Values]")
    customized_label = pane.find("customized-label")
    if (
        customized_label is not None
        and "[:Measure Names]" in etree.tostring(customized_label, encoding="unicode")
        and not any(
            e.get("column") == f"[{ds_name}].[:Measure Names]"
            for e in enc_el.findall("text")
        )
    ):
        etree.SubElement(enc_el, "text", column=f"[{ds_name}].[:Measure Names]")

    style_el = pane.find("style")
    if old_enc is None:
        if style_el is not None:
            style_el.addprevious(enc_el)
        else:
            pane.append(enc_el)

    user_ns = "{http://www.tableausoftware.com/xml/user}"
    measure_refs: list[str] = []
    for mv_expr in measure_values:
        ci = instances.get(mv_expr)
        if ci is None:
            normalized_expr = editor.field_registry.default_view_expression(mv_expr)
            ci = instances.get(normalized_expr)
        if ci is not None:
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
            member.set("member", f'"{ref}"')  # Measure names are always strings

        insert_before = None
        for tag in ("sort", "perspectives", "shelf-sorts", "slices", "aggregation"):
            insert_before = view.find(tag)
            if insert_before is not None:
                break
        if insert_before is not None:
            insert_before.addprevious(filter_el)
        else:
            view.append(filter_el)

    for old in list(view.findall("manual-sort")):
        if old.get("column") == f"[{ds_name}].[:Measure Names]":
            view.remove(old)
    if measure_refs:
        sort = etree.Element("manual-sort", column=f"[{ds_name}].[:Measure Names]", direction="ASC")
        dictionary = etree.SubElement(sort, "dictionary")
        for ref in measure_refs:
            etree.SubElement(dictionary, "bucket").text = f'"{ref}"'
        anchor = next((view.find(tag) for tag in ("slices", "aggregation") if view.find(tag) is not None), None)
        if anchor is not None:
            anchor.addprevious(sort)
        else:
            view.append(sort)

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
