"""Declarative multi-pane chart builder.

This builder is intended for authored Tableau compositions that need more than
the two panes supported by ``DualAxisChartBuilder``.  Callers describe each
pane independently and may bind a pane to a normal field axis or Tableau's
special ``Multiple Values`` axis.
"""

from __future__ import annotations

from typing import Any, Optional
from copy import deepcopy
import math
import json

from lxml import etree

from .builder_base import BaseChartBuilder
from .helpers import build_dimension_shelf, setup_mapsources
from ..field_registry import ColumnInstance


_SPECIAL_MULTIPLE_VALUES = "Multiple Values"
_SPECIAL_MEASURE_NAMES = "Measure Names"
_GENERATED_FIELDS = {"Latitude (generated)", "Longitude (generated)", "Geometry (generated)"}


class LayeredChartBuilder(BaseChartBuilder):
    """Build a worksheet from a declarative list of mark panes."""

    def __init__(
        self,
        editor,
        worksheet_name: str,
        *,
        columns: Optional[list[str]] = None,
        rows: Optional[list[str]] = None,
        panes: Optional[list[dict[str, Any]]] = None,
        axis_shelf: str = "rows",
        synchronized: bool = True,
        fold_axes: bool = True,
        hide_axes: bool = False,
        sort_descending: Optional[str] = None,
        sort_field: Optional[str] = None,
        filters: Optional[list[dict]] = None,
        table_calc_overrides: Optional[
            dict[str, list[dict[str, Any]]]
        ] = None,
    ) -> None:
        super().__init__(editor)
        self.worksheet_name = worksheet_name
        self.columns = columns or []
        self.rows = rows or []
        self.panes = panes or []
        self.axis_shelf = axis_shelf
        self.synchronized = synchronized
        if not isinstance(fold_axes, bool):
            raise ValueError("fold_axes must be boolean")
        self.fold_axes = fold_axes
        self.hide_axes = hide_axes
        self.sort_descending = sort_descending
        self.sort_field = sort_field
        self.filters = filters or []
        self.table_calc_overrides = table_calc_overrides or {}

    @staticmethod
    def _is_special(expression: Optional[str]) -> bool:
        return str(expression or "").strip() in {
            _SPECIAL_MULTIPLE_VALUES,
            _SPECIAL_MEASURE_NAMES,
            *_GENERATED_FIELDS,
        }

    def _field_ref(self, instances, expression: str, ds_name: str) -> str:
        if str(expression).strip() in _GENERATED_FIELDS:
            return f"[{ds_name}].[{str(expression).strip()}]"
        if str(expression or "").strip() == _SPECIAL_MULTIPLE_VALUES:
            return f"[{ds_name}].[Multiple Values]"
        if str(expression or "").strip() == _SPECIAL_MEASURE_NAMES:
            return f"[{ds_name}].[:Measure Names]"
        ci = self._instance_for_expression(instances, expression)
        if ci is None:
            raise ValueError(f"Could not resolve layered-chart field: {expression}")
        return self.field_registry.resolve_full_reference(ci.instance_name)

    def _build_axis_shelf(self, instances, expressions: list[str], ds_name: str) -> str:
        refs = [self._field_ref(instances, expr, ds_name) for expr in expressions]
        if not refs:
            return ""
        if len(refs) == 1:
            return refs[0]

        def discrete(expression: str) -> bool:
            if expression == _SPECIAL_MEASURE_NAMES:
                return True
            if self._is_special(expression):
                return False
            instance = self._instance_for_expression(instances, expression)
            return instance.ci_type in {"nominal", "ordinal"}

        kinds = [discrete(expression) for expression in expressions]

        def nested(index: int) -> str:
            if index == len(refs) - 1:
                return refs[index]
            operator = "/" if kinds[index] and kinds[index + 1] else "+" if not kinds[index] and not kinds[index + 1] else "*"
            return f"({refs[index]} {operator} {nested(index + 1)})"

        return nested(0)

    def _build_dimension_shelf(self, instances, expressions: list[str], ds_name: str) -> str:
        if not any(self._is_special(expression) for expression in expressions):
            return build_dimension_shelf(self.editor, instances, expressions)
        refs = [self._field_ref(instances, expression, ds_name) for expression in expressions]
        def nested(index):
            if index == len(refs) - 1:
                return refs[index]
            return f"({refs[index]} / {nested(index + 1)})"
        return nested(0) if refs else ""

    def _append_measure_names_filter(
        self,
        view: etree._Element,
        instances,
        ds_name: str,
        measure_values: list[str],
    ) -> None:
        if not measure_values:
            return
        user_ns = "{http://www.tableausoftware.com/xml/user}"
        filter_el = etree.Element(
            "filter",
            {"class": "categorical", "column": f"[{ds_name}].[:Measure Names]"},
        )
        union = etree.SubElement(
            filter_el,
            "groupfilter",
            {
                "function": "union",
                f"{user_ns}ui-domain": "database",
                f"{user_ns}ui-enumeration": "inclusive",
                f"{user_ns}ui-marker": "enumerate",
            },
        )
        for expression in measure_values:
            ref = self._field_ref(instances, expression, ds_name)
            etree.SubElement(
                union,
                "groupfilter",
                {
                    "function": "member",
                    "level": "[:Measure Names]",
                    "member": f'"{ref}"',
                },
            )
        aggregation = view.find("aggregation")
        if aggregation is not None:
            aggregation.addprevious(filter_el)
        else:
            view.append(filter_el)

        slices = view.find("slices")
        if slices is None:
            slices = etree.Element("slices")
            aggregation = view.find("aggregation")
            if aggregation is not None:
                aggregation.addprevious(slices)
            else:
                view.append(slices)
        measure_names_ref = f"[{ds_name}].[:Measure Names]"
        if not any(
            (column.text or "").strip() == measure_names_ref
            for column in slices.findall("column")
        ):
            column = etree.SubElement(slices, "column")
            column.text = measure_names_ref

    def _append_extra_labels(
        self,
        pane: etree._Element,
        instances,
        labels: list[str],
        ds_name: str,
    ) -> None:
        if not labels:
            return
        encodings = pane.find("encodings")
        if encodings is None:
            encodings = etree.SubElement(pane, "encodings")
        existing = {
            node.get("column")
            for node in encodings.findall("text")
            if node.get("column")
        }
        for expression in labels:
            ref = self._field_ref(instances, expression, ds_name)
            if ref not in existing:
                etree.SubElement(encodings, "text", {"column": ref})
                existing.add(ref)

    @staticmethod
    def _apply_pane_style(pane: etree._Element, formats: dict[str, Any]) -> None:
        if not formats:
            return
        style = pane.find("style")
        if style is None:
            style = etree.SubElement(pane, "style")
        rule = next(
            (item for item in style.findall("style-rule") if item.get("element") == "mark"),
            None,
        )
        if rule is None:
            rule = etree.SubElement(style, "style-rule", {"element": "mark"})
        for attr, value in formats.items():
            for old in list(rule.findall("format")):
                if old.get("attr") == attr:
                    rule.remove(old)
            etree.SubElement(rule, "format", {"attr": attr, "value": str(value)})

    def _apply_trendline(self, pane, specification, formats, instances, ds_name):
        """Configure Tableau's native statistical fit on an individual pane."""
        if specification is None:
            if formats:
                raise ValueError("trendline_style requires a trendline specification")
            return
        if not isinstance(specification, dict):
            raise ValueError("trendline requires a dictionary")
        options = {"enabled": True, "fit": "linear", "exclude_intercept": False,
                   "enable_confidence_bands": False, "exclude_color": False}
        allowed = {*options, "enable_instant_analytics", "enable_tooltips", "degree", "excluded_factors"}
        if set(specification) - allowed:
            raise ValueError("Unknown trendline options")
        options.update(specification)
        if options["fit"] not in {"linear", "polynomial", "log", "exp", "power"}:
            raise ValueError("Unsupported trendline fit")
        for key, value in options.items():
            if key not in {"fit", "degree", "excluded_factors"} and not isinstance(value, bool):
                raise ValueError("Trendline boolean options require boolean values")
        if "degree" in options and (type(options["degree"]) is not int or options["degree"] < 1):
            raise ValueError("Trendline degree must be a positive integer")
        factors = options.pop("excluded_factors", [])
        if not isinstance(factors, list) or any(not isinstance(f, str) or not f.strip() for f in factors):
            raise ValueError("Trendline excluded_factors requires field expressions")
        attributes = {k.replace("_", "-"): str(v).lower() if isinstance(v, bool) else str(v) for k, v in options.items()}
        trendline = etree.Element("trendline", attributes)
        if factors:
            excluded = etree.SubElement(trendline, "excluded-factors")
            for field in factors:
                etree.SubElement(excluded, "column").text = self._field_ref(instances, field, ds_name)
        anchor = next((pane.find(tag) for tag in ("reference-line", "customized-tooltip", "customized-label", "style") if pane.find(tag) is not None), None)
        if anchor is None:
            pane.append(trendline)
        else:
            anchor.addprevious(trendline)
        if formats:
            if not isinstance(formats, dict):
                raise ValueError("trendline_style requires a format dictionary")
            style = pane.find("style")
            if style is None:
                style = etree.SubElement(pane, "style")
            rule = etree.SubElement(style, "style-rule", element="trendline")
            for key, value in formats.items():
                etree.SubElement(rule, "format", attr=str(key), value=str(value))

    def _apply_table_calc_overrides(
        self,
        view: etree._Element,
        instances,
        ds_name: str,
    ) -> None:
        """Apply explicit, per-instance Tableau table-calculation addressing."""

        super()._apply_table_calc_overrides(
            view, instances, ds_name, self.table_calc_overrides
        )

    def _apply_color_map(self, instances, pane_spec: dict[str, Any], view: etree._Element) -> None:
        color_map = pane_spec.get("color_map")
        color = pane_spec.get("color")
        if not color_map or not color:
            return
        if color == _SPECIAL_MEASURE_NAMES:
            buckets = {}
            for expression, hex_color in color_map.items():
                measure = self._instance_for_expression(instances, expression)
                if measure is None:
                    raise ValueError(f"Could not resolve Measure Names palette member: {expression}")
                reference = self.field_registry.resolve_full_reference(measure.instance_name)
                buckets[json.dumps(reference)] = hex_color
            self.editor.set_datasource_color_palette("Measure Names", buckets, is_measure_names=True)
            return
        instance = self._instance_for_expression(instances, color)
        if instance is None:
            raise ValueError(f"Could not resolve layered color field: {color}")
        if self._datasource.find(
            f"column-instance[@name='{instance.instance_name}']"
        ) is None:
            palette_instance = etree.Element("column-instance")
            palette_instance.set("column", instance.column_local_name)
            palette_instance.set("derivation", instance.derivation)
            palette_instance.set("name", instance.instance_name)
            palette_instance.set("pivot", "key")
            palette_instance.set("type", instance.ci_type)
            anchor = next(
                (
                    self._datasource.find(tag)
                    for tag in ("group", "layout", "style", "semantic-values", "date-options", "object-graph")
                    if self._datasource.find(tag) is not None
                ),
                None,
            )
            if anchor is not None:
                anchor.addprevious(palette_instance)
            else:
                self._datasource.append(palette_instance)
        # Palette identity includes table-calculation addressing, not just its
        # field name. Preserve the worksheet's actual nested calculation context.
        palette_instance = self._datasource.find(
            f"column-instance[@name='{instance.instance_name}']"
        )
        bound_instance = view.find(
            f"datasource-dependencies/column-instance[@name='{instance.instance_name}']"
        )
        if bound_instance is not None:
            for old in list(palette_instance.findall("table-calc")):
                palette_instance.remove(old)
            for calculation in bound_instance.findall("table-calc"):
                palette_instance.append(deepcopy(calculation))
        style = self._datasource.find("style")
        if style is None:
            style = etree.Element("style")
            anchor = next(
                (
                    self._datasource.find(tag)
                    for tag in (
                        "semantic-values",
                        "date-options",
                        "default-date-format",
                        "object-graph",
                    )
                    if self._datasource.find(tag) is not None
                ),
                None,
            )
            if anchor is not None:
                anchor.addprevious(style)
            else:
                self._datasource.append(style)
        mark_rule = next(
            (
                rule
                for rule in style.findall("style-rule")
                if rule.get("element") == "mark"
            ),
            None,
        )
        if mark_rule is None:
            mark_rule = etree.SubElement(style, "style-rule", {"element": "mark"})
        for old in list(mark_rule.findall("encoding")):
            if old.get("attr") == "color" and old.get("field") == instance.instance_name:
                mark_rule.remove(old)
        encoding = etree.SubElement(
            mark_rule,
            "encoding",
            {"attr": "color", "field": instance.instance_name, "type": "palette"},
        )
        for value, hex_color in color_map.items():
            mapping = etree.SubElement(encoding, "map", {"to": str(hex_color)})
            bucket = etree.SubElement(mapping, "bucket")
            bucket.text = self._format_palette_value(value, instance)

    def build(self) -> str:
        """Build all declared panes, shelves, dependencies, and axis folding."""
        if not self.panes:
            raise ValueError("Layered charts require at least one pane")
        if self.axis_shelf not in {"rows", "columns", "cols"}:
            raise ValueError("axis_shelf must be 'rows', 'columns', or 'cols'")

        worksheet = self.editor._find_worksheet(self.worksheet_name)
        table = worksheet.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is missing <table>")
        view = table.find("view")
        if view is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is missing <view>")
        ds_name = self._datasource.get("name", "")

        expressions: list[str] = []

        def include(expression: Optional[str]) -> None:
            text = str(expression or "").strip()
            if text and not self._is_special(text) and text not in expressions:
                expressions.append(text)

        for expression in self.columns + self.rows:
            include(expression)
        include(self.sort_descending)
        include(self.sort_field)
        for specification in self.filters:
            include(specification.get("column"))
        all_measure_values: list[str] = []
        for pane_spec in self.panes:
            for key in ("axis", "color", "size", "label", "detail", "path", "shape"):
                include(pane_spec.get(key))
            for expression in pane_spec.get("color_extra", []):
                include(expression)
            for expression in pane_spec.get("detail_extra", []):
                include(expression)
            trendline = pane_spec.get("trendline")
            if isinstance(trendline, dict) and isinstance(trendline.get("excluded_factors", []), list):
                for expression in trendline.get("excluded_factors", []):
                    if isinstance(expression, str):
                        include(expression)
            include(pane_spec.get("geometry"))
            for expression in pane_spec.get("labels", []):
                include(expression)
            tooltip = pane_spec.get("tooltip")
            for expression in ([tooltip] if isinstance(tooltip, str) else tooltip or []):
                include(expression)
            for expression in pane_spec.get("measure_values", []):
                include(expression)
                if expression not in all_measure_values:
                    all_measure_values.append(expression)

        instances = self._parse_and_prepare_instances(expressions, self.filters)
        if self.sort_field is not None:
            bound_expressions = list(self.columns + self.rows)
            for specification in self.panes:
                bound_expressions.extend(specification.get(key) for key in ("detail", "color", "path", "label") if specification.get(key))
                for key in ("detail_extra", "color_extra", "labels"):
                    bound_expressions.extend(specification.get(key, []))
            target = self._instance_for_expression(instances, self.sort_field)
            bound_instances = [self._instance_for_expression(instances, expression) for expression in bound_expressions if not self._is_special(expression)]
            if target is None or target.ci_type not in {"nominal", "ordinal"} or not any(instance and instance.instance_name == target.instance_name for instance in bound_instances):
                raise ValueError("sort_field must identify a dimension bound to a shelf or mark encoding")
        for pane_spec in self.panes:
            self._add_tooltip_instances(
                instances,
                expressions,
                pane_spec.get("tooltip"),
            )
        self._setup_datasource_dependencies(view, ds_name, instances, expressions)
        geographic = any(pane.get("geometry") in _GENERATED_FIELDS for pane in self.panes) or any(expr in _GENERATED_FIELDS for expr in self.columns + self.rows)
        if geographic:
            setup_mapsources(self.editor, view)
        for name in _GENERATED_FIELDS:
            instances[name] = ColumnInstance(column_local_name=f"[{name}]", derivation="None", instance_name=f"[{name}]", ci_type="quantitative", is_direct=True)
        self._apply_table_calc_overrides(view, instances, ds_name)
        self._add_filters(view, instances, self.filters)
        if self.sort_descending:
            row_instances = [self._instance_for_expression(instances, expression) for expression in self.rows]
            sort_instance = self._instance_for_expression(instances, self.sort_field) if self.sort_field else None
            if sort_instance is not None and not any(instance and instance.instance_name == sort_instance.instance_name for instance in row_instances):
                if sort_instance.ci_type not in {"nominal", "ordinal"}:
                    raise ValueError("sort_field must identify a dimension")
                measure = self._instance_for_expression(instances, self.sort_descending)
                for old in list(view.findall("computed-sort")):
                    if old.get("column") == self.field_registry.resolve_full_reference(sort_instance.instance_name):
                        view.remove(old)
                sort = etree.Element("computed-sort", column=self.field_registry.resolve_full_reference(sort_instance.instance_name), direction="DESC", using=self.field_registry.resolve_full_reference(measure.instance_name))
                anchor = next((view.find(tag) for tag in ("slices", "aggregation") if view.find(tag) is not None), None)
                if anchor is not None:
                    anchor.addprevious(sort)
                else:
                    view.append(sort)
            else:
                self._add_shelf_sort(view, ds_name, instances, self.rows, self.sort_descending, sort_field=self.sort_field)
        self._append_measure_names_filter(
            view,
            instances,
            ds_name,
            all_measure_values,
        )
        for old in list(view.findall("manual-sort")):
            if old.get("column") == f"[{ds_name}].[:Measure Names]":
                view.remove(old)
        if all_measure_values:
            values = etree.Element("manual-sort", column=f"[{ds_name}].[:Measure Names]", direction="ASC")
            dictionary = etree.SubElement(values, "dictionary")
            for expression in all_measure_values:
                bucket = etree.SubElement(dictionary, "bucket")
                bucket.text = '"' + self._field_ref(instances, expression, ds_name) + '"'
            anchor = next((view.find(tag) for tag in ("shelf-sorts", "slices", "aggregation") if view.find(tag) is not None), None)
            if anchor is not None:
                anchor.addprevious(values)
            else:
                view.append(values)

        old_pane = table.find("pane")
        if old_pane is not None:
            table.remove(old_pane)
        old_panes = table.find("panes")
        if old_panes is not None:
            table.remove(old_panes)
        panes_element = etree.Element("panes")

        axis_attribute = (
            "y-axis-name" if self.axis_shelf == "rows" else "x-axis-name"
        )
        axis_refs: list[str] = []
        for index, pane_spec in enumerate(self.panes, start=1):
            pane = etree.SubElement(
                panes_element,
                "pane",
                {
                    "id": str(index),
                    "selection-relaxation-option": pane_spec.get(
                        "selection_relaxation",
                        "selection-relaxation-allow",
                    ),
                },
            )
            axis = pane_spec.get("axis")
            if axis:
                axis_ref = self._field_ref(instances, axis, ds_name)
                pane.set(axis_attribute, axis_ref)
                if axis in {_SPECIAL_MULTIPLE_VALUES, *_GENERATED_FIELDS}:
                    pane.set("y-index" if self.axis_shelf == "rows" else "x-index", str(axis_refs.count(axis_ref)))
                axis_refs.append(axis_ref)
            pane_view = etree.SubElement(pane, "view")
            breakdown = pane_spec.get("breakdown", "auto")
            if breakdown not in {"auto", "on", "off"}:
                raise ValueError("Pane breakdown must be auto, on or off")
            etree.SubElement(pane_view, "breakdown", {"value": breakdown})
            self._setup_pane(
                pane,
                pane_spec.get("mark_type", "Automatic"),
                pane_spec.get("mark_type", "Automatic"),
                instances,
                None if self._is_special(pane_spec.get("color")) else pane_spec.get("color"),
                None if self._is_special(pane_spec.get("size")) else pane_spec.get("size"),
                None if self._is_special(pane_spec.get("label")) else pane_spec.get("label"),
                pane_spec.get("detail"),
                None,
                pane_spec.get("tooltip"),
                False,
                None,
                None,
                ds_name,
            )
            if pane_spec.get("color") == _SPECIAL_MEASURE_NAMES:
                encodings = pane.find("encodings")
                if encodings is None:
                    encodings = etree.Element("encodings")
                    pane.find("mark").addnext(encodings)
                etree.SubElement(
                    encodings,
                    "color",
                    {"column": f"[{ds_name}].[:Measure Names]"},
                )
            encodings = pane.find("encodings")
            if encodings is None:
                encodings = etree.Element("encodings")
                pane.find("mark").addnext(encodings)
            if pane_spec.get("size") == _SPECIAL_MEASURE_NAMES:
                etree.SubElement(encodings, "size", column=f"[{ds_name}].[:Measure Names]")
            for expression in pane_spec.get("color_extra", []):
                etree.SubElement(encodings, "color", column=self._field_ref(instances, expression, ds_name))
            for expression in pane_spec.get("detail_extra", []):
                etree.SubElement(encodings, "lod", column=self._field_ref(instances, expression, ds_name))
            if pane_spec.get("geometry"):
                etree.SubElement(encodings, "geometry", column=self._field_ref(instances, pane_spec["geometry"], ds_name))
            if pane_spec.get("path"):
                etree.SubElement(encodings, "path", column=self._field_ref(instances, pane_spec["path"], ds_name))
            if pane_spec.get("shape"):
                etree.SubElement(encodings, "shape", column=self._field_ref(instances, pane_spec["shape"], ds_name))
            self._append_extra_labels(
                pane,
                instances,
                pane_spec.get("labels", []) + ([pane_spec["label"]] if self._is_special(pane_spec.get("label")) else []),
                ds_name,
            )
            if pane_spec.get("label_runs"):
                self._build_rich_label(
                    pane,
                    instances,
                    pane_spec["label_runs"],
                )
            sizing = pane_spec.get("mark_sizing")
            if sizing is not None:
                if not isinstance(sizing, dict) or not sizing:
                    raise ValueError("mark_sizing must be a nonempty dictionary")
                sizing = {key.replace("_", "-"): value for key, value in sizing.items()}
                allowed = {"mark-sizing-setting", "mark-alignment", "use-custom-mark-size", "custom-mark-size-in-axis-units"}
                if set(sizing) - allowed:
                    raise ValueError("Unsupported mark sizing attribute")
                if pane_spec.get("mark_sizing_off"):
                    raise ValueError("Use mark_sizing or mark_sizing_off, not both")
                if "mark-sizing-setting" in sizing and sizing["mark-sizing-setting"] not in {"marks-scaling-on", "marks-scaling-off"}:
                    raise ValueError("Invalid mark sizing setting")
                if "mark-alignment" in sizing and sizing["mark-alignment"] not in {"mark-alignment-center", "mark-alignment-start", "mark-alignment-end"}:
                    raise ValueError("Invalid mark alignment")
                if "use-custom-mark-size" in sizing:
                    if not isinstance(sizing["use-custom-mark-size"], bool):
                        raise ValueError("use-custom-mark-size must be boolean")
                    sizing["use-custom-mark-size"] = str(sizing["use-custom-mark-size"]).lower()
                if "custom-mark-size-in-axis-units" in sizing:
                    value = sizing["custom-mark-size-in-axis-units"]
                    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
                        raise ValueError("Axis-unit mark size must be finite and positive")
                sizing = {key: str(value) for key, value in sizing.items()}
            elif pane_spec.get("mark_sizing_off"):
                sizing = {"mark-sizing-setting": "marks-scaling-off"}
            if sizing:
                mark_sizing = etree.Element(
                    "mark-sizing",
                    sizing,
                )
                mark = pane.find("mark")
                if mark is not None:
                    mark.addnext(mark_sizing)
                else:
                    pane.insert(1, mark_sizing)
            self._apply_pane_style(pane, pane_spec.get("mark_style", {}))
            self._apply_trendline(pane, pane_spec.get("trendline"), pane_spec.get("trendline_style"), instances, ds_name)
            self._apply_color_map(instances, pane_spec, view)
            if pane_spec.get("shape_map"):
                shape = self._instance_for_expression(instances, pane_spec.get("shape", ""))
                if shape is None:
                    raise ValueError("shape_map requires a shape field")
                style = self._datasource.find("style")
                if style is None:
                    style = etree.SubElement(self._datasource, "style")
                rule = style.find("style-rule[@element='mark']")
                if rule is None:
                    rule = etree.SubElement(style, "style-rule", element="mark")
                for old in list(rule.findall("encoding")):
                    if old.get("attr") == "shape" and old.get("field") == shape.instance_name:
                        rule.remove(old)
                encoding = etree.SubElement(rule, "encoding", attr="shape", field=shape.instance_name, type="palette")
                # Shape identities, like colour identities, include the actual
                # worksheet instance and its table calculation addressing.
                palette_instance = self._datasource.find(f"column-instance[@name='{shape.instance_name}']")
                if palette_instance is None:
                    bound = view.find(f"datasource-dependencies/column-instance[@name='{shape.instance_name}']")
                    palette_instance = deepcopy(bound)
                    style.addprevious(palette_instance)
                for value, symbol in pane_spec["shape_map"].items():
                    mapping = etree.SubElement(encoding, "map", to=str(symbol))
                    etree.SubElement(mapping, "bucket").text = self._format_palette_value(value, shape)

        rows_element = table.find("rows")
        columns_element = table.find("cols")
        if rows_element is not None:
            if self.axis_shelf == "rows":
                rows_element.text = self._build_axis_shelf(
                    instances,
                    self.rows,
                    ds_name,
                )
            else:
                rows_element.text = self._build_dimension_shelf(
                    instances,
                    self.rows,
                    ds_name,
                )
        if columns_element is not None:
            if self.axis_shelf in {"columns", "cols"}:
                columns_element.text = self._build_axis_shelf(
                    instances,
                    self.columns,
                    ds_name,
                )
            else:
                columns_element.text = self._build_dimension_shelf(
                    instances,
                    self.columns,
                    ds_name,
                )

        old_style = table.find("style")
        if old_style is not None:
            table.remove(old_style)
        table_style = etree.Element("style")
        if axis_refs:
            axis_rule = etree.SubElement(table_style, "style-rule", {"element": "axis"})
            if self.hide_axes:
                etree.SubElement(
                    axis_rule,
                    "format",
                    {
                        "attr": "display",
                        "field": axis_refs[0],
                        "scope": "rows" if self.axis_shelf == "rows" else "cols",
                        "value": "false",
                    },
                )
            for class_index, axis_ref in enumerate(axis_refs[1:]):
                attributes = {
                    "attr": "space",
                    "class": str(class_index + 1 if axis_ref == axis_refs[0] else class_index),
                    "field": axis_ref,
                    "field-type": "quantitative",
                    "fold": "true",
                    "scope": "rows" if self.axis_shelf == "rows" else "cols",
                    "type": "space",
                }
                if self.synchronized:
                    attributes["synchronized"] = "true"
                if self.fold_axes:
                    etree.SubElement(axis_rule, "encoding", attributes)
                if self.hide_axes:
                    etree.SubElement(
                        axis_rule,
                        "format",
                        {
                            "attr": "display",
                            "class": str(class_index),
                            "field": axis_ref,
                            "scope": attributes["scope"],
                            "value": "false",
                        },
                    )

        insertion_index = min(
            [
                list(table).index(node)
                for node in (table.find("rows"), table.find("cols"))
                if node is not None
            ]
            or [len(table)]
        )
        table.insert(insertion_index, table_style)
        table.insert(insertion_index + 1, panes_element)
        return self.worksheet_name
