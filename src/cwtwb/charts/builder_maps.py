"""Map Chart Builder."""

import logging
from typing import Optional, Union
from lxml import etree

from .builder_base import BaseChartBuilder

logger = logging.getLogger(__name__)


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
                        if tt in instances:
                            te = etree.SubElement(enc_el, "tooltip")
                            te.set("column", self.field_registry.resolve_full_reference(
                                instances[tt].instance_name))

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
