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
                 reverse_axis_1: bool = False,
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
        self.reverse_axis_1 = reverse_axis_1

    def build(self) -> str:
        if self.dual_axis_shelf == "rows":
            if len(self.rows) < 2:
                raise ValueError("dual_axis_shelf 'rows' must have at least 2 expressions to fold.")
            measure_1 = self.rows[-2]
            measure_2 = self.rows[-1]
        elif self.dual_axis_shelf == "columns":
            if len(self.columns) < 2:
                raise ValueError("dual_axis_shelf 'columns' must have at least 2 expressions to fold.")
            measure_1 = self.columns[-2]
            measure_2 = self.columns[-1]
        else:
            raise ValueError("dual_axis_shelf must be 'rows' or 'columns'")

        ws = self.editor._find_worksheet(self.worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is malformed: missing <table>")
        view = table.find("view")
        if view is None:
            raise ValueError("Malformed structure: missing <view>")

        ds_name = self._datasource.get("name", "")
        
        # Gather all expressions
        all_exprs = self._gather_expressions(
            self.columns, self.rows, self.color_1, self.size_1, self.label_1, self.detail_1, self.wedge_size_1, self.sort_descending, None, self.filters, None, None
        )
        for enc in (self.color_2, self.size_2, self.label_2, self.detail_2, self.wedge_size_2):
            if enc and enc not in all_exprs:
                all_exprs.append(enc)
                
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
        if not self.show_labels or self.size_value_1:
            self._override_pane_style(pane_1, show_labels=self.show_labels, size_value=self.size_value_1)
        
        # Pane 2: Secondary Axis Mark
        if measure_1 == measure_2:
            # Same measure on both axes (Lollipop, Donut) — use index
            pane_2 = etree.SubElement(panes_el, "pane")
            pane_2.set("id", "2")
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
                if self.dual_axis_shelf == "columns":
                    cols_el.text = self.editor._build_dimension_shelf(instances, self.columns[:-2])
                    if cols_el.text:
                        cols_el.text += f" ({ref_m1} + {ref_m2})"
                    else:
                        cols_el.text = f"({ref_m1} + {ref_m2})"
                else:
                    cols_el.text = self.editor._build_dimension_shelf(instances, self.columns)
            else:
                cols_el.text = None

        # Build style with dual encoding
        old_style = table.find("style")
        if old_style is not None:
            table.remove(old_style)
        style_el = etree.Element("style")
        scope = "cols" if self.dual_axis_shelf == "columns" else "rows"
        
        rule_el = etree.SubElement(style_el, "style-rule", {"element": "axis"})
        
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

        if self.filters:
            self._add_filters(view, instances, self.filters)

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
