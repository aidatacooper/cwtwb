"""Public chart facade for TWBEditor — stable API surface for all chart operations.

ChartsMixin is mixed into TWBEditor and exposes two public methods:
  - configure_chart()      → standard single-pane charts
  - configure_dual_axis()  → dual-pane overlaid charts

Internal architecture (hidden from callers):
  ChartsMixin.configure_chart()
    └─ dispatcher.configure_chart()
         └─ routing_policy.profile_chart_request()  → ChartRouteProfile
              └─ Selects one of:
                   BasicChartBuilder   (Bar, Line, Area, Circle, GanttBar, …)
                   TextChartBuilder    (Text / cross-tab / measure-values)
                   PieChartBuilder     (Pie with color/wedge-size encodings)
                   MapChartBuilder     (filled / symbol maps)
                      └─ builder.build() → mutates editor.root, returns worksheet_name

  ChartsMixin.configure_dual_axis()
    └─ dispatcher.configure_dual_axis()
         └─ DualAxisChartBuilder.build()

  ChartsMixin.configure_worksheet_style()  — called separately after configure_chart
    └─ helpers.apply_worksheet_style()

The public mixin stays stable; routing, pattern mapping, and builder helpers
live in focused internal modules and can change without breaking callers.
"""
__author__ = "Cooper Wenhua <imgwho@gmail.com>"

from typing import Optional, Union

from .dispatcher import configure_chart as dispatch_configure_chart
from .dispatcher import configure_dual_axis as dispatch_configure_dual_axis
from .dispatcher import configure_layered_chart as dispatch_configure_layered_chart
from .helpers import (
    apply_chart_macros,
    apply_measure_values,
    apply_worksheet_style,
    build_dimension_shelf,
    setup_mapsources,
    setup_table_style,
)


class ChartsMixin:
    """Mixin providing the stable chart configuration facade for TWBEditor."""

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
        mark_sizing_off: bool = False,
        axis_fixed_range: Optional[dict] = None,
        customized_label: Optional[str] = None,
        color_map: Optional[dict[str, str]] = None,
        text_format: Optional[dict[str, str]] = None,
        map_layers: Optional[list[dict]] = None,
        map_partition: Optional[str] = None,
        label_extra: Optional[list[str]] = None,
        label_runs: Optional[list[dict]] = None,
        label_param: Optional[str] = None,
        table_calc_overrides: Optional[dict[str, list[dict]]] = None,
        sort_field: Optional[str] = None,
        separate_measure_domains: bool = False,
        map_layer_mode: str = "overlay",
    ) -> str:
        """Route chart configuration to the correct builder."""

        return dispatch_configure_chart(
            self,
            worksheet_name=worksheet_name,
            mark_type=mark_type,
            columns=columns,
            rows=rows,
            color=color,
            size=size,
            label=label,
            detail=detail,
            wedge_size=wedge_size,
            sort_descending=sort_descending,
            sort_field=sort_field,
            tooltip=tooltip,
            filters=filters,
            geographic_field=geographic_field,
            measure_values=measure_values,
            separate_measure_domains=separate_measure_domains,
            map_fields=map_fields,
            mark_sizing_off=mark_sizing_off,
            axis_fixed_range=axis_fixed_range,
            customized_label=customized_label,
            color_map=color_map,
            text_format=text_format,
            map_layers=map_layers,
            map_partition=map_partition,
            map_layer_mode=map_layer_mode,
            label_extra=label_extra,
            label_runs=label_runs,
            label_param=label_param,
            table_calc_overrides=table_calc_overrides,
        )

    def configure_custom_label(
        self, worksheet_name: str, runs: list[dict], *, pane_index: int = 0
    ) -> str:
        """Set formatted literal/field mark-label runs on a configured pane.

        ``pane_index`` is zero based and includes native default panes. Field
        runs retain existing worksheet table-calculation instances and contexts.
        Rich attributes use native names: fontsize, fontname, fontcolor,
        fontalignment, bold, italic and underline.
        """
        from .custom_labels import configure_custom_label

        return configure_custom_label(self, worksheet_name, runs, pane_index=pane_index)

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
        fold_axis: bool = False,
        color_by_measure_names: bool = False,
        table_calc_overrides: Optional[dict[str, list[dict]]] = None,
        sort_field: Optional[str] = None,
    ) -> str:
        """Route dual axis configuration to the specific builder."""

        return dispatch_configure_dual_axis(
            self,
            worksheet_name=worksheet_name,
            mark_type_1=mark_type_1,
            mark_type_2=mark_type_2,
            columns=columns,
            rows=rows,
            dual_axis_shelf=dual_axis_shelf,
            color_1=color_1,
            size_1=size_1,
            label_1=label_1,
            detail_1=detail_1,
            color_2=color_2,
            size_2=size_2,
            label_2=label_2,
            detail_2=detail_2,
            synchronized=synchronized,
            sort_descending=sort_descending,
            sort_field=sort_field,
            filters=filters,
            wedge_size_1=wedge_size_1,
            wedge_size_2=wedge_size_2,
            show_labels=show_labels,
            hide_axes=hide_axes,
            hide_zeroline=hide_zeroline,
            mark_sizing_off=mark_sizing_off,
            size_value_1=size_value_1,
            size_value_2=size_value_2,
            mark_color_2=mark_color_2,
            mark_color_1=mark_color_1,
            reverse_axis_1=reverse_axis_1,
            extra_axes=extra_axes,
            color_map_1=color_map_1,
            fold_axis=fold_axis,
            color_by_measure_names=color_by_measure_names,
            table_calc_overrides=table_calc_overrides,
        )

    def configure_layered_chart(
        self,
        worksheet_name: str,
        *,
        columns: Optional[list[str]] = None,
        rows: Optional[list[str]] = None,
        panes: Optional[list[dict]] = None,
        axis_shelf: str = "rows",
        synchronized: bool = True,
        fold_axes: bool = True,
        hide_axes: bool = False,
        sort_descending: Optional[str] = None,
        table_calc_overrides: Optional[dict[str, list[dict]]] = None,
        table_calc_context: bool = False,
        sort_field: Optional[str] = None,
        sort_mode: str = "auto",
        filters: Optional[list[dict]] = None,
    ) -> str:
        """Configure panes with encodings, sorting, and native trendline/style dictionaries."""

        return dispatch_configure_layered_chart(
            self,
            worksheet_name,
            columns=columns,
            rows=rows,
            panes=panes,
            axis_shelf=axis_shelf,
            synchronized=synchronized,
            fold_axes=fold_axes,
            hide_axes=hide_axes,
            sort_descending=sort_descending,
            sort_field=sort_field,
            sort_mode=sort_mode,
            filters=filters,
            table_calc_overrides=table_calc_overrides,
            table_calc_context=table_calc_context,
        )

    def _set_parameter_axis_title(self, worksheet, reference, parameter, scope, duplicate_index):
        """Bind an axis title to a parameter using Tableau's expression graph."""
        from lxml import etree
        from uuid import uuid4
        guid = lambda: str(uuid4())
        manifest = self.root.find("document-format-change-manifest")
        if manifest is None:
            manifest = etree.Element("document-format-change-manifest")
            self.root.insert(0, manifest)
        for feature in ("DatagraphCoreV1", "DatagraphNodeAxisTitle", "DatagraphNodeSingleValueFieldV1"):
            if manifest.find(feature) is None:
                etree.SubElement(manifest, feature)
        datagraph = self.root.find("datagraph")
        if datagraph is None:
            datagraph = etree.SubElement(self.root, "datagraph")
        graph = datagraph.find("graph")
        if graph is None:
            graph = etree.SubElement(datagraph, "graph")
            properties = etree.SubElement(graph, "properties")
            etree.SubElement(properties, "default-execution-subgraph-guid", value=guid())
            for tag in ("node-execution-subgraphs", "nodes", "edges", "pin-values"):
                etree.SubElement(graph, tag)
        nodes, edges = graph.find("nodes"), graph.find("edges")
        sheet_id = worksheet.find("simple-id").get("uuid")
        orientation = "horizontal" if scope == "cols" else "vertical"
        axis = next((node for node in nodes.findall("axis-title-node") if node.get("sheet-identifier") == sheet_id and node.get("fieldname") == reference and node.get("orientation") == orientation and node.get("duplicate-index") == str(duplicate_index)), None)
        if axis is None:
            axis = etree.SubElement(nodes, "axis-title-node", {"duplicate-index": str(duplicate_index), "fieldname": reference, "node-guid": guid(), "orientation": orientation, "sheet-identifier": sheet_id, "title-input-guid": guid()})
        previous = next((edge for edge in edges.findall("edge") if edge.get("to") == axis.get("title-input-guid")), None)
        source = next((node for node in nodes.findall("single-value-field-node") if previous is not None and node.get("value-output-guid") == previous.get("from")), None)
        if source is None:
            source = etree.SubElement(nodes, "single-value-field-node", {"fieldname-input-guid": guid(), "node-guid": guid(), "value-output-guid": guid()})
        source.set("fieldname", f"[Parameters].{self._parameters[parameter]['internal_name']}")
        if previous is None:
            etree.SubElement(edges, "edge", {"from": source.get("value-output-guid"), "to": axis.get("title-input-guid")})
        subgraph = graph.find("properties/default-execution-subgraph-guid").get("value")
        pairs = graph.find("node-execution-subgraphs")
        for node in (axis, source):
            if not any(pair.get("node-guid") == node.get("node-guid") for pair in pairs.findall("pair")):
                etree.SubElement(pairs, "pair", {"execution-subgraph-guid": subgraph, "node-guid": node.get("node-guid")})

    def configure_worksheet_style(
        self,
        worksheet_name: str,
        background_color: Optional[str] = None,
        hide_axes: bool = False,
        hide_gridlines: bool = False,
        hide_zeroline: bool = False,
        hide_borders: bool = False,
        hide_band_color: bool = False,
        hide_row_label: Optional[str] = None,
        hide_col_field_labels: bool = False,
        hide_row_field_labels: bool = False,
        hide_droplines: bool = False,
        hide_reflines: bool = False,
        hide_table_dividers: bool = False,
        table_dividers: Optional[list] = None,
        disable_tooltip: bool = False,
        show_column_totals: bool = False,
        show_row_totals: bool = False,
        pane_cell_style: Optional[dict] = None,
        pane_datalabel_style: Optional[dict] = None,
        pane_mark_style: Optional[dict] = None,
        pane_trendline_hidden: bool = False,
        panes_style: Optional[dict | list] = None,
        label_formats: Optional[list] = None,
        cell_formats: Optional[list] = None,
        header_formats: Optional[list] = None,
        table_formats: Optional[list] = None,
        legend_style: Optional[dict] = None,
        axis_style: Optional[dict] = None,
        map_style: Optional[dict] = None,
        color_style: Optional[dict] = None,
        pane_formats: Optional[list] = None,
        size_style: Optional[dict] = None,
        gridline_style: Optional[dict] = None,
        hide_sort_controls: Optional[bool] = None,
    ) -> str:
        """Apply worksheet-level styling after chart configuration."""
        if pane_formats is not None and (not isinstance(pane_formats, list) or any(not isinstance(item, dict) for item in pane_formats)):
            raise ValueError("pane_formats requires a list of format specifications")
        if legend_style is not None and (not isinstance(legend_style, dict) or any(not isinstance(key, str) or not key.strip() or value is None or isinstance(value, (dict, list, tuple, set)) for key, value in legend_style.items())):
            raise ValueError("legend_style requires nonempty attribute names and scalar values")
        if table_formats is not None:
            if not isinstance(table_formats, list) or any(not isinstance(item, dict) or "attr" not in item or "value" not in item or not isinstance(item["attr"], str) or not item["attr"].strip() or item["value"] is None or set(item) - {"attr", "value", "scope"} or item.get("scope") not in (None, "rows", "cols") for item in table_formats):
                raise ValueError("table_formats requires attr/value entries with optional rows/cols scope")
        ws = self._find_worksheet(worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{worksheet_name}' is malformed: missing <table>")
        def style_instance(expression):
            special = {"Measure Names": ("[:Measure Names]", "nominal"), "Multiple Values": ("[Multiple Values]", "quantitative"), **{name: (f"[{name}]", "quantitative") for name in ("Latitude (generated)", "Longitude (generated)", "Geometry (generated)")}}
            if expression in special:
                from ..field_registry import ColumnInstance
                name, field_type = special[expression]
                return ColumnInstance(column_local_name=name, derivation="None", instance_name=name, ci_type=field_type, is_direct=True)
            return self.field_registry.parse_expression(expression)

        def style_reference(instance):
            dependencies = table.find("view/datasource-dependencies[@datasource='%s']" % self._datasource.get("name", ""))
            if dependencies is not None:
                for existing in dependencies.findall("column-instance"):
                    if existing.get("column") == instance.column_local_name and existing.get("name", "").startswith(instance.instance_name[:-1] + ":"):
                        return self.field_registry.resolve_full_reference(existing.get("name"))
                    if existing.get("column") == instance.column_local_name and existing.get("visual-totals"):
                        return self.field_registry.resolve_full_reference(existing.get("name"))
            return self.field_registry.resolve_full_reference(instance.instance_name)

        hide_row_label_ref = None
        if hide_row_label:
            ci = style_instance(hide_row_label)
            hide_row_label_ref = style_reference(ci)

        # Resolve label_formats field references
        resolved_label_formats = None
        if label_formats:
            resolved_label_formats = []
            for lf in label_formats:
                resolved_lf = {}
                if "field" in lf:
                    ci = style_instance(lf["field"])
                    resolved_lf["_field_ref"] = style_reference(ci)
                for k, v in lf.items():
                    if k != "field":
                        resolved_lf[k] = v
                resolved_label_formats.append(resolved_lf)

        # Resolve cell_formats field references
        resolved_cell_formats = None
        if cell_formats:
            resolved_cell_formats = []
            for cf in cell_formats:
                resolved_cf = {}
                if "field" in cf:
                    ci = style_instance(cf["field"])
                    resolved_cf["_field_ref"] = style_reference(ci)
                for k, v in cf.items():
                    if k != "field":
                        resolved_cf[k] = v
                resolved_cell_formats.append(resolved_cf)

        # Resolve header_formats field references
        resolved_header_formats = None
        if header_formats:
            resolved_header_formats = []
            for hf in header_formats:
                resolved_hf = {}
                if "field" in hf:
                    ci = style_instance(hf["field"])
                    resolved_hf["_field_ref"] = style_reference(ci)
                for k, v in hf.items():
                    if k != "field":
                        resolved_hf[k] = v
                resolved_header_formats.append(resolved_hf)

        dynamic_axis_titles = []
        for specification in (axis_style or {}).get("per_field", []):
            if "title_parameter" in specification:
                parameter = specification["title_parameter"]
                if parameter not in self._parameters:
                    raise ValueError(f"Unknown axis title parameter: {parameter}")
                if not specification.get("field"):
                    raise ValueError("Dynamic axis titles require a field")
                scope = specification.get("scope", "cols")
                if scope not in ("rows", "cols"):
                    raise ValueError("Dynamic axis title scope must be rows or cols")
                dynamic_axis_titles.append((specification, style_reference(self.field_registry.parse_expression(specification["field"]))))

        # Resolve axis_style per_field references
        resolved_axis_style = None
        if axis_style:
            resolved_axis_style = {k: v for k, v in axis_style.items() if k not in ("per_field", "encodings")}
            if "encodings" in axis_style:
                encodings = axis_style["encodings"]
                if not isinstance(encodings, list) or any(not isinstance(item, dict) or not item.get("field") for item in encodings):
                    raise ValueError("axis_style encodings requires a list of field specifications")
                resolved_axis_style["encodings"] = []
                for encoding in encodings:
                    ci = style_instance(encoding["field"])
                    resolved = {key.replace("_", "-"): str(value).lower() if isinstance(value, bool) else str(value) for key, value in encoding.items() if key != "field"}
                    resolved["field"] = style_reference(ci)
                    resolved_axis_style["encodings"].append(resolved)
            if "per_field" in axis_style:
                resolved_per_field = []
                for pf in axis_style["per_field"]:
                    resolved_pf = {k: v for k, v in pf.items() if k not in ("field", "title_parameter")}
                    if "title_parameter" in pf and resolved_pf.get("attr") == "title" and "value" not in resolved_pf:
                        parameter_info = self._parameters[pf["title_parameter"]]
                        parameter_column = self.root.find(f"datasources/datasource[@name='Parameters']/column[@name='{parameter_info['internal_name']}']")
                        raw_value = parameter_column.get("value", "")
                        alias = parameter_column.find(f"aliases/alias[@key='{raw_value}']")
                        resolved_pf["value"] = alias.get("value") if alias is not None else raw_value.strip('"')
                    if "field" in pf:
                        ci = style_instance(pf["field"])
                        resolved_pf["_field_ref"] = style_reference(ci)
                    if "attr" in resolved_pf:
                        resolved_per_field.append(resolved_pf)
                resolved_axis_style["per_field"] = resolved_per_field

        def resolved_mark_style(specification):
            if specification is None:
                return None
            resolved = dict(specification)
            for attribute, expression in specification.items():
                if attribute.replace("_", "-") == "mark-labels-range-field":
                    resolved[attribute] = style_reference(style_instance(expression))
            return resolved

        resolved_panes_style = None
        if panes_style is not None:
            def resolved_pane_style(pane_specification):
                resolved = dict(pane_specification)
                for key in ("mark_style", "pane_mark_style"):
                    if key in resolved:
                        resolved[key] = resolved_mark_style(resolved[key])
                return resolved
            if isinstance(panes_style, dict):
                resolved_panes_style = {key: resolved_pane_style(value) for key, value in panes_style.items()}
            else:
                resolved_panes_style = [resolved_pane_style(value) for value in panes_style]

        from ..native_encodings import size_style_attributes
        resolved_size_style = size_style_attributes(size_style, style_instance, style_reference) if size_style else None

        apply_worksheet_style(
            table,
            background_color=background_color,
            hide_axes=hide_axes,
            hide_gridlines=hide_gridlines,
            hide_zeroline=hide_zeroline,
            hide_borders=hide_borders,
            hide_band_color=hide_band_color,
            hide_row_label_ref=hide_row_label_ref,
            hide_col_field_labels=hide_col_field_labels,
            hide_row_field_labels=hide_row_field_labels,
            hide_sort_controls=hide_sort_controls,
            hide_droplines=hide_droplines,
            hide_reflines=hide_reflines,
            hide_table_dividers=hide_table_dividers,
            table_dividers=table_dividers,
            disable_tooltip=disable_tooltip,
            show_column_totals=show_column_totals,
            show_row_totals=show_row_totals,
            pane_cell_style=pane_cell_style,
            pane_datalabel_style=pane_datalabel_style,
            pane_mark_style=resolved_mark_style(pane_mark_style),
            pane_trendline_hidden=pane_trendline_hidden,
            panes_style=resolved_panes_style,
            resolved_label_formats=resolved_label_formats,
            resolved_cell_formats=resolved_cell_formats,
            pane_formats=pane_formats,
            resolved_header_formats=resolved_header_formats,
            table_formats=table_formats,
            legend_style=legend_style,
            resolved_axis_style=resolved_axis_style,
        )
        for specification, reference in dynamic_axis_titles:
            self._set_parameter_axis_title(ws, reference, specification["title_parameter"], specification.get("scope", "cols"), specification.get("class", "0"))
        if gridline_style:
            if not isinstance(gridline_style, dict) or set(gridline_style) - {"rows", "cols"}:
                raise ValueError("gridline_style requires rows/cols format dictionaries")
            allowed = {"line-visibility", "stroke-color", "stroke-size", "stroke-pattern"}
            for scope, formats in gridline_style.items():
                if not isinstance(formats, dict) or not formats:
                    raise ValueError("gridline_style scopes require nonempty format dictionaries")
                for key, value in formats.items():
                    attr = key.replace("_", "-")
                    if attr not in allowed or isinstance(value, (dict, list)):
                        raise ValueError(f"Unsupported gridline style: {key}")
                    if attr == "line-visibility" and value not in ("on", "off"):
                        raise ValueError("gridline line_visibility must be on or off")
            from lxml import etree
            style = table.find("style")
            rule = style.find("style-rule[@element='gridline']")
            if rule is None:
                rule = etree.SubElement(style, "style-rule", element="gridline")
            for scope, formats in gridline_style.items():
                for key, value in formats.items():
                    attr = key.replace("_", "-")
                    for old in list(rule.findall("format")):
                        if old.get("attr") == attr and old.get("scope") == scope:
                            rule.remove(old)
                    etree.SubElement(rule, "format", attr=attr, scope=scope, value=str(value))
        if resolved_size_style is not None:
            from lxml import etree
            attributes = resolved_size_style
            style = table.find("style")
            rule = style.find("style-rule[@element='mark']")
            if rule is None:
                rule = etree.SubElement(style, "style-rule", element="mark")
            for old in list(rule.findall("encoding")):
                if old.get("attr") == "size" and old.get("field") == attributes["field"]:
                    rule.remove(old)
            etree.SubElement(rule, "encoding", attributes)
        if color_style:
            if not isinstance(color_style, dict) or not color_style.get("field") or not (color_style.get("palette") or color_style.get("colors")):
                raise ValueError("color_style requires field and either palette or colors")
            allowed = {"field", "palette", "colors", "center", "min", "max", "include_totals", "include-totals", "reverse", "num_steps", "num-steps"}
            if set(color_style) - allowed:
                raise ValueError("Unsupported continuous color style setting")
            if "reverse" in color_style and not isinstance(color_style["reverse"], bool):
                raise ValueError("color_style reverse must be boolean")
            if "num_steps" in color_style and "num-steps" in color_style:
                raise ValueError("Use one num_steps spelling")
            steps = color_style.get("num_steps", color_style.get("num-steps"))
            if ("num_steps" in color_style or "num-steps" in color_style) and (isinstance(steps, bool) or not isinstance(steps, int) or steps < 1):
                raise ValueError("color_style num_steps must be a positive integer")
            from lxml import etree
            attributes = {"attr": "color", "type": "interpolated", "field": style_reference(self.field_registry.parse_expression(color_style["field"]))}
            for key, value in color_style.items():
                if key not in {"field", "colors"}:
                    attributes[key.replace("_", "-")] = str(value).lower() if isinstance(value, bool) else str(value)
            colors = color_style.get("colors")
            if colors is not None:
                import re
                if color_style.get("palette") or not isinstance(colors, list) or len(colors) < 2 or any(not isinstance(c, str) or re.fullmatch(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?", c) is None for c in colors):
                    raise ValueError("Custom colors require at least two hex colors and no named palette")
                attributes["type"] = "custom-interpolated"
            style = table.find("style")
            rule = style.find("style-rule[@element='mark']")
            if rule is None:
                rule = etree.SubElement(style, "style-rule", element="mark")
            for old in list(rule.findall("encoding")):
                if old.get("attr") == "color" and old.get("field") == attributes["field"]:
                    rule.remove(old)
            encoding = etree.SubElement(rule, "encoding", attributes)
            if colors is not None:
                palette = etree.SubElement(encoding, "color-palette", custom="true", name="", type="ordered-sequential")
                for color in colors:
                    etree.SubElement(palette, "color").text = color
        if map_style:
            allowed = {"map-style", "washout", "layers"}
            settings = {key.replace("_", "-"): value for key, value in map_style.items()}
            if set(settings) - allowed:
                raise ValueError("map_style supports map_style, washout and layers")
            if "map-style" in settings and settings["map-style"] not in ("light", "normal", "dark", "satellite", "outdoors", "streets"):
                raise ValueError("Unsupported Tableau map style")
            if "washout" in settings and not 0 <= float(settings["washout"]) <= 100:
                raise ValueError("map_style washout must be between 0 and 100")
            from lxml import etree
            style = table.find("style")
            rule = style.find("style-rule[@element='map']")
            if rule is None:
                rule = etree.SubElement(style, "style-rule", element="map")
            layers = settings.pop("layers", None)
            if layers is not None:
                if not isinstance(layers, dict) or any(not isinstance(name, str) or not name or not isinstance(enabled, bool) for name, enabled in layers.items()):
                    raise ValueError("map_style layers must map nonempty layer IDs to booleans")
                layer_rule = style.find("style-rule[@element='map-layer']")
                if layer_rule is None:
                    layer_rule = etree.SubElement(style, "style-rule", element="map-layer")
                for name, enabled in layers.items():
                    for old in list(layer_rule.findall("format")):
                        if old.get("id") == name and old.get("attr") == "enabled":
                            layer_rule.remove(old)
                    etree.SubElement(layer_rule, "format", attr="enabled", id=name, value=str(enabled).lower())
            for attr, value in settings.items():
                for old in list(rule.findall("format")):
                    if old.get("attr") == attr:
                        rule.remove(old)
                etree.SubElement(rule, "format", attr=attr, value=str(value))
        parts = []
        if background_color:
            parts.append(f"background={background_color}")
        for flag_name, flag_val in [
            ("hide_axes", hide_axes), ("hide_gridlines", hide_gridlines),
            ("hide_zeroline", hide_zeroline), ("hide_borders", hide_borders),
            ("hide_band_color", hide_band_color), ("hide_col_field_labels", hide_col_field_labels),
            ("hide_row_field_labels", hide_row_field_labels),
            ("hide_droplines", hide_droplines), ("hide_table_dividers", hide_table_dividers),
            ("disable_tooltip", disable_tooltip),
            ("show_column_totals", show_column_totals),
            ("show_row_totals", show_row_totals),
        ]:
            if flag_val:
                parts.append(flag_name)
        if table_dividers:
            parts.append(f"table_dividers({len(table_dividers)})")
        if pane_cell_style:
            parts.append("pane_cell_style")
        if pane_datalabel_style:
            parts.append("pane_datalabel_style")
        if pane_mark_style:
            parts.append("pane_mark_style")
        if panes_style:
            parts.append("panes_style")
        if label_formats:
            parts.append(f"label_formats({len(label_formats)})")
        if cell_formats:
            parts.append(f"cell_formats({len(cell_formats)})")
        if header_formats:
            parts.append(f"header_formats({len(header_formats)})")
        if axis_style:
            parts.append("axis_style")
        if pane_trendline_hidden:
            parts.append("pane_trendline_hidden")
        return f"Styled worksheet '{worksheet_name}': {', '.join(parts)}"

    def _apply_chart_macros(
        self,
        mark_type: str,
        columns: list[str],
        rows: list[str],
        color: Optional[str],
    ) -> tuple[str, list[str], list[str]]:
        """Compatibility wrapper around helper-level chart macro expansion."""
        return apply_chart_macros(self, mark_type, columns, rows, color)

    def _build_dimension_shelf(self, instances: dict, exprs: list[str]) -> str:
        """Build Tableau shelf text while preserving dimension nesting semantics."""
        return build_dimension_shelf(self, instances, exprs)

    def _setup_table_style(self, table, mark_type) -> None:
        """Apply default table style defaults for the resolved mark type."""
        setup_table_style(table, mark_type)

    def _setup_mapsources(self, view) -> None:
        """Ensure required top-level map source XML exists for map worksheets."""
        setup_mapsources(self, view)

    def _apply_measure_values(
        self,
        view,
        table,
        pane,
        ds_name: str,
        instances: dict,
        measure_values: list[str],
    ) -> None:
        """Attach measure-values specific XML after base pane setup."""
        apply_measure_values(self, view, table, pane, ds_name, instances, measure_values)

    def configure_multi_column_table(
        self,
        worksheet_name: str,
        row_field: str,
        columns: list,
        color_field: Optional[str] = None,
        row_height: int = 38,
        header_height: int = 44,
        mark_size: str = "1.626187801361084",
        spacer_size: str = "0.0099999997764825821",
    ) -> str:
        """构建 MIN(1)/MIN(0) spacer 多列文本表格工作表。"""
        from .builder_table import TableChartBuilder

        builder = TableChartBuilder(
            self,
            worksheet_name=worksheet_name,
            row_field=row_field,
            columns=columns,
            color_field=color_field,
            row_height=row_height,
            header_height=header_height,
            mark_size=mark_size,
            spacer_size=spacer_size,
        )
        return builder.build()
