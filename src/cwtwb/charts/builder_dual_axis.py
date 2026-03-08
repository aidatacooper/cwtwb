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
                 filters: Optional[list[dict]] = None) -> None:
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
        
        all_exprs = self._gather_expressions(
            self.columns, self.rows, self.color_1, self.size_1, self.label_1, self.detail_1, None, self.sort_descending, None, self.filters, None, None
        )
        for enc in (self.color_2, self.size_2, self.label_2, self.detail_2):
            if enc and enc not in all_exprs:
                all_exprs.append(enc)
                
        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

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
        
        # Pane 0: Primary (Automatic mark acts as a container or layout base)
        pane_0 = etree.SubElement(panes_el, "pane")
        pane_0.set("selection-relaxation-option", "selection-relaxation-allow")
        p0_view = etree.SubElement(pane_0, "view")
        etree.SubElement(p0_view, "breakdown", value="auto")
        etree.SubElement(pane_0, "mark", {"class": "Automatic"})
        
        # Pane 1: Primary Axis Mark
        pane_1 = etree.SubElement(panes_el, "pane")
        pane_1.set("id", "1")
        pane_1.set("selection-relaxation-option", "selection-relaxation-allow")
        axis_attr_name = "y-axis-name" if self.dual_axis_shelf == "rows" else "x-axis-name"
        axis_attr_index = "y-index" if self.dual_axis_shelf == "rows" else "x-index"
        
        ci_m1 = instances[measure_1]
        ci_m2 = instances[measure_2]
        ref_m1 = self.field_registry.resolve_full_reference(ci_m1.instance_name)
        ref_m2 = self.field_registry.resolve_full_reference(ci_m2.instance_name)
        
        pane_1.set(axis_attr_name, ref_m1)
        p1_view = etree.SubElement(pane_1, "view")
        etree.SubElement(p1_view, "breakdown", value="auto")
        
        self._setup_pane(
            pane_1, self.mark_type_1, self.mark_type_1, instances,
            self.color_1, self.size_1, self.label_1, self.detail_1, None, None,
            False, None, None, ds_name
        )
        
        # Pane 2: Secondary Axis Mark
        pane_2 = etree.SubElement(panes_el, "pane")
        pane_2.set("id", "2")
        pane_2.set("selection-relaxation-option", "selection-relaxation-allow")
        pane_2.set(axis_attr_name, ref_m1)
        pane_2.set(axis_attr_index, "1")
        p2_view = etree.SubElement(pane_2, "view")
        etree.SubElement(p2_view, "breakdown", value="auto")
        
        self._setup_pane(
            pane_2, self.mark_type_2, self.mark_type_2, instances,
            self.color_2, self.size_2, self.label_2, self.detail_2, None, None,
            False, None, None, ds_name
        )

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

        old_style = table.find("style")
        if old_style is not None:
            table.remove(old_style)
        style_el = etree.Element("style")
        
        rule_el = etree.SubElement(style_el, "style-rule", {"element": "axis"})
        enc_el = etree.SubElement(rule_el, "encoding")
        enc_el.set("attr", "space")
        enc_el.set("class", "1")
        enc_el.set("field", ref_m1)
        enc_el.set("field-type", "quantitative")
        enc_el.set("fold", "true")
        enc_el.set("scope", "cols" if self.dual_axis_shelf == "columns" else "rows")
        if self.synchronized:
            enc_el.set("synchronized", "true")
        enc_el.set("type", "space")
        
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
