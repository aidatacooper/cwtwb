"""Base builder for Chart construction in cwtwb."""

import copy
import logging
import re
from dataclasses import replace as dataclass_replace
from typing import Optional, Union

from lxml import etree

from ..field_registry import FieldRegistry, ColumnInstance

logger = logging.getLogger(__name__)


class BaseChartBuilder:
    """Abstract base chart builder class."""

    def __init__(self, editor) -> None:
        """Initialize the builder using the editor context."""
        self.editor = editor
        # Access editor components for ease of use
        self.root = editor.root
        self.field_registry: FieldRegistry = editor.field_registry
        self._datasource = editor._datasource
        self._parameters = editor._parameters

    def build(self) -> str:
        """Orchestrates the chart creation. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement build().")

    def _gather_expressions(self, columns, rows, color, size, label, detail, wedge_size, sort_descending, tooltip, filters, geographic_field, measure_values) -> list[str]:
        all_exprs: list[str] = []
        all_exprs.extend(columns or [])
        all_exprs.extend(rows or [])
        for enc in (color, size, label, detail, wedge_size, sort_descending):
            if enc:
                all_exprs.append(enc)
        if tooltip:
            if isinstance(tooltip, str):
                all_exprs.append(tooltip)
            else:
                all_exprs.extend(tooltip)
        if filters:
            for f in filters:
                if "column" in f:
                    all_exprs.append(f["column"])
        if geographic_field:
            all_exprs.append(geographic_field)
        if measure_values:
            for mv_expr in measure_values:
                if mv_expr not in all_exprs:
                    all_exprs.append(mv_expr)
        return all_exprs

    def _parse_and_prepare_instances(self, all_exprs: list[str], filters: Optional[list[dict]]) -> dict[str, ColumnInstance]:
        instances: dict[str, ColumnInstance] = {}
        for expr in all_exprs:
            ci = self.field_registry.parse_expression(expr)
            instances[expr] = ci
        if filters:
            for f in filters:
                if f.get("type") == "quantitative" and f["column"] in instances:
                    expr = f["column"]
                    ci = instances[expr]
                    new_inst_name = ci.instance_name
                    if new_inst_name.endswith(":nk]"):
                        new_inst_name = new_inst_name[:-4] + ":qk]"
                    instances[expr] = dataclass_replace(ci, ci_type="quantitative", instance_name=new_inst_name)
        return instances

    def _setup_datasource_dependencies(self, view: etree._Element, ds_name: str, instances: dict[str, ColumnInstance], all_exprs: list[str]) -> None:
        for old_dep in view.findall("datasource-dependencies"):
            view.remove(old_dep)
        deps = etree.Element("datasource-dependencies")
        deps.set("datasource", ds_name)
        agg = view.find("aggregation")
        if agg is not None:
            agg.addprevious(deps)
        else:
            view.append(deps)

        seen_columns: set[str] = set()
        seen_instances: set[str] = set()
        column_elements: list[etree._Element] = []
        instance_elements: list[etree._Element] = []

        for expr, ci in instances.items():
            if ci.column_local_name not in seen_columns:
                seen_columns.add(ci.column_local_name)
                fi = self.field_registry._find_field(expr.split("(")[-1].rstrip(")").strip() if "(" in expr else expr.strip())
                if fi.is_calculated:
                    src_col = self._datasource.find(f"column[@name='{fi.local_name}']")
                    if src_col is not None:
                        col_el = copy.deepcopy(src_col)
                    else:
                        col_el = etree.Element("column")
                        col_el.set("datatype", fi.datatype)
                        col_el.set("name", fi.local_name)
                        col_el.set("role", fi.role)
                        col_el.set("type", fi.field_type)
                else:
                    col_el = etree.Element("column")
                    col_el.set("datatype", fi.datatype)
                    col_el.set("name", fi.local_name)
                    col_el.set("role", fi.role)
                    col_el.set("type", fi.field_type)
                    src_col = self._datasource.find(f"column[@name='{fi.local_name}']")
                    if src_col is not None and src_col.get("semantic-role"):
                        col_el.set("semantic-role", src_col.get("semantic-role"))
                column_elements.append(col_el)
            if ci.instance_name not in seen_instances:
                seen_instances.add(ci.instance_name)
                ci_el = etree.Element("column-instance")
                ci_el.set("column", ci.column_local_name)
                ci_el.set("derivation", ci.derivation)
                ci_el.set("name", ci.instance_name)
                ci_el.set("pivot", ci.pivot)
                ci_el.set("type", ci.ci_type)
                # If source column has a table-calc (e.g. RANK functions), add to instance
                src_calc = self._datasource.find(f"column[@name='{ci.column_local_name}']/calculation")
                if src_calc is not None and src_calc.find("table-calc") is not None:
                    tc_el = etree.SubElement(ci_el, "table-calc")
                    tc_el.set("ordering-type", "Columns")
                instance_elements.append(ci_el)

        for el in sorted(column_elements, key=lambda e: e.get("name", "")):
            deps.append(el)
        for el in sorted(instance_elements, key=lambda e: e.get("name", "")):
            deps.append(el)

        _re = re
        for col_el in list(column_elements):
            calc_el = col_el.find("calculation")
            if calc_el is None:
                continue
            formula = calc_el.get("formula", "")
            for ref_name in _re.findall(r"\[([^\]]+)\]", formula):
                local_ref = f"[{ref_name}]"
                if local_ref in seen_columns:
                    continue
                if ref_name.startswith("Parameter ") or ref_name == "Parameters":
                    continue
                raw_col = self._datasource.find(f"column[@name='{local_ref}']")
                if raw_col is None:
                    for mr in self._datasource.findall(".//metadata-record[@class='column']"):
                        rn = mr.findtext("remote-name", "")
                        if rn == ref_name:
                            ln = mr.findtext("local-name", "")
                            raw_col = self._datasource.find(f"column[@name='{ln}']")
                            if raw_col is not None:
                                local_ref = ln
                            break
                if raw_col is not None and local_ref not in seen_columns:
                    seen_columns.add(local_ref)
                    dep_col = etree.Element("column")
                    dep_col.set("datatype", raw_col.get("datatype", "string"))
                    dep_col.set("name", local_ref)
                    dep_col.set("role", raw_col.get("role", "dimension"))
                    dep_col.set("type", raw_col.get("type", "nominal"))
                    first_ci = deps.find("column-instance")
                    if first_ci is not None:
                        first_ci.addprevious(dep_col)
                    else:
                        deps.append(dep_col)
                        
        self._add_calculated_field_deps(view, ds_name, all_exprs)

    def _add_calculated_field_deps(self, view: etree._Element, ds_name: str, all_exprs: list[str]) -> None:
        deps = view.find(f"datasource-dependencies[@datasource='{ds_name}']")
        if deps is None:
            return
        for fi_name, fi in self.field_registry._fields.items():
            if not fi.is_calculated:
                continue
            existing = deps.find(f"column-instance[@column='{fi.local_name}']")
            if existing is not None:
                existing_col = deps.find(f"column[@name='{fi.local_name}']")
                if existing_col is None:
                    src_col = self._datasource.find(f"column[@name='{fi.local_name}']")
                    if src_col is not None:
                        col_copy = copy.deepcopy(src_col)
                        first_ci = deps.find("column-instance")
                        if first_ci is not None:
                            first_ci.addprevious(col_copy)
                        else:
                            deps.append(col_copy)

    def _get_or_create_pane(self, table: etree._Element, pane_id: Optional[int] = None) -> etree._Element:
        panes_el = table.find("panes")
        if panes_el is not None:
            if pane_id is not None:
                pane = panes_el.find(f"pane[@id='{pane_id}']")
                if pane is not None:
                    return pane
                pane = etree.SubElement(panes_el, "pane")
                pane.set("id", str(pane_id))
                return pane
            else:
                pane = panes_el.find("pane")
                if pane is not None:
                    return pane
                return etree.SubElement(panes_el, "pane")
        
        pane = table.find("pane")
        if pane is not None:
            return pane
        pane = etree.SubElement(table, "pane")
        return pane

    def _build_rich_label(
        self,
        pane: etree._Element,
        instances: dict[str, "ColumnInstance"],
        label_runs: list[dict],
    ) -> None:
        """Build a <customized-label> element from rich-text run specs.

        Each run dict may contain:
          text      – literal text (mutually exclusive with field)
          field     – field expression; resolves to full reference, wrapped in CDATA <ref>
          prefix    – literal prefix prepended before the CDATA field reference (default "")
          fontname  – font family string
          fontsize  – font size (int or str)
          fontcolor – hex color string, e.g. "#5a6dff"
          bold      – bool
          fontalignment – Tableau fontalignment value (default "2")
        """
        if not label_runs:
            return

        old_cl = pane.find("customized-label")
        if old_cl is not None:
            pane.remove(old_cl)

        cl = etree.Element("customized-label")
        pane_style = pane.find("style")
        if pane_style is not None:
            pane_style.addprevious(cl)
        else:
            pane.append(cl)

        ft = etree.SubElement(cl, "formatted-text")

        for run_spec in label_runs:
            r = etree.SubElement(ft, "run")

            # Font attributes
            fontalignment = run_spec.get("fontalignment", "2")
            r.set("fontalignment", str(fontalignment))
            if run_spec.get("bold"):
                r.set("bold", "true")
            if run_spec.get("fontcolor"):
                r.set("fontcolor", run_spec["fontcolor"])
            if run_spec.get("fontname"):
                r.set("fontname", run_spec["fontname"])
            if run_spec.get("fontsize") is not None:
                r.set("fontsize", str(run_spec["fontsize"]))

            # Text content
            if "field" in run_spec:
                field_expr = run_spec["field"]
                ci = instances.get(field_expr)
                if ci:
                    full_ref = self.field_registry.resolve_full_reference(ci.instance_name)
                    prefix = run_spec.get("prefix", "")
                    r.text = etree.CDATA(f"{prefix}<{full_ref}>")
                else:
                    r.text = run_spec.get("text", "")
            elif "text" in run_spec:
                text = run_spec["text"]
                if text == "\n":
                    # Tableau paragraph separator (Æ + newline)
                    r.text = "\u00c6\n"
                else:
                    r.text = text

    def _ensure_mark_style(self, pane_style: etree._Element, mark_type: str, original_mark_type: str = None) -> None:
        for sr in pane_style.findall("style-rule"):
            if sr.get("element") == "mark":
                return

        sr = etree.SubElement(pane_style, "style-rule")
        sr.set("element", "mark")
        style_mark_type = original_mark_type or mark_type

        if style_mark_type == "Pie":
            fmt = etree.SubElement(sr, "format")
            fmt.set("attr", "size")
            fmt.set("value", "1.8")
        elif style_mark_type in ("Tree Map", "Bubble Chart"):
            fmt = etree.SubElement(sr, "format")
            fmt.set("attr", "size")
            fmt.set("value", "2")

        fmt = etree.SubElement(sr, "format")
        fmt.set("attr", "mark-labels-show")
        fmt.set("value", "true")
        fmt = etree.SubElement(sr, "format")
        fmt.set("attr", "mark-labels-cull")
        fmt.set("value", "true")

    def _setup_pane(self, pane: etree._Element, mark_type: str, original_mark_type: str, instances: dict[str, ColumnInstance], color: Optional[str], size: Optional[str], label: Optional[str], detail: Optional[str], wedge_size: Optional[str], tooltip: Optional[Union[str, list[str]]], is_map: bool, geographic_field: Optional[str], map_fields: Optional[list[str]], ds_name: str) -> None:
        mark_el = pane.find("mark")
        if mark_el is not None:
            mark_el.set("class", mark_type)
        else:
            mark_el = etree.SubElement(pane, "mark")
            mark_el.set("class", mark_type)

        old_enc = pane.find("encodings")
        if old_enc is not None:
            pane.remove(old_enc)

        has_encodings = any(x is not None for x in (color, size, label, detail, wedge_size, tooltip, geographic_field if is_map else None))
        if has_encodings:
            encodings_el = etree.SubElement(pane, "encodings")

            if color:
                color_el = etree.SubElement(encodings_el, "color")
                color_el.set("column", self.field_registry.resolve_full_reference(instances[color].instance_name))

            if wedge_size:
                ws_el = etree.SubElement(encodings_el, "wedge-size")
                ws_el.set("column", self.field_registry.resolve_full_reference(instances[wedge_size].instance_name))

            if size:
                size_el = etree.SubElement(encodings_el, "size")
                size_el.set("column", self.field_registry.resolve_full_reference(instances[size].instance_name))

            if label:
                label_el = etree.SubElement(encodings_el, "text")
                label_el.set("column", self.field_registry.resolve_full_reference(instances[label].instance_name))

            if detail:
                detail_el = etree.SubElement(encodings_el, "lod")
                detail_el.set("column", self.field_registry.resolve_full_reference(instances[detail].instance_name))

            if is_map and geographic_field and geographic_field != detail:
                geo_lod = etree.SubElement(encodings_el, "lod")
                geo_lod.set("column", self.field_registry.resolve_full_reference(instances[geographic_field].instance_name))

            if is_map and map_fields:
                for mf_name in map_fields:
                    try:
                        mf_ci = self.field_registry.parse_expression(mf_name)
                        mf_lod = etree.SubElement(encodings_el, "lod")
                        mf_lod.set("column", self.field_registry.resolve_full_reference(mf_ci.instance_name))
                    except (KeyError, ValueError) as e:
                        logger.warning("Map field '%s' not found, skipping: %s", mf_name, e)

            if is_map:
                geom = etree.SubElement(encodings_el, "geometry")
                geom.set("column", f"[{ds_name}].[Geometry (generated)]")

            if tooltip:
                tooltip_list = [tooltip] if isinstance(tooltip, str) else tooltip
                for tt in tooltip_list:
                    tt_el = etree.SubElement(encodings_el, "tooltip")
                    tt_el.set("column", self.field_registry.resolve_full_reference(instances[tt].instance_name))

        pane_style = pane.find("style")
        if pane_style is None:
            pane_style = etree.SubElement(pane, "style")
        self._ensure_mark_style(pane_style, mark_type, original_mark_type)

    def _add_filters(
        self,
        view: etree._Element,
        instances: dict[str, "ColumnInstance"],
        filters: list[dict],
    ) -> None:
        for f in filters:
            expr = f.get("column")
            if not expr:
                continue
            values = f.get("values", [])
            ci = instances.get(expr)
            if not ci:
                continue
            
            filter_el = etree.Element("filter")
            filter_type = f.get("type")
            if not filter_type:
                if ci.ci_type == "quantitative" or ci.instance_name.endswith(":qk]"):
                    filter_type = "quantitative"
                else:
                    filter_type = "categorical"
            
            USER_NS = "{http://www.tableausoftware.com/xml/user}"
            
            if filter_type == "quantitative":
                filter_el.set("class", "quantitative")
                filter_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))
                filter_el.set("included-values", "in-range")
                
                if "min" in f:
                    min_el = etree.SubElement(filter_el, "min")
                    min_el.text = f["min"]
                if "max" in f:
                    max_el = etree.SubElement(filter_el, "max")
                    max_el.text = f["max"]
            elif "top" in f:
                # Top N filter
                filter_el.set("class", "categorical")
                filter_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))
                
                gf_top = etree.SubElement(filter_el, "groupfilter")
                gf_top.set("count", str(f["top"]))
                gf_top.set("end", "top")
                gf_top.set("function", "end")
                gf_top.set("units", "records")
                gf_top.set(f"{USER_NS}ui-marker", "end")
                gf_top.set(f"{USER_NS}ui-top-by-field", "true")
                
                gf_order = etree.SubElement(gf_top, "groupfilter")
                gf_order.set("direction", f.get("direction", "DESC"))
                
                # Resolve the 'by' measure — Tableau requires formula syntax SUM([col]) not instance ref
                by_measure = f.get("by")
                if by_measure:
                    try:
                        by_ci = self.field_registry.parse_expression(by_measure)
                        by_expr = f"{by_ci.derivation.upper()}({by_ci.column_local_name})"
                        gf_order.set("expression", by_expr)
                    except (KeyError, ValueError):
                        gf_order.set("expression", by_measure)

                gf_order.set("function", "order")
                gf_order.set(f"{USER_NS}ui-marker", "order")

                gf_level = etree.SubElement(gf_order, "groupfilter")
                gf_level.set("function", "level-members")
                gf_level.set("level", ci.instance_name)
                gf_level.set(f"{USER_NS}ui-manual-selection", "true")
                gf_level.set(f"{USER_NS}ui-manual-selection-all-when-empty", "true")
                gf_level.set(f"{USER_NS}ui-manual-selection-is-empty", "true")
                gf_level.set(f"{USER_NS}ui-marker", "enumerate")

                # Add dimension to <slices> — required for Tableau to apply Top N correctly
                slices_el = view.find("slices")
                if slices_el is None:
                    slices_el = etree.Element("slices")
                    agg_el = view.find("aggregation")
                    if agg_el is not None:
                        agg_el.addprevious(slices_el)
                    else:
                        view.append(slices_el)
                slice_col = etree.SubElement(slices_el, "column")
                slice_col.text = self.field_registry.resolve_full_reference(ci.instance_name)
            else:
                filter_el.set("class", "categorical")
                filter_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))
                if len(values) == 1:
                    gf = etree.SubElement(filter_el, "groupfilter")
                    gf.set("function", "member")
                    gf.set("level", ci.instance_name)
                    gf.set("member", f'"{values[0]}"')
                    gf.set(f"{USER_NS}ui-domain", "database")
                    gf.set(f"{USER_NS}ui-enumeration", "inclusive")
                    gf.set(f"{USER_NS}ui-marker", "enumerate")
                elif len(values) > 1:
                    gf = etree.SubElement(filter_el, "groupfilter")
                    gf.set("function", "union")
                    gf.set(f"{USER_NS}ui-domain", "database")
                    gf.set(f"{USER_NS}ui-enumeration", "inclusive")
                    gf.set(f"{USER_NS}ui-marker", "enumerate")
                    for v in values:
                        member_el = etree.SubElement(gf, "groupfilter")
                        member_el.set("function", "member")
                        member_el.set("level", ci.instance_name)
                        member_el.set("member", f'"{v}"')
                else:
                    gf = etree.SubElement(filter_el, "groupfilter")
                    gf.set("function", "level-members")
                    gf.set("level", ci.instance_name)
                    gf.set(f"{USER_NS}ui-domain", "database")
                    gf.set(f"{USER_NS}ui-enumeration", "inclusive")
                    gf.set(f"{USER_NS}ui-marker", "enumerate")
            
            insert_before = None
            for tag in ("sort", "perspectives", "shelf-sorts", "slices", "aggregation"):
                insert_before = view.find(tag)
                if insert_before is not None:
                    break
            if insert_before is not None:
                insert_before.addprevious(filter_el)
            else:
                view.append(filter_el)

    def _ensure_manifest_entry(self, entry_name: str) -> None:
        manifest = self.root.find("document-format-change-manifest")
        if manifest is None:
            manifest = etree.SubElement(self.root, "document-format-change-manifest")
        if manifest.find(entry_name) is None:
            etree.SubElement(manifest, entry_name)

    def _add_shelf_sort(
        self,
        view: etree._Element,
        ds_name: str,
        instances: dict[str, "ColumnInstance"],
        rows: list[str],
        sort_measure_expr: str,
    ) -> None:
        dim_ci = None
        for expr in rows:
            ci = instances.get(expr)
            if ci and ci.ci_type == "nominal":
                dim_ci = ci
                break
        if dim_ci is None:
            return

        measure_ci = instances.get(sort_measure_expr)
        if measure_ci is None:
            return

        self._ensure_manifest_entry("IntuitiveSorting")
        self._ensure_manifest_entry("IntuitiveSorting_SP2")

        for old_ss in view.findall("shelf-sorts"):
            view.remove(old_ss)

        shelf_sorts = etree.Element("shelf-sorts")

        sort_v2 = etree.SubElement(shelf_sorts, "shelf-sort-v2")
        sort_v2.set("dimension-to-sort",
                     self.field_registry.resolve_full_reference(dim_ci.instance_name))
        sort_v2.set("direction", "DESC")
        sort_v2.set("is-on-innermost-dimension", "true")
        sort_v2.set("measure-to-sort-by",
                     self.field_registry.resolve_full_reference(measure_ci.instance_name))
        sort_v2.set("shelf", "rows")

        agg = view.find("aggregation")
        if agg is not None:
            agg.addprevious(shelf_sorts)
        else:
            view.append(shelf_sorts)
