"""Basic (Single Pane) Chart Builder."""

import re
from typing import Optional, Union
from lxml import etree

from .builder_base import BaseChartBuilder
from .helpers import _get_or_create_table_style

class BasicChartBuilder(BaseChartBuilder):
    """Builder for basic charts (Bar, Line, Circle, Square)."""

    def __init__(self, editor, worksheet_name: str, mark_type: str,
                 columns: Optional[list[str]] = None,
                 rows: Optional[list[str]] = None,
                 color: Optional[str] = None,
                 size: Optional[str] = None,
                 label: Optional[str] = None,
                 detail: Optional[str] = None,
                 sort_descending: Optional[str] = None,
                 tooltip: Optional[Union[str, list[str]]] = None,
                 filters: Optional[list[dict]] = None,
                 mark_sizing_off: bool = False,
                 axis_fixed_range: Optional[dict] = None,
                 customized_label: Optional[str] = None,
                 color_map: Optional[dict[str, str]] = None,
                 text_format: Optional[dict[str, str]] = None,
                 label_extra: Optional[list[str]] = None,
                 label_runs: Optional[list[dict]] = None) -> None:
        super().__init__(editor)
        self.worksheet_name = worksheet_name
        self.mark_type = mark_type
        self.columns = columns or []
        self.rows = rows or []
        self.color = color
        self.size = size
        self.label = label
        self.detail = detail
        self.sort_descending = sort_descending
        self.tooltip = tooltip
        self.filters = filters
        self.mark_sizing_off = mark_sizing_off
        self.axis_fixed_range = axis_fixed_range
        self.customized_label = customized_label
        self.color_map = color_map
        self.text_format = text_format
        self.label_extra = label_extra or []
        self.label_runs = label_runs or []

    def build(self) -> str:
        # Macro processing
        mark_type, columns, rows = self.editor._apply_chart_macros(
            self.mark_type, self.columns, self.rows, self.color
        )

        ws = self.editor._find_worksheet(self.worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is malformed: missing <table>")
        view = table.find("view")
        if view is None:
            raise ValueError("Malformed structure: missing <view>")

        ds_name = self._datasource.get("name", "")

        all_exprs = self._gather_expressions(
            columns, rows, self.color, self.size, self.label, self.detail, None,
            self.sort_descending, self.tooltip, self.filters, None, None
        )
        for extra_field in self.label_extra:
            if extra_field not in all_exprs:
                all_exprs.append(extra_field)
        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        pane = self._get_or_create_pane(table)
        pane.set("selection-relaxation-option", "selection-relaxation-disallow")
        self._setup_pane(
            pane, mark_type, self.mark_type, instances,
            self.color, self.size, self.label, self.detail, None, self.tooltip,
            False, None, None, ds_name
        )

        # Add extra text encodings for label_extra fields
        if self.label_extra:
            encodings_el = pane.find("encodings")
            if encodings_el is None:
                encodings_el = etree.SubElement(pane, "encodings")
            for extra_field in self.label_extra:
                ci_extra = instances.get(extra_field)
                if ci_extra:
                    extra_ref = self.field_registry.resolve_full_reference(ci_extra.instance_name)
                    text_el = etree.SubElement(encodings_el, "text")
                    text_el.set("column", extra_ref)

        # Mark sizing off
        if self.mark_sizing_off:
            mark_el = pane.find("mark")
            ms_el = etree.Element("mark-sizing")
            ms_el.set("mark-sizing-setting", "marks-scaling-off")
            if mark_el is not None:
                mark_el.addnext(ms_el)
            else:
                pane.append(ms_el)

        # Customized label template (multi-field version)
        if self.customized_label and (self.label or self.label_extra):
            # Build field_map: field name -> full_ref
            field_map = {}
            all_label_fields = ([self.label] if self.label else []) + list(self.label_extra)
            for lf in all_label_fields:
                ci_lf = instances.get(lf)
                if ci_lf:
                    field_map[lf] = self.field_registry.resolve_full_reference(ci_lf.instance_name)

            old_cl = pane.find("customized-label")
            if old_cl is not None:
                pane.remove(old_cl)
            cl = etree.Element("customized-label")

            # Ensure <customized-label> is inserted BEFORE <style> to satisfy DTD
            pane_style = pane.find("style")
            if pane_style is not None:
                pane_style.addprevious(cl)
            else:
                pane.append(cl)

            ft = etree.SubElement(cl, "formatted-text")

            def _add_run(text_value: str) -> None:
                r = etree.SubElement(ft, "run")
                r.set("fontalignment", "2")
                r.set("fontname", "Tableau Medium")
                r.set("fontsize", "8")
                r.text = text_value

            template = self.customized_label
            segments = re.split(r'(<[^>]+>)', template)
            pending_prefix = ""
            for segment in segments:
                # Check if segment looks like <FieldName> and matches a known field
                m = re.match(r'^<([^>]+)>$', segment)
                if m and m.group(1) in field_map:
                    field_name = m.group(1)
                    # Combine pending prefix with "<"
                    _add_run(pending_prefix + "<")
                    _add_run(field_map[field_name])
                    pending_prefix = ">"
                else:
                    pending_prefix += segment
            if pending_prefix:
                _add_run(pending_prefix)

        # Rich-text label runs (takes precedence over customized_label if both set)
        if self.label_runs:
            self._build_rich_label(pane, instances, self.label_runs)

        rows_el = table.find("rows")
        if rows_el is not None:
            rows_el.text = self.editor._build_dimension_shelf(instances, rows) if rows else None

        cols_el = table.find("cols")
        if cols_el is not None:
            cols_el.text = self.editor._build_dimension_shelf(instances, columns) if columns else None

        if self.sort_descending:
             self._add_shelf_sort(view, ds_name, instances, rows, self.sort_descending)

        if self.filters:
            self._add_filters(view, instances, self.filters)

        self.editor._setup_table_style(table, self.mark_type)

        # Axis fixed range
        if self.axis_fixed_range:
            table_style = _get_or_create_table_style(table)
            # Find or create axis style-rule
            axis_rule = None
            for sr in table_style.findall("style-rule"):
                if sr.get("element") == "axis":
                    axis_rule = sr
                    break
            if axis_rule is None:
                axis_rule = etree.SubElement(table_style, "style-rule")
                axis_rule.set("element", "axis")

            # Determine which field to apply the range to (first column measure)
            range_field = self.axis_fixed_range.get("field")
            range_scope = self.axis_fixed_range.get("scope", "cols")
            if not range_field and columns:
                ci = instances.get(columns[0])
                if ci:
                    range_field = self.field_registry.resolve_full_reference(ci.instance_name)
            if range_field:
                enc = etree.SubElement(axis_rule, "encoding")
                enc.set("attr", "space")
                enc.set("class", "0")
                enc.set("field", range_field)
                enc.set("field-type", "quantitative")
                if "min" in self.axis_fixed_range:
                    enc.set("min", str(self.axis_fixed_range["min"]))
                if "max" in self.axis_fixed_range:
                    enc.set("max", str(self.axis_fixed_range["max"]))
                enc.set("range-type", "fixed")
                enc.set("scope", range_scope)
                enc.set("type", "space")

        # Text format (e.g. percentage)
        if self.text_format:
            table_style = _get_or_create_table_style(table)
            cell_rule = etree.SubElement(table_style, "style-rule")
            cell_rule.set("element", "cell")
            for field_expr, fmt_str in self.text_format.items():
                ci = instances.get(field_expr)
                if ci:
                    full_ref = self.field_registry.resolve_full_reference(ci.instance_name)
                    fmt = etree.SubElement(cell_rule, "format")
                    fmt.set("attr", "text-format")
                    fmt.set("field", full_ref)
                    fmt.set("value", fmt_str)

        # Color map (datasource-level palette mapping)
        if self.color_map and self.color:
            ci = instances.get(self.color)
            if ci:
                full_ref = self.field_registry.resolve_full_reference(ci.instance_name)
                ds_style = self._datasource.find("style")
                if ds_style is None:
                    ds_style = etree.Element("style")
                    # DTD requires <style> before semantic-values, date-options, object-graph
                    insert_before = None
                    for tag in ("semantic-values", "date-options", "default-date-format", "object-graph"):
                        insert_before = self._datasource.find(tag)
                        if insert_before is not None:
                            break
                    if insert_before is not None:
                        insert_before.addprevious(ds_style)
                    else:
                        self._datasource.append(ds_style)
                        
                mark_rule = None
                for sr in ds_style.findall("style-rule"):
                    if sr.get("element") == "mark":
                        mark_rule = sr
                        break
                if mark_rule is None:
                    mark_rule = etree.SubElement(ds_style, "style-rule")
                    mark_rule.set("element", "mark")
                color_enc = etree.SubElement(mark_rule, "encoding")
                color_enc.set("attr", "color")
                color_enc.set("field", full_ref)
                color_enc.set("type", "palette")
                for bucket_val, hex_color in self.color_map.items():
                    map_el = etree.SubElement(color_enc, "map")
                    map_el.set("to", hex_color)
                    bucket_el = etree.SubElement(map_el, "bucket")
                    bucket_el.text = f'"{bucket_val}"'

        return f"Configured worksheet '{self.worksheet_name}' as {self.mark_type} chart"
