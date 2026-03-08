"""Chart Factory and Router for TWBEditor.

This module acts as a facade, routing chart configuration requests
to the appropriate builder subclass based on the mark_type or chart characteristics.
"""

from typing import Optional, Union

from .builder_basic import BasicChartBuilder
from .builder_pie import PieChartBuilder
from .builder_maps import MapChartBuilder
from .builder_dual_axis import DualAxisChartBuilder

class ChartsMixin:
    """Mixin providing chart configuration methods for TWBEditor (Facade)."""
    
    def configure_chart(
        self,
        worksheet_name: str,
        mark_type: str = "Automatic",
        columns: Optional[list[str]] = None,
        rows: Optional[list[str]] = None,
        color: Optional[str] = None,
        size: Optional[str] = None,
        label: Optional[str] = None,
        detail: Optional[str] = None,
        wedge_size: Optional[str] = None,
        sort_descending: Optional[str] = None,
        tooltip: Optional[Union[str, list[str]]] = None,
        filters: Optional[list[dict]] = None,
        geographic_field: Optional[str] = None,
        measure_values: Optional[list[str]] = None,
        map_fields: Optional[list[str]] = None,
    ) -> str:
        """Route chart configuration to the correct builder."""
        
        real_mark = mark_type
        # Pre-process simple aliases to direct to correct builder if needed
        if mark_type in ("Scatterplot", "Bubble Chart"):
            real_mark = "Circle"
        elif mark_type in ("Heatmap", "Tree Map"):
            real_mark = "Square"
            
        if real_mark == "Pie" or mark_type == "Pie":
            builder = PieChartBuilder(
                self, worksheet_name, color, wedge_size, label, detail, tooltip, filters
            )
            return builder.build()
            
        elif real_mark == "Map" or mark_type == "Map":
            builder = MapChartBuilder(
                self, worksheet_name, geographic_field, color, size, label, detail, tooltip, map_fields, filters
            )
            return builder.build()
            
        else:
            builder = BasicChartBuilder(
                self, worksheet_name, mark_type, columns, rows, color, size, label, detail, sort_descending, tooltip, filters
            )
            return builder.build()

    def configure_dual_axis(
        self,
        worksheet_name: str,
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
    ) -> str:
        """Route dual axis configuration to the specific builder."""
        builder = DualAxisChartBuilder(
            self, worksheet_name, mark_type_1, mark_type_2, columns, rows, dual_axis_shelf,
            color_1, size_1, label_1, detail_1,
            color_2, size_2, label_2, detail_2,
            synchronized, sort_descending, filters
        )
        return builder.build()

    # NOTE: Keep the generic macro appliers available for Builders
    def _apply_chart_macros(self, mark_type: str, columns: list[str], rows: list[str], color: Optional[str]) -> tuple[str, list[str], list[str]]:
        new_mark_type = mark_type
        
        if mark_type == "Scatterplot":
            new_mark_type = "Circle"
        elif mark_type == "Heatmap":
            new_mark_type = "Square"
            if not color and len(columns) > 0 and len(rows) > 0:
                pass 
        elif mark_type == "Tree Map":
            new_mark_type = "Square"
            columns = []
            rows = []
        elif mark_type == "Bubble Chart":
            new_mark_type = "Circle"
            columns = []
            rows = []
            
        return new_mark_type, columns, rows

    def _build_dimension_shelf(self, instances: dict, exprs: list[str]) -> str:
        parts = []
        ci_list = []
        for e in exprs:
            ci = instances.get(e)
            if ci:
                parts.append(self.field_registry.resolve_full_reference(ci.instance_name))
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

    def _setup_table_style(self, table, mark_type):
        import lxml.etree as etree
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
        if mark_type in ("Tree Map", "Bubble Chart"):
            # Hide axes
            axis_rule = etree.SubElement(table_style, "style-rule")
            axis_rule.set("element", "axis")
            fmt = etree.SubElement(axis_rule, "format")
            fmt.set("attr", "line-visibility")
            fmt.set("value", "off")
            # Hide grid lines and zero lines
            for el_name in ("gridline", "zeroline"):
                rule = etree.SubElement(table_style, "style-rule")
                rule.set("element", el_name)
                fmt = etree.SubElement(rule, "format")
                fmt.set("attr", "line-visibility")
                fmt.set("value", "off")
            # Hide headers
            ws_rule = etree.SubElement(table_style, "style-rule")
            ws_rule.set("element", "worksheet")
            for scope in ("cols", "rows"):
                fmt = etree.SubElement(ws_rule, "format")
                fmt.set("attr", "display-field-labels")
                fmt.set("scope", scope)
                fmt.set("value", "false")

    def _setup_mapsources(self, view):
        import lxml.etree as etree
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
            
        if self._parameters and view_ds is not None:
            params_ds_ref = view_ds.find("datasource[@name='Parameters']")
            if params_ds_ref is None:
                pds = etree.SubElement(view_ds, "datasource")
                pds.set("caption", "参数")
                pds.set("name", "Parameters")
            # For Map, if parameter is used
            
        root_ms = self.root.find("mapsources")
        if root_ms is None:
            root_ms = etree.Element("mapsources")
            ds_el = self.root.find("datasources")
            if ds_el is not None:
                ds_el.addnext(root_ms)
            else:
                self.root.append(root_ms)
            rms = etree.SubElement(root_ms, "mapsource")
            rms.set("name", "Tableau")

    def _apply_measure_values(
        self,
        view,
        table,
        pane,
        ds_name: str,
        instances: dict,
        measure_values: list[str],
    ) -> None:
        import lxml.etree as etree
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
        
        USER_NS = "{http://www.tableausoftware.com/xml/user}"
        measure_refs = []
        for mv_expr in measure_values:
            if mv_expr in instances:
                ci = instances[mv_expr]
                full_ref = self.field_registry.resolve_full_reference(ci.instance_name)
                measure_refs.append(full_ref)
        
        if measure_refs:
            filter_el = etree.Element("filter")
            filter_el.set("class", "categorical")
            filter_el.set("column", f"[{ds_name}].[:Measure Names]")
            
            gf = etree.SubElement(filter_el, "groupfilter")
            gf.set("function", "union")
            gf.set(f"{USER_NS}ui-domain", "database")
            gf.set(f"{USER_NS}ui-enumeration", "inclusive")
            gf.set(f"{USER_NS}ui-marker", "enumerate")
            
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
        for attr, val in [("text-align", "center"), ("font-weight", "bold"), ("font-size", "12")]:
            fmt = etree.SubElement(cell_rule, "format")
            fmt.set("attr", attr)
            fmt.set("value", val)
        
        label_rule = etree.SubElement(table_style, "style-rule")
        label_rule.set("element", "label")
        for attr, val in [("text-align", "center"), ("font-size", "10")]:
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
