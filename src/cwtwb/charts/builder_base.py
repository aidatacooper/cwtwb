"""Base chart builder — shared XML mutation helpers for all chart types.

Every concrete builder (BasicChartBuilder, DualAxisChartBuilder, etc.)
inherits from BaseChartBuilder.  The base class does three things:

1. Stores references to editor internals (root lxml tree, field_registry,
   _datasource element, _parameters dict) so subclasses don't have to.

2. Provides shared XML helpers used by all builders:
   - _gather_expressions()          — collects all field expressions from chart args
   - _parse_and_prepare_instances() — resolves each expression via FieldRegistry
                                      into a ColumnInstance (internal TWB name)
   - _setup_datasource_dependencies() — writes <datasource-dependencies> into the
                                        <view> element (required for each worksheet)
   - _setup_pane()                  — writes <mark>, <encodings>, <style> into a pane
   - _add_filters()                 — writes categorical / quantitative / Top-N filters
   - _build_rich_label()            — writes <customized-label> rich-text runs
   - _add_shelf_sort()              — writes <shelf-sorts> for descending sort by measure

3. Declares the abstract build() contract:
   Subclasses must override build() and return the worksheet_name string.
   build() is the only public entry point called by the dispatcher.

XML structure written by builders (inside editor.root):
  <workbook>
    <worksheets>
      <worksheet name="...">
        <table>
          <view>
            <datasource-dependencies datasource="...">...</datasource-dependencies>
            <filter .../>
            <aggregation value="true"/>
          </view>
          <pane id="1">
            <mark class="Bar"/>
            <encodings>
              <color column="[ds].[instance]"/>
              <text  column="..."/>
            </encodings>
            <style>...</style>
          </pane>
          <rows>(dim / SUM(measure))</rows>
          <cols>YEAR(date)</cols>
        </table>
      </worksheet>
    </worksheets>
  </workbook>
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import replace as dataclass_replace
from typing import Optional, Union

from lxml import etree

from ..field_registry import FieldRegistry, ColumnInstance, _DERIVATION_ABBR, _EXPR_RE
from .helpers import _get_or_create_table_style

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

    @staticmethod
    def _format_filter_value(value) -> str:
        """Format a filter member value for Tableau XML.

        Boolean values (true/false) are written unquoted.  All other values
        are wrapped in double quotes to match Tableau's expected format.
        """
        s = str(value).strip().lower()
        if s in ("true", "false"):
            return s
        return f'"{value}"'

    def _gather_expressions(self, columns, rows, color, size, label, detail, wedge_size, sort_descending, tooltip, filters, geographic_field, measure_values) -> list[str]:
        """Collect all field expressions needed for dependencies and encodings."""
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
                if "by" in f:
                    all_exprs.append(f["by"])
        if geographic_field:
            all_exprs.append(geographic_field)
        if measure_values:
            for mv_expr in measure_values:
                if mv_expr not in all_exprs:
                    all_exprs.append(mv_expr)
        return all_exprs

    def _parse_and_prepare_instances(self, all_exprs: list[str], filters: Optional[list[dict]]) -> dict[str, ColumnInstance]:
        """Parse expressions into ColumnInstances and normalize filter-side types."""
        instances: dict[str, ColumnInstance] = {}
        for expr in all_exprs:
            normalized_expr = self.field_registry.default_view_expression(expr)
            ci = self.field_registry.parse_expression(normalized_expr)
            instances[expr] = ci
            instances[normalized_expr] = ci
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

    def _instance_for_expression(
        self,
        instances: dict[str, ColumnInstance],
        expr: Optional[str],
    ) -> ColumnInstance | None:
        """Resolve a field expression using the normalized chart binding rules."""

        text = str(expr or "").strip()
        if not text:
            return None
        ci = instances.get(text)
        if ci is not None:
            return ci
        normalized = self.field_registry.default_view_expression(text)
        if normalized != text:
            return instances.get(normalized)
        return None

    def _tooltip_instance_for_expression(self, expr: Optional[str]) -> Optional[ColumnInstance]:
        """Resolve a field expression to the ColumnInstance Tableau writes on the
        Tooltip encoding shelf.

        Tooltip encodings always aggregate the field:

        * Dimensions  → ``Attribute`` (``[attr:Field:nk]``)
        * Measures    → ``Sum``       (``[sum:Field:qk]``)

        These differ from ``parse_expression``'s defaults, which keep dimensions
        at ``None`` (``[none:...]``) and promote calculated measures to ``User``
        (``[usr:...]``).  Without this override, a tooltip on a bare dimension
        or calculated measure ends up pointing at an instance Tableau cannot
        resolve, so the tooltip value silently disappears.
        """
        text = str(expr or "").strip()
        if not text:
            return None
        # Honour explicit aggregations (SUM, AVG, ATTR, …) as written.
        if _EXPR_RE.match(text):
            return self.field_registry.parse_expression(text)
        try:
            fi = self.field_registry._find_field(text)
        except KeyError:
            return None
        if fi.role == "dimension":
            target_deriv_xml = "Attribute"     # written into <column-instance derivation="…">
            target_deriv_key = "Attr"          # key into _DERIVATION_ABBR
            ci_type = "nominal"
        else:
            target_deriv_xml = "Sum"
            target_deriv_key = "Sum"
            ci_type = "quantitative"
        abbr = _DERIVATION_ABBR[target_deriv_key]
        type_suffix = {"nominal": "nk", "quantitative": "qk", "ordinal": "ok"}[ci_type]
        return ColumnInstance(
            column_local_name=fi.local_name,
            derivation=target_deriv_xml,
            instance_name=f"[{abbr}:{fi.local_name.strip('[]')}:{type_suffix}]",
            ci_type=ci_type,
        )

    def _add_tooltip_instances(
        self,
        instances: dict[str, ColumnInstance],
        all_exprs: list[str],
        tooltip: Optional[Union[str, list[str]]],
    ) -> None:
        """Augment ``instances``/``all_exprs`` with tooltip-shelf instances.

        ``_setup_datasource_dependencies`` iterates over ``instances.items()``
        to emit ``<column-instance>`` entries, so any tooltip-specific instance
        must be added here *before* that pass runs.  Bare fields get a fresh
        instance (e.g. ``[attr:day:nk]`` for a dimension, ``[sum:Tip Ratio:qk]``
        for a calculated measure).  Explicit aggregations already produce the
        correct instance via ``parse_expression`` and need no augmentation.
        """
        if not tooltip:
            return
        tooltip_list = [tooltip] if isinstance(tooltip, str) else tooltip
        for tt in tooltip_list:
            tt_ci = self._tooltip_instance_for_expression(tt)
            if tt_ci is None:
                continue
            if tt_ci.instance_name in {ci.instance_name for ci in instances.values()}:
                continue
            key = f"__tooltip__:{tt}"
            if key in instances:
                continue
            instances[key] = tt_ci
            if key not in all_exprs:
                all_exprs.append(key)

    def _setup_datasource_dependencies(self, view: etree._Element, ds_name: str, instances: dict[str, ColumnInstance], all_exprs: list[str]) -> None:
        """Rewrite <datasource-dependencies> to include required columns and instances."""
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
        """Ensure calculated fields are present in dependency blocks when needed."""
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
        """Return an existing pane (optionally by id) or create one."""
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

        def _run_attrs(spec: dict) -> tuple:
            _S = object()
            fa = spec.get("fontalignment", _S)
            fa_val = str(fa) if fa is not _S and fa is not None else None
            return (
                "true" if spec.get("bold") else None,
                spec.get("fontcolor"),
                spec.get("fontname"),
                str(spec["fontsize"]) if spec.get("fontsize") is not None else None,
                fa_val,
            )

        def _resolve_run_text(spec: dict) -> str:
            if "param" in spec:
                param_info = self._parameters.get(spec["param"])
                if param_info:
                    internal = param_info["internal_name"]
                    prefix = spec.get("prefix", "")
                    return f"{prefix}<[Parameters].{internal}>"
                return ""
            if "field" in spec:
                ci = self._instance_for_expression(instances, spec["field"])
                if ci:
                    full_ref = self.field_registry.resolve_full_reference(ci.instance_name)
                    prefix = spec.get("prefix", "")
                    return f"{prefix}<{full_ref}>"
                return spec.get("text", "")
            if "text" in spec:
                text = spec["text"]
                return "\u00c6\n" if text == "\n" else text
            return ""

        resolved: list[tuple[dict, str]] = []
        for spec in label_runs:
            text = _resolve_run_text(spec)
            if text:
                resolved.append((spec, text))

        merged: list[tuple[dict, list[str]]] = []
        for spec, text in resolved:
            is_separator = text == "\u00c6\n"
            if merged and not is_separator:
                prev_spec, prev_texts = merged[-1]
                prev_is_sep = len(prev_texts) == 1 and prev_texts[0] == "\u00c6\n"
                if not prev_is_sep and _run_attrs(spec) == _run_attrs(prev_spec):
                    merged[-1] = (prev_spec, prev_texts + [text])
                    continue
            merged.append((spec, [text]))

        for spec, texts in merged:
            r = etree.SubElement(ft, "run")
            _S = object()
            fontalignment = spec.get("fontalignment", _S)
            if fontalignment is not _S and fontalignment is not None:
                r.set("fontalignment", str(fontalignment))
            if spec.get("bold"):
                r.set("bold", "true")
            if spec.get("fontcolor"):
                r.set("fontcolor", spec["fontcolor"])
            if spec.get("fontname"):
                r.set("fontname", spec["fontname"])
            if spec.get("fontsize") is not None:
                r.set("fontsize", str(spec["fontsize"]))
            combined = "".join(texts)
            if "<" in combined:
                r.text = etree.CDATA(combined)
            else:
                r.text = combined
    def _ensure_mark_style(self, pane_style: etree._Element, mark_type: str, original_mark_type: str = None) -> None:
        """Ensure pane style has a mark rule with required default formats."""
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
        """Populate pane mark, encodings, tooltip, style, and map-specific XML."""
        # Validate mark class against the Tableau XSD enumeration before
        # writing it to <mark class="…"/>.  An unknown class would cause
        # Tableau to reject the workbook with a 'value not in enumeration'
        # error.  Aliases are resolved by normalize_chart_pattern in the
        # builder's build() method, so by the time we get here ``mark_type``
        # should already be a primitive class.  The whitelist assertion is a
        # safety net for direct callers of _setup_pane.
        from .dispatcher import TABLEAU_MARK_CLASSES
        if mark_type not in TABLEAU_MARK_CLASSES:
            raise ValueError(
                f"Invalid Tableau mark class {mark_type!r}.  "
                f"Must be one of {sorted(TABLEAU_MARK_CLASSES)}."
            )
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
                color_ci = self._instance_for_expression(instances, color)
                if color_ci is not None:
                    color_el = etree.SubElement(encodings_el, "color")
                    color_el.set("column", self.field_registry.resolve_full_reference(color_ci.instance_name))

            if wedge_size:
                ws_ci = self._instance_for_expression(instances, wedge_size)
                if ws_ci is not None:
                    ws_el = etree.SubElement(encodings_el, "wedge-size")
                    ws_el.set("column", self.field_registry.resolve_full_reference(ws_ci.instance_name))

            if size:
                size_ci = self._instance_for_expression(instances, size)
                if size_ci is not None:
                    size_el = etree.SubElement(encodings_el, "size")
                    size_el.set("column", self.field_registry.resolve_full_reference(size_ci.instance_name))

            if label:
                label_ci = self._instance_for_expression(instances, label)
                if label_ci is not None:
                    label_el = etree.SubElement(encodings_el, "text")
                    label_el.set("column", self.field_registry.resolve_full_reference(label_ci.instance_name))

            if detail:
                detail_ci = self._instance_for_expression(instances, detail)
                if detail_ci is not None:
                    detail_el = etree.SubElement(encodings_el, "lod")
                    detail_el.set("column", self.field_registry.resolve_full_reference(detail_ci.instance_name))

            if is_map and geographic_field and geographic_field != detail:
                geo_ci = self._instance_for_expression(instances, geographic_field)
                if geo_ci is not None:
                    geo_lod = etree.SubElement(encodings_el, "lod")
                    geo_lod.set("column", self.field_registry.resolve_full_reference(geo_ci.instance_name))

            if is_map and map_fields:
                for mf_name in map_fields:
                    try:
                        mf_ci = self._instance_for_expression(instances, mf_name)
                        if mf_ci is None:
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
                    tt_ci = self._tooltip_instance_for_expression(tt)
                    if tt_ci is None:
                        tt_ci = self._instance_for_expression(instances, tt)
                    if tt_ci is not None:
                        tt_el = etree.SubElement(encodings_el, "tooltip")
                        tt_el.set("column", self.field_registry.resolve_full_reference(tt_ci.instance_name))

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
        """Append supported filter XML nodes to the worksheet view."""
        for f in filters:
            expr = f.get("column")
            if not expr:
                continue
            values = f.get("values", [])
            ci = instances.get(expr)
            if not ci:
                continue
            
            filter_el = etree.Element("filter")
            if f.get("context"):
                filter_el.set("context", "true")
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
                        by_ci = self._instance_for_expression(instances, by_measure)
                        if by_ci is None:
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
                gf_level.set(f"{USER_NS}ui-enumeration", "all")
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
                    gf.set("member", self._format_filter_value(values[0]))
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
                        member_el.set("member", self._format_filter_value(v))
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
        """Add a document-format manifest flag if not already present."""
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
        """Attach descending shelf sort metadata for the leading row dimension."""
        dim_ci = None
        for expr in rows:
            ci = instances.get(expr)
            if ci and ci.ci_type == "nominal":
                dim_ci = ci
                break
        if dim_ci is None:
            return

        measure_ci = self._instance_for_expression(instances, sort_measure_expr) or instances.get(sort_measure_expr)
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


# --- BasicChartBuilder ---


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
        """Capture chart configuration for one single-pane worksheet mutation."""
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
        """Create/update worksheet XML for a standard single-pane chart."""
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
        self._add_tooltip_instances(instances, all_exprs, self.tooltip)
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
                """Append a default-formatted run to customized label text."""
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


# --- PieChartBuilder ---


class PieChartBuilder(BaseChartBuilder):
    """Builder for Pie charts."""

    def __init__(self, editor, worksheet_name: str,
                 color: Optional[str] = None,
                 wedge_size: Optional[str] = None,
                 label: Optional[str] = None,
                 detail: Optional[str] = None,
                 tooltip: Optional[Union[str, list[str]]] = None,
                 filters: Optional[list[dict]] = None) -> None:
        """Capture pie-chart specific encodings for one worksheet."""
        super().__init__(editor)
        self.worksheet_name = worksheet_name
        self.mark_type = "Pie"
        self.color = color
        self.wedge_size = wedge_size
        self.label = label
        self.detail = detail
        self.tooltip = tooltip
        self.filters = filters

    def build(self) -> str:
        """Build pie mark XML including wedge-size, label, and filter wiring."""
        ws = self.editor._find_worksheet(self.worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is malformed: missing <table>")
        view = table.find("view")
        if view is None:
            raise ValueError("Malformed structure: missing <view>")

        ds_name = self._datasource.get("name", "")
        
        all_exprs = self._gather_expressions(
            None, None, self.color, None, self.label, self.detail, self.wedge_size,
            None, self.tooltip, self.filters, None, None
        )
        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        self._add_tooltip_instances(instances, all_exprs, self.tooltip)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        pane = self._get_or_create_pane(table)
        self._setup_pane(
            pane, "Pie", "Pie", instances,
            self.color, None, self.label, self.detail, self.wedge_size, self.tooltip,
            False, None, None, ds_name
        )

        rows_el = table.find("rows")
        if rows_el is not None:
            rows_el.text = None
            
        cols_el = table.find("cols")
        if cols_el is not None:
            cols_el.text = None

        if self.color:
            color_ref = self.field_registry.resolve_full_reference(instances[self.color].instance_name)
            windows = self.editor.root.find("windows")
            if windows is not None:
                for window in windows.findall("window"):
                    if window.get("name") == self.worksheet_name:
                        old_vp = window.find("viewpoint")
                        if old_vp is not None:
                            window.remove(old_vp)
                        
                        vp = etree.Element("viewpoint")
                        highlight = etree.SubElement(vp, "highlight")
                        color_viewpoint = etree.SubElement(highlight, "color-one-way")
                        etree.SubElement(color_viewpoint, "field").text = color_ref
                        
                        simple_id = window.find("simple-id")
                        if simple_id is not None:
                            simple_id.addprevious(vp)
                        else:
                            window.append(vp)
                        break

        if self.filters:
            self._add_filters(view, instances, self.filters)
            
        self.editor._setup_table_style(table, "Pie")

        return f"Configured worksheet '{self.worksheet_name}' as Pie chart"


# --- TextChartBuilder ---


class TextChartBuilder(BaseChartBuilder):
    """Builder for Text marks, including measure-values KPI mode."""

    def __init__(
        self,
        editor,
        worksheet_name: str,
        columns: Optional[list[str]] = None,
        rows: Optional[list[str]] = None,
        color: Optional[str] = None,
        size: Optional[str] = None,
        label: Optional[str] = None,
        detail: Optional[str] = None,
        sort_descending: Optional[str] = None,
        tooltip: Optional[Union[str, list[str]]] = None,
        filters: Optional[list[dict]] = None,
        measure_values: Optional[list[str]] = None,
        label_extra: Optional[list[str]] = None,
        label_runs: Optional[list[dict]] = None,
        label_param: Optional[str] = None,
    ) -> None:
        """Capture text-table/KPI options, including measure-values configuration."""
        super().__init__(editor)
        self.worksheet_name = worksheet_name
        self.mark_type = "Text"
        self.columns = columns or []
        self.rows = rows or []
        self.color = color
        self.size = size
        self.label = label
        self.detail = detail
        self.sort_descending = sort_descending
        self.tooltip = tooltip
        self.filters = filters
        self.measure_values = measure_values or []
        self.label_extra = label_extra or []
        self.label_runs = label_runs or []
        self.label_param = label_param

    def build(self) -> str:
        """Build text mark worksheet XML and optional measure-values overlays."""
        ws = self.editor._find_worksheet(self.worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is malformed: missing <table>")
        view = table.find("view")
        if view is None:
            raise ValueError("Malformed structure: missing <view>")

        ds_name = self._datasource.get("name", "")
        # When label_param is set, the label field is not used as a datasource encoding
        label_for_exprs = None if self.label_param else self.label
        all_exprs = self._gather_expressions(
            self.columns,
            self.rows,
            self.color,
            self.size,
            label_for_exprs,
            self.detail,
            None,
            self.sort_descending,
            self.tooltip,
            self.filters,
            None,
            self.measure_values,
        )
        for extra_field in self.label_extra:
            if extra_field not in all_exprs:
                all_exprs.append(extra_field)
        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        self._add_tooltip_instances(instances, all_exprs, self.tooltip)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        pane = self._get_or_create_pane(table)
        pane.set("selection-relaxation-option", "selection-relaxation-disallow")
        self._setup_pane(
            pane,
            "Text",
            "Text",
            instances,
            self.color,
            self.size,
            label_for_exprs,
            self.detail,
            None,
            self.tooltip,
            False,
            None,
            None,
            ds_name,
        )

        # Add label_extra fields as text encodings so Tableau can resolve
        # field references in the customized-label.
        if self.label_extra:
            encodings_el = pane.find("encodings")
            if encodings_el is None:
                encodings_el = etree.SubElement(pane, "encodings")
            for extra_field in self.label_extra:
                ci = self._instance_for_expression(instances, extra_field)
                if ci is not None:
                    text_el = etree.SubElement(encodings_el, "text")
                    text_el.set("column", self.field_registry.resolve_full_reference(ci.instance_name))

        # If label_param is set, add the parameter as the text encoding directly
        if self.label_param:
            param_info = self._parameters.get(self.label_param)
            if param_info:
                internal = param_info["internal_name"]  # e.g. "[Parameter 1]"
                # Add Parameters datasource to view's <datasources>
                datasources_el = view.find("datasources")
                if datasources_el is not None:
                    if not any(d.get("name") == "Parameters" for d in datasources_el.findall("datasource")):
                        # Get caption from the actual Parameters datasource
                        params_ds = self.editor.root.find(".//datasource[@name='Parameters']")
                        caption = params_ds.get("caption", "Parameters") if params_ds is not None else "Parameters"
                        param_ds_el = etree.SubElement(datasources_el, "datasource")
                        param_ds_el.set("caption", caption)
                        param_ds_el.set("name", "Parameters")
                # Add parameter datasource-dependencies to view
                self.editor._add_parameter_deps(view)
                # Add text encoding pointing to the parameter
                encodings_el = pane.find("encodings")
                if encodings_el is None:
                    encodings_el = etree.Element("encodings")
                    cl = pane.find("customized-label")
                    style_el = pane.find("style")
                    insert_before = cl or style_el
                    if insert_before is not None:
                        insert_before.addprevious(encodings_el)
                    else:
                        pane.append(encodings_el)
                text_enc = etree.SubElement(encodings_el, "text")
                text_enc.set("column", f"[Parameters].{internal}")

        # Rich-text label runs
        if self.label_runs:
            self._build_rich_label(pane, instances, self.label_runs)

        if self.measure_values:
            self.editor._apply_measure_values(
                view,
                table,
                pane,
                ds_name,
                instances,
                self.measure_values,
            )
        else:
            # Detect if this is a simple KPI card (no dimensions, only measures).
            # In KPI mode, measures should only appear in text encoding, not on shelves.
            has_dimension = False
            for expr in (self.columns or []) + (self.rows or []):
                ci = instances.get(expr)
                if ci is None:
                    normalized = self.editor.field_registry.default_view_expression(expr)
                    ci = instances.get(normalized)
                if ci and ci.ci_type != "quantitative":
                    has_dimension = True
                    break

            is_kpi_mode = not has_dimension and not self.columns

            if not is_kpi_mode:
                rows_el = table.find("rows")
                if rows_el is not None:
                    rows_el.text = self.editor._build_dimension_shelf(instances, self.rows) if self.rows else None

                cols_el = table.find("cols")
                if cols_el is not None:
                    cols_el.text = self.editor._build_dimension_shelf(instances, self.columns) if self.columns else None

            if self.sort_descending:
                self._add_shelf_sort(view, ds_name, instances, self.rows, self.sort_descending)

            self.editor._setup_table_style(table, "Text")

        if self.filters:
            self._add_filters(view, instances, self.filters)

        return f"Configured worksheet '{self.worksheet_name}' as Text chart"


# --- MapChartBuilder ---


class MapChartBuilder(BaseChartBuilder):
    """Builder for Map charts (Automatic mark over geography).

    Supports single-layer (default Multipolygon) and multi-layer maps via
    ``map_layers``.  When *map_layers* is provided the ``<panes>`` element
    receives ``customization-axis='layer'`` and each list entry becomes an
    independent pane / layer.

    Layer dict keys
    ---------------
    mark_type       : str   – e.g. "Automatic", "Multipolygon"
    color           : str   – field expression for color encoding
    size            : str   – field expression for size encoding
    tooltip         : str | list[str]
    mark_color      : str   – fixed mark colour hex (style format)
    mark_sizing_off : bool  – disable mark size scaling
    has_stroke      : bool  – show stroke on marks
    stroke_color    : str   – stroke colour hex
    mark_size_value : str   – explicit size style value
    """

    def __init__(self, editor, worksheet_name: str,
                 geographic_field: str,
                 color: Optional[str] = None,
                 size: Optional[str] = None,
                 label: Optional[str] = None,
                 detail: Optional[str] = None,
                 tooltip: Optional[Union[str, list[str]]] = None,
                 map_fields: Optional[list[str]] = None,
                 filters: Optional[list[dict]] = None,
                 map_layers: Optional[list[dict]] = None) -> None:
        """Capture map-specific encodings and layer settings."""
        super().__init__(editor)
        self.worksheet_name = worksheet_name
        self.mark_type = "Map"
        self.geographic_field = geographic_field
        self.color = color
        self.size = size
        self.label = label
        self.detail = detail
        self.tooltip = tooltip
        self.map_fields = map_fields
        self.filters = filters
        self.map_layers = map_layers

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def build(self) -> str:
        """Build map worksheet XML, including optional multi-layer panes."""
        ws = self.editor._find_worksheet(self.worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is malformed: missing <table>")
        view = table.find("view")
        if view is None:
            raise ValueError("Malformed structure: missing <view>")

        ds_name = self._datasource.get("name", "")

        # Gather all field expressions across all layers for dependency setup
        all_exprs = self._collect_all_expressions()
        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        # Augment with tooltip-specific aggregations (Attribute for dimensions,
        # Sum for measures) so the encoding references resolve correctly.
        tooltip_for_deps = self._collect_tooltip_expressions()
        self._add_tooltip_instances(instances, all_exprs, tooltip_for_deps)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        if self.map_layers:
            self._build_multi_layer(table, ds_name, instances)
        else:
            self._build_single_layer(table, ds_name, instances)

        # rows / cols: Latitude / Longitude
        rows_el = table.find("rows")
        if rows_el is not None:
            rows_el.text = f"[{ds_name}].[Latitude (generated)]"

        cols_el = table.find("cols")
        if cols_el is not None:
            cols_el.text = f"[{ds_name}].[Longitude (generated)]"

        self.editor._setup_mapsources(view)

        if self.filters:
            self._add_filters(view, instances, self.filters)

        self.editor._setup_table_style(table, "Map")

        return f"Configured worksheet '{self.worksheet_name}' as Map chart"

    # ------------------------------------------------------------------
    # Field expression collection
    # ------------------------------------------------------------------
    def _collect_tooltip_expressions(self) -> list[str]:
        """Flatten top-level and per-layer tooltip expressions for the map."""
        out: list[str] = []
        if self.tooltip:
            if isinstance(self.tooltip, str):
                out.append(self.tooltip)
            else:
                out.extend(self.tooltip)
        if self.map_layers:
            for layer in self.map_layers:
                tt = layer.get("tooltip")
                if not tt:
                    continue
                if isinstance(tt, str):
                    if tt not in out:
                        out.append(tt)
                else:
                    for t in tt:
                        if t not in out:
                            out.append(t)
        return out

    def _collect_all_expressions(self) -> list[str]:
        """Gather every field expression used across all parameters."""
        if not self.map_layers:
            return self._gather_expressions(
                None, None, self.color, self.size, self.label, self.detail, None,
                None, self.tooltip, self.filters, self.geographic_field, None
            )

        exprs: list[str] = []
        if self.geographic_field:
            exprs.append(self.geographic_field)
        if self.map_fields:
            exprs.extend(self.map_fields)

        for layer in self.map_layers:
            for key in ("color", "size", "label", "detail"):
                val = layer.get(key)
                if val and val not in exprs:
                    # Skip numeric literals (e.g. size="0.01") — not field expressions
                    try:
                        float(val)
                    except (ValueError, TypeError):
                        exprs.append(val)
            tt = layer.get("tooltip")
            if tt:
                tt_list = [tt] if isinstance(tt, str) else tt
                for t in tt_list:
                    if t not in exprs:
                        exprs.append(t)

        # Also include top-level fields (they may be shared)
        for val in (self.color, self.size, self.label, self.detail):
            if val and val not in exprs:
                exprs.append(val)
        if self.tooltip:
            tt_list = [self.tooltip] if isinstance(self.tooltip, str) else self.tooltip
            for t in tt_list:
                if t not in exprs:
                    exprs.append(t)
        # filter expressions
        if self.filters:
            for f in self.filters:
                fld = f.get("field") or f.get("column")
                if fld and fld not in exprs:
                    exprs.append(fld)
        return exprs

    # ------------------------------------------------------------------
    # Single-layer (legacy behaviour)
    # ------------------------------------------------------------------
    def _build_single_layer(self, table, ds_name, instances):
        """Render the legacy single-layer map pane path."""
        pane = self._get_or_create_pane(table)
        self._setup_pane(
            pane, "Multipolygon", "Map", instances,
            self.color, self.size, self.label, self.detail, None, self.tooltip,
            True, self.geographic_field, self.map_fields, ds_name
        )

    # ------------------------------------------------------------------
    # Multi-layer map
    # ------------------------------------------------------------------
    def _build_multi_layer(self, table, ds_name, instances):
        """Build multi-layer panes with ``customization-axis='layer'``."""
        # Ensure Tableau knows this workbook uses layers
        self._ensure_manifest_entry("Layers")
        self._ensure_manifest_entry("MapboxVectorStylesAndLayers")

        # Remove the existing empty <panes> and create a new one
        old_panes = table.find("panes")
        if old_panes is not None:
            table.remove(old_panes)

        panes_el = etree.SubElement(table, "panes")
        panes_el.set("customization-axis", "layer")

        for idx, layer_cfg in enumerate(self.map_layers):
            mark_type = layer_cfg.get("mark_type", "Automatic")
            is_multipolygon = mark_type == "Multipolygon"

            pane = etree.SubElement(panes_el, "pane")
            if idx > 0:
                pane.set("generated-title", f"{self.geographic_field} ({idx + 1})" if idx > 1
                         else self.geographic_field)
            pane.set("id", str(idx))
            pane.set("selection-relaxation-option",
                     "selection-relaxation-disallow" if is_multipolygon
                     else "selection-relaxation-allow")

            # <view><breakdown value='auto' /></view>
            pane_view = etree.SubElement(pane, "view")
            etree.SubElement(pane_view, "breakdown").set("value", "auto")

            # <mark class="..."/>
            mark_el = etree.SubElement(pane, "mark")
            mark_el.set("class", mark_type)

            # Optional mark-sizing
            if layer_cfg.get("mark_sizing_off"):
                ms_el = etree.SubElement(pane, "mark-sizing")
                ms_el.set("mark-sizing-setting", "marks-scaling-off")

            # --- Encodings ---
            l_color = layer_cfg.get("color")
            l_size = layer_cfg.get("size")
            l_tooltip = layer_cfg.get("tooltip")

            has_enc = any(x is not None for x in (l_color, l_size, l_tooltip)) \
                or is_multipolygon or self.geographic_field or self.map_fields
            if has_enc:
                enc_el = etree.SubElement(pane, "encodings")

                if l_color and l_color in instances:
                    ce = etree.SubElement(enc_el, "color")
                    ce.set("column", self.field_registry.resolve_full_reference(
                        instances[l_color].instance_name))

                if l_size and l_size in instances:
                    se = etree.SubElement(enc_el, "size")
                    se.set("column", self.field_registry.resolve_full_reference(
                        instances[l_size].instance_name))

                if l_tooltip:
                    tt_list = [l_tooltip] if isinstance(l_tooltip, str) else l_tooltip
                    for tt in tt_list:
                        # Prefer the tooltip-correct instance (Attribute for
                        # dim, Sum for measure).  Fall back to the default
                        # lookup for explicit aggregations like SUM(field).
                        tt_ci = self._tooltip_instance_for_expression(tt)
                        if tt_ci is None and tt in instances:
                            tt_ci = instances[tt]
                        if tt_ci is not None:
                            te = etree.SubElement(enc_el, "tooltip")
                            te.set("column", self.field_registry.resolve_full_reference(
                                tt_ci.instance_name))

                # LOD fields (geographic + map_fields) on every layer
                if self.geographic_field and self.geographic_field in instances:
                    lod = etree.SubElement(enc_el, "lod")
                    lod.set("column", self.field_registry.resolve_full_reference(
                        instances[self.geographic_field].instance_name))

                if self.map_fields:
                    for mf in self.map_fields:
                        try:
                            mf_ci = self.field_registry.parse_expression(mf)
                            lod = etree.SubElement(enc_el, "lod")
                            lod.set("column", self.field_registry.resolve_full_reference(
                                mf_ci.instance_name))
                        except (KeyError, ValueError):
                            pass

                # Geometry encoding only for Multipolygon layers
                if is_multipolygon:
                    geom = etree.SubElement(enc_el, "geometry")
                    geom.set("column", f"[{ds_name}].[Geometry (generated)]")

            # --- Pane style ---
            pane_style = etree.SubElement(pane, "style")
            sr = etree.SubElement(pane_style, "style-rule")
            sr.set("element", "mark")

            mark_color = layer_cfg.get("mark_color")
            mark_size_value = layer_cfg.get("mark_size_value")
            has_stroke = layer_cfg.get("has_stroke", False)
            stroke_color = layer_cfg.get("stroke_color", "#000000")

            if mark_size_value:
                fmt = etree.SubElement(sr, "format")
                fmt.set("attr", "size")
                fmt.set("value", str(mark_size_value))

            fmt_cull = etree.SubElement(sr, "format")
            fmt_cull.set("attr", "mark-labels-cull")
            fmt_cull.set("value", "true")

            if mark_color:
                fmt_mc = etree.SubElement(sr, "format")
                fmt_mc.set("attr", "mark-color")
                fmt_mc.set("value", mark_color)

            if has_stroke:
                fmt_hs = etree.SubElement(sr, "format")
                fmt_hs.set("attr", "has-stroke")
                fmt_hs.set("value", "true")
                fmt_sc = etree.SubElement(sr, "format")
                fmt_sc.set("attr", "stroke-color")
                fmt_sc.set("value", stroke_color)

            fmt_show = etree.SubElement(sr, "format")
            fmt_show.set("attr", "mark-labels-show")
            fmt_show.set("value", "false")

        # Ensure <panes> is placed before <rows>/<cols> in the table
        rows_el = table.find("rows")
        if rows_el is not None:
            rows_el.addprevious(panes_el)
