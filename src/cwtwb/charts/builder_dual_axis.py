"""Dual Axis Chart Builder."""

from typing import Optional, Union
from lxml import etree

from .builder_base import BaseChartBuilder

class DualAxisChartBuilder(BaseChartBuilder):
    """Builder for Dual-Axis charts (Lollipop, Combo, Donut)."""

    def __init__(self, editor, worksheet_name: str,
                 mark_type_1: str = "Bar",
                 mark_type_2: str = "Line",
                 columns: Optional[list[str]] = None,
                 rows: Optional[list[str]] = None,
                 dual_axis_shelf: str = "rows",
                 color_1: Optional[str] = None,
                 size_1: Optional[str] = None,
                 label_1: Optional[str] = None,
                 detail_1: Optional[str] = None,
                 color_2: Optional[str] = None,
                 size_2: Optional[str] = None,
                 label_2: Optional[str] = None,
                 detail_2: Optional[str] = None,
                 synchronized: bool = True,
                 sort_descending: Optional[str] = None,
                 filters: Optional[list[dict]] = None,
                 wedge_size_1: Optional[str] = None,
                 wedge_size_2: Optional[str] = None,
                 show_labels: bool = True,
                 hide_axes: bool = False,
                 hide_zeroline: bool = False,
                 mark_sizing_off: bool = False,
                 size_value_1: Optional[str] = None,
                 size_value_2: Optional[str] = None,
                 mark_color_2: Optional[str] = None,
                 mark_color_1: Optional[str] = None,
                 reverse_axis_1: bool = False,
                 extra_axes: Optional[list[dict]] = None,
                 color_map_1: Optional[dict[str, str]] = None,
                 ) -> None:
        super().__init__(editor)
        self.worksheet_name = worksheet_name
        self.mark_type_1 = mark_type_1
        self.mark_type_2 = mark_type_2
        self.columns = columns or []
        self.rows = rows or []
        self.dual_axis_shelf = dual_axis_shelf
        self.color_1 = color_1
        self.size_1 = size_1
        self.label_1 = label_1
        self.detail_1 = detail_1
        self.color_2 = color_2
        self.size_2 = size_2
        self.label_2 = label_2
        self.detail_2 = detail_2
        self.synchronized = synchronized
        self.sort_descending = sort_descending
        self.filters = filters
        self.wedge_size_1 = wedge_size_1
        self.wedge_size_2 = wedge_size_2
        self.show_labels = show_labels
        self.hide_axes = hide_axes
        self.hide_zeroline = hide_zeroline
        self.mark_sizing_off = mark_sizing_off
        self.size_value_1 = size_value_1
        self.size_value_2 = size_value_2
        self.mark_color_2 = mark_color_2
        self.mark_color_1 = mark_color_1
        self.reverse_axis_1 = reverse_axis_1
        self.extra_axes = extra_axes or []
        self.color_map_1 = color_map_1 or {}

    def build(self) -> str:
        if self.dual_axis_shelf == "rows":
            if len(self.rows) < 2:
                raise ValueError("dual_axis_shelf 'rows' must have at least 2 expressions to fold.")
            measure_1 = self.rows[-2]
            measure_2 = self.rows[-1]
        elif self.dual_axis_shelf in ("columns", "cols"):
            if len(self.columns) < 2:
                raise ValueError("dual_axis_shelf 'cols' must have at least 2 expressions to fold.")
            measure_1 = self.columns[-2]
            measure_2 = self.columns[-1]
        else:
            raise ValueError("dual_axis_shelf must be 'rows', 'columns', or 'cols'")

        ws = self.editor._find_worksheet(self.worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is malformed: missing <table>")
        view = table.find("view")
        if view is None:
            raise ValueError("Malformed structure: missing <view>")

        ds_name = self._datasource.get("name", "")

        USER_NS = "{http://www.tableausoftware.com/xml/user}"

        # Gather all expressions
        all_exprs = self._gather_expressions(
            self.columns, self.rows, self.color_1, self.size_1, self.label_1, self.detail_1, self.wedge_size_1, self.sort_descending, None, self.filters, None, None
        )
        for enc in (self.color_2, self.size_2, self.label_2, self.detail_2, self.wedge_size_2):
            if enc and enc not in all_exprs:
                all_exprs.append(enc)

        # Gather extra_axes expressions
        for ea in self.extra_axes:
            ea_measure = ea.get("measure")
            if ea_measure and ea_measure not in all_exprs:
                all_exprs.append(ea_measure)
            ea_label = ea.get("label")
            if ea_label and ea_label not in (":Measure Names", "Multiple Values") and ea_label not in all_exprs:
                all_exprs.append(ea_label)
            ea_color = ea.get("color")
            if ea_color and ea_color not in (":Measure Names", "Multiple Values") and ea_color not in all_exprs:
                all_exprs.append(ea_color)
            ea_size = ea.get("size")
            if ea_size and ea_size not in (":Measure Names", "Multiple Values") and ea_size not in all_exprs:
                all_exprs.append(ea_size)
            for mv in ea.get("measure_values", []):
                if mv not in all_exprs:
                    all_exprs.append(mv)

        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        # Remove old pane/panes
        old_pane = table.find("pane")
        old_panes = table.find("panes")
        
        insert_idx = len(table)
        if old_pane is not None:
            insert_idx = list(table).index(old_pane)
            table.remove(old_pane)
        elif old_panes is not None:
            insert_idx = list(table).index(old_panes)
            table.remove(old_panes)
        else:
            for tag in ("mark-layout", "rows", "cols", "table-calc-densification"):
                el = table.find(tag)
                if el is not None:
                    idx = list(table).index(el)
                    if idx < insert_idx:
                        insert_idx = idx

        panes_el = etree.Element("panes")
        table.insert(insert_idx, panes_el)
        
        axis_attr_name = "y-axis-name" if self.dual_axis_shelf == "rows" else "x-axis-name"
        axis_attr_index = "y-index" if self.dual_axis_shelf == "rows" else "x-index"
        
        ci_m1 = instances[measure_1]
        ci_m2 = instances[measure_2]
        ref_m1 = self.field_registry.resolve_full_reference(ci_m1.instance_name)
        ref_m2 = self.field_registry.resolve_full_reference(ci_m2.instance_name)
        
        # Pane 0: Primary (Automatic mark acts as a container/layout base)
        pane_0 = etree.SubElement(panes_el, "pane")
        pane_0.set("selection-relaxation-option", "selection-relaxation-allow")
        p0_view = etree.SubElement(pane_0, "view")
        etree.SubElement(p0_view, "breakdown", value="auto")
        etree.SubElement(pane_0, "mark", {"class": "Automatic"})
        if not self.show_labels:
            self._add_pane_label_style(pane_0, show=False)
        
        # Pane 1: Primary Axis Mark
        pane_1 = etree.SubElement(panes_el, "pane")
        pane_1.set("id", "1")
        pane_1.set("selection-relaxation-option", "selection-relaxation-allow")
        pane_1.set(axis_attr_name, ref_m1)
        p1_view = etree.SubElement(pane_1, "view")
        etree.SubElement(p1_view, "breakdown", value="auto")
        
        self._setup_pane(
            pane_1, self.mark_type_1, self.mark_type_1, instances,
            self.color_1, self.size_1, self.label_1, self.detail_1, self.wedge_size_1, None,
            False, None, None, ds_name
        )
        
        if self.mark_sizing_off:
            self._insert_mark_sizing(pane_1)
        
        # Override pane 1 style if needed
        if not self.show_labels or self.size_value_1 or self.mark_color_1:
            self._override_pane_style(pane_1, show_labels=self.show_labels, size_value=self.size_value_1, mark_color=self.mark_color_1)
        
        # Pane 2: Secondary Axis Mark
        if measure_1 == measure_2:
            # Same measure on both axes (Lollipop, Donut) — use index
            pane_2 = etree.SubElement(panes_el, "pane")
            pane_2.set("id", "3")
            pane_2.set("selection-relaxation-option", "selection-relaxation-allow")
            pane_2.set(axis_attr_name, ref_m1)
            pane_2.set(axis_attr_index, "1")
        else:
            # Different measures (Combo) — pane 3 with second measure ref
            pane_2 = etree.SubElement(panes_el, "pane")
            pane_2.set("id", "3")
            pane_2.set("selection-relaxation-option", "selection-relaxation-allow")
            pane_2.set(axis_attr_name, ref_m2)
        
        p2_view = etree.SubElement(pane_2, "view")
        etree.SubElement(p2_view, "breakdown", value="auto")
        
        self._setup_pane(
            pane_2, self.mark_type_2, self.mark_type_2, instances,
            self.color_2, self.size_2, self.label_2, self.detail_2, self.wedge_size_2, None,
            False, None, None, ds_name
        )
        
        if self.mark_sizing_off:
            self._insert_mark_sizing(pane_2)
        
        # Override pane 2 style if needed
        if not self.show_labels or self.size_value_2 or self.mark_color_2:
            self._override_pane_style(pane_2, show_labels=self.show_labels, 
                                      size_value=self.size_value_2, mark_color=self.mark_color_2)

        # Helper to build nested measures shelf expression
        def _build_measures_shelf(refs):
            if len(refs) == 1:
                return refs[0]
            return f"({refs[0]} + {_build_measures_shelf(refs[1:])})"

        # Build rows/cols shelf text
        rows_el = table.find("rows")
        if rows_el is not None:
            if self.rows:
                if self.dual_axis_shelf == "rows":
                    rows_el.text = self.editor._build_dimension_shelf(instances, self.rows[:-2])
                    if rows_el.text:
                        rows_el.text += f" ({ref_m1} + {ref_m2})"
                    else:
                        rows_el.text = f"({ref_m1} + {ref_m2})"
                else:
                    rows_el.text = self.editor._build_dimension_shelf(instances, self.rows)
            else:
                rows_el.text = None

        cols_el = table.find("cols")
        if cols_el is not None:
            if self.columns:
                if self.dual_axis_shelf in ("columns", "cols"):
                    # Build extra measure refs
                    extra_refs = []
                    for ea in self.extra_axes:
                        ea_measure = ea.get("measure")
                        if ea_measure:
                            ea_ci = instances.get(ea_measure)
                            if ea_ci:
                                extra_refs.append(self.field_registry.resolve_full_reference(ea_ci.instance_name))
                    if self.extra_axes:
                        all_measure_refs = [ref_m1, ref_m2] + extra_refs
                        cols_el.text = _build_measures_shelf(all_measure_refs)
                    else:
                        cols_el.text = self.editor._build_dimension_shelf(instances, self.columns[:-2])
                        if cols_el.text:
                            cols_el.text += f" ({ref_m1} + {ref_m2})"
                        else:
                            cols_el.text = f"({ref_m1} + {ref_m2})"
                    # Rows become dimension-only when dual_axis_shelf is cols
                    if rows_el is not None:
                        rows_el.text = self.editor._build_dimension_shelf(instances, self.rows)
                else:
                    cols_el.text = self.editor._build_dimension_shelf(instances, self.columns)
            else:
                cols_el.text = None

        # Build extra panes
        if self.extra_axes:
            seen_measures = [measure_1, measure_2]
            pane_id = 4
            for ea in self.extra_axes:
                ea_measure = ea.get("measure", "")
                ea_mark_type = ea.get("mark_type", "Automatic")
                ea_color = ea.get("color")
                ea_size = ea.get("size")
                ea_label = ea.get("label")
                ea_mark_color = ea.get("mark_color")
                ea_mark_sizing_off = ea.get("mark_sizing_off", False)
                ea_size_value = ea.get("size_value")

                ea_ci = instances.get(ea_measure)
                ea_ref = self.field_registry.resolve_full_reference(ea_ci.instance_name) if ea_ci else ""

                # Determine if we need x-index
                # Count occurrences of this measure in seen_measures
                x_index_val = None
                count_prev = seen_measures.count(ea_measure)
                if count_prev >= 1:
                    x_index_val = str(count_prev)  # "1" for second occurrence, "2" for third, etc.

                seen_measures.append(ea_measure)

                pane_ea = etree.SubElement(panes_el, "pane")
                pane_ea.set("id", str(pane_id))
                pane_ea.set("selection-relaxation-option", "selection-relaxation-allow")
                if self.dual_axis_shelf in ("columns", "cols"):
                    pane_ea.set("x-axis-name", ea_ref)
                    if x_index_val is not None:
                        pane_ea.set("x-index", x_index_val)
                else:
                    pane_ea.set("y-axis-name", ea_ref)
                    if x_index_val is not None:
                        pane_ea.set("y-index", x_index_val)

                ea_view = etree.SubElement(pane_ea, "view")
                etree.SubElement(ea_view, "breakdown", value="auto")

                etree.SubElement(pane_ea, "mark", {"class": ea_mark_type})

                if ea_mark_sizing_off:
                    ms_el = etree.SubElement(pane_ea, "mark-sizing")
                    ms_el.set("mark-sizing-setting", "marks-scaling-off")

                # Build encodings
                enc_items = []
                if ea_color:
                    if ea_color == ":Measure Names":
                        enc_items.append(("color", f"[{ds_name}].[:Measure Names]"))
                    else:
                        ea_color_ci = instances.get(ea_color)
                        if ea_color_ci:
                            enc_items.append(("color", self.field_registry.resolve_full_reference(ea_color_ci.instance_name)))
                # Pie charts with measure_values automatically use Multiple Values as size (donut chart)
                if ea_mark_type == "Pie" and ea.get("measure_values"):
                    enc_items.append(("size", f"[{ds_name}].[Multiple Values]"))
                if ea_size:
                    if ea_size == "Multiple Values":
                        enc_items.append(("size", f"[{ds_name}].[Multiple Values]"))
                    else:
                        ea_size_ci = instances.get(ea_size)
                        if ea_size_ci:
                            enc_items.append(("size", self.field_registry.resolve_full_reference(ea_size_ci.instance_name)))
                if ea_label:
                    ea_label_ci = instances.get(ea_label)
                    if ea_label_ci:
                        enc_items.append(("text", self.field_registry.resolve_full_reference(ea_label_ci.instance_name)))

                if enc_items:
                    enc_el = etree.SubElement(pane_ea, "encodings")
                    for enc_tag, enc_col in enc_items:
                        e = etree.SubElement(enc_el, enc_tag)
                        e.set("column", enc_col)

                # Build pane style
                ea_style = etree.SubElement(pane_ea, "style")
                ea_sr = etree.SubElement(ea_style, "style-rule", {"element": "mark"})
                if ea_mark_type == "Pie":
                    etree.SubElement(ea_sr, "format", {"attr": "mark-labels-mode", "value": "range"})
                    etree.SubElement(ea_sr, "format", {"attr": "mark-labels-cull", "value": "false"})
                    etree.SubElement(ea_sr, "format", {"attr": "mark-labels-range-min", "value": "false"})
                    etree.SubElement(ea_sr, "format", {"attr": "mark-labels-range-max", "value": "true"})
                    etree.SubElement(ea_sr, "format", {"attr": "mark-labels-show", "value": "false"})
                else:
                    if ea_mark_color:
                        etree.SubElement(ea_sr, "format", {"attr": "mark-color", "value": ea_mark_color})
                    if ea_size_value:
                        etree.SubElement(ea_sr, "format", {"attr": "size", "value": ea_size_value})
                    etree.SubElement(ea_sr, "format", {"attr": "mark-labels-cull", "value": "false"})
                    etree.SubElement(ea_sr, "format", {"attr": "mark-labels-show", "value": "true" if ea_label else "false"})

                pane_id += 1

        # Build style with dual encoding
        old_style = table.find("style")
        if old_style is not None:
            table.remove(old_style)
        style_el = etree.Element("style")
        scope = "cols" if self.dual_axis_shelf in ("columns", "cols") else "rows"

        rule_el = etree.SubElement(style_el, "style-rule", {"element": "axis"})

        if self.extra_axes and measure_1 != measure_2:
            # Extra axes case: class "0" = ref_m2 (synchronized), class "1" = first extra axis measure
            enc_0 = etree.SubElement(rule_el, "encoding")
            enc_0.set("attr", "space")
            enc_0.set("class", "0")
            enc_0.set("field", ref_m2)
            enc_0.set("field-type", "quantitative")
            enc_0.set("fold", "true")
            enc_0.set("scope", scope)
            enc_0.set("synchronized", "true")
            enc_0.set("type", "space")

            # class "1" = first extra axis measure ref, not synchronized
            first_ea = self.extra_axes[0]
            first_ea_measure = first_ea.get("measure", "")
            first_ea_ci = instances.get(first_ea_measure)
            if first_ea_ci:
                first_ea_ref = self.field_registry.resolve_full_reference(first_ea_ci.instance_name)
                enc_1 = etree.SubElement(rule_el, "encoding")
                enc_1.set("attr", "space")
                enc_1.set("class", "1")
                enc_1.set("field", first_ea_ref)
                enc_1.set("field-type", "quantitative")
                enc_1.set("fold", "true")
                enc_1.set("scope", scope)
                enc_1.set("type", "space")
        else:
            # Normal dual axis encoding
            # Encoding for primary axis (class="1")
            enc_1 = etree.SubElement(rule_el, "encoding")
            enc_1.set("attr", "space")
            enc_1.set("class", "1")
            enc_1.set("field", ref_m1)
            enc_1.set("field-type", "quantitative")
            enc_1.set("fold", "true")
            enc_1.set("scope", scope)
            if self.synchronized:
                enc_1.set("synchronized", "true")
            enc_1.set("type", "space")

            # Encoding for secondary axis (class="0") — needed for proper dual axis
            if measure_1 != measure_2:
                enc_0 = etree.SubElement(rule_el, "encoding")
                enc_0.set("attr", "space")
                enc_0.set("class", "0")
                enc_0.set("field", ref_m1 if self.reverse_axis_1 else ref_m2)
                enc_0.set("field-type", "quantitative")
                if not self.reverse_axis_1:
                    enc_0.set("fold", "true")
                if self.reverse_axis_1:
                    enc_0.set("reverse", "true")
                enc_0.set("scope", scope)
                if self.synchronized and not self.reverse_axis_1:
                    enc_0.set("synchronized", "true")
                enc_0.set("type", "space")

        # Hide axes display if requested
        if self.hide_axes:
            for cls_val in ("0", "1"):
                fmt = etree.SubElement(rule_el, "format")
                fmt.set("attr", "display")
                fmt.set("class", cls_val)
                fmt.set("field", ref_m1 if measure_1 == measure_2 else (ref_m1 if cls_val == "1" else ref_m2))
                fmt.set("scope", scope)
                fmt.set("value", "false")

        # Hide zeroline if requested (Donut/Butterfly)
        if self.hide_zeroline:
            zr = etree.SubElement(style_el, "style-rule", {"element": "zeroline"})
            etree.SubElement(zr, "format", {"attr": "stroke-size", "value": "0"})
            etree.SubElement(zr, "format", {"attr": "line-visibility", "value": "off"})

        insert_before = None
        for tag in ("panes", "rows", "cols"):
            insert_before = table.find(tag)
            if insert_before is not None:
                break
        if insert_before is not None:
            insert_before.addprevious(style_el)
        else:
            table.append(style_el)

        if self.sort_descending:
             self._add_shelf_sort(view, ds_name, instances, self.rows, self.sort_descending)

        # Build Measure Names filter BEFORE other filters so it appears first in view XML
        measure_values_list = []
        for ea in self.extra_axes:
            for mv in ea.get("measure_values", []):
                mv_ci = instances.get(mv)
                if mv_ci:
                    mv_ref = self.field_registry.resolve_full_reference(mv_ci.instance_name)
                    if mv_ref not in measure_values_list:
                        measure_values_list.append(mv_ref)

        if measure_values_list:
            mn_filter = etree.Element("filter")
            mn_filter.set("class", "categorical")
            mn_filter.set("column", f"[{ds_name}].[:Measure Names]")

            gf_union = etree.SubElement(mn_filter, "groupfilter")
            gf_union.set("function", "union")
            gf_union.set(f"{USER_NS}op", "manual")
            for mv_ref in measure_values_list:
                gf_member = etree.SubElement(gf_union, "groupfilter")
                gf_member.set("function", "member")
                gf_member.set("level", "[:Measure Names]")
                gf_member.set("member", f'"{mv_ref}"')

            insert_before = None
            for tag in ("sort", "perspectives", "shelf-sorts", "slices", "aggregation"):
                insert_before = view.find(tag)
                if insert_before is not None:
                    break
            if insert_before is not None:
                insert_before.addprevious(mn_filter)
            else:
                view.append(mn_filter)

            # Add [:Measure Names] to slices
            slices_el = view.find("slices")
            if slices_el is None:
                slices_el = etree.Element("slices")
                agg_el = view.find("aggregation")
                if agg_el is not None:
                    agg_el.addprevious(slices_el)
                else:
                    view.append(slices_el)
            mn_slice = etree.SubElement(slices_el, "column")
            mn_slice.text = f"[{ds_name}].[:Measure Names]"

        if self.filters:
            self._add_filters(view, instances, self.filters)

        # Color map for extra_axes using :Measure Names palette (datasource-level)
        for ea in self.extra_axes:
            ea_color_map = ea.get("color_map")
            if ea_color_map and ea.get("color") == ":Measure Names":
                ds_style = self._datasource.find("style")
                if ds_style is None:
                    ds_style = etree.Element("style")
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
                mn_field = f"[{ds_name}].[:Measure Names]"
                # Remove existing duplicate encoding for :Measure Names
                for existing_enc in mark_rule.findall("encoding"):
                    if existing_enc.get("field") == mn_field and existing_enc.get("attr") == "color":
                        mark_rule.remove(existing_enc)
                color_enc = etree.SubElement(mark_rule, "encoding")
                color_enc.set("attr", "color")
                color_enc.set("field", mn_field)
                color_enc.set("type", "palette")
                for measure_name, hex_color in ea_color_map.items():
                    mv_ci = instances.get(measure_name)
                    if mv_ci:
                        mv_ref = self.field_registry.resolve_full_reference(mv_ci.instance_name)
                        map_el = etree.SubElement(color_enc, "map")
                        map_el.set("to", hex_color)
                        bucket_el = etree.SubElement(map_el, "bucket")
                        bucket_el.text = f'"{mv_ref}"'

        # Color map for primary axis color field (datasource-level palette)
        if self.color_map_1 and self.color_1:
            ci = instances.get(self.color_1)
            if ci:
                full_ref = self.field_registry.resolve_full_reference(ci.instance_name)
                ds_style = self._datasource.find("style")
                if ds_style is None:
                    ds_style = etree.Element("style")
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
                # Avoid duplicate encodings for the same field
                for existing_enc in mark_rule.findall("encoding"):
                    if existing_enc.get("field") == full_ref and existing_enc.get("attr") == "color":
                        mark_rule.remove(existing_enc)
                color_enc = etree.SubElement(mark_rule, "encoding")
                color_enc.set("attr", "color")
                color_enc.set("field", full_ref)
                color_enc.set("type", "palette")
                for bucket_val, hex_color in self.color_map_1.items():
                    map_el = etree.SubElement(color_enc, "map")
                    map_el.set("to", hex_color)
                    bucket_el = etree.SubElement(map_el, "bucket")
                    bucket_el.text = f'"{bucket_val}"'

        return f"Configured worksheet '{self.worksheet_name}' as Dual Axis chart"

    def _insert_mark_sizing(self, pane: etree._Element) -> None:
        """Insert mark-sizing right after mark element (required by Tableau DTD)."""
        mark_el = pane.find("mark")
        ms_el = etree.Element("mark-sizing")
        ms_el.set("mark-sizing-setting", "marks-scaling-off")
        if mark_el is not None:
            mark_el.addnext(ms_el)
        else:
            pane.append(ms_el)

    def _add_pane_label_style(self, pane: etree._Element, show: bool = True) -> None:
        """Add label visibility style to a pane."""
        style = pane.find("style")
        if style is None:
            style = etree.SubElement(pane, "style")
        sr = etree.SubElement(style, "style-rule", {"element": "mark"})
        etree.SubElement(sr, "format", {"attr": "mark-labels-cull", "value": "true"})
        etree.SubElement(sr, "format", {"attr": "mark-labels-show", "value": "true" if show else "false"})

    def _override_pane_style(self, pane: etree._Element, show_labels: bool = True, 
                             size_value: Optional[str] = None, mark_color: Optional[str] = None) -> None:
        """Override existing pane style with label/size/color settings."""
        style = pane.find("style")
        if style is None:
            style = etree.SubElement(pane, "style")
        
        # Find or create mark style-rule
        sr = None
        for existing_sr in style.findall("style-rule"):
            if existing_sr.get("element") == "mark":
                sr = existing_sr
                break
        if sr is None:
            sr = etree.SubElement(style, "style-rule", {"element": "mark"})
        
        # Update label visibility
        label_found = False
        for fmt in sr.findall("format"):
            if fmt.get("attr") == "mark-labels-show":
                fmt.set("value", "true" if show_labels else "false")
                label_found = True
        if not label_found:
            etree.SubElement(sr, "format", {"attr": "mark-labels-show", "value": "true" if show_labels else "false"})
        
        # Set size
        if size_value:
            size_found = False
            for fmt in sr.findall("format"):
                if fmt.get("attr") == "size":
                    fmt.set("value", size_value)
                    size_found = True
            if not size_found:
                etree.SubElement(sr, "format", {"attr": "size", "value": size_value})
        
        # Set mark color
        if mark_color:
            etree.SubElement(sr, "format", {"attr": "mark-color", "value": mark_color})
