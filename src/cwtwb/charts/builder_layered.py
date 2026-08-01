"""Declarative multi-pane chart builder.

This builder is intended for authored Tableau compositions that need more than
the two panes supported by ``DualAxisChartBuilder``.  Callers describe each
pane independently and may bind a pane to a normal field axis or Tableau's
special ``Multiple Values`` axis.
"""

from __future__ import annotations

from typing import Any, Optional

from lxml import etree

from .builder_base import BaseChartBuilder
from .helpers import build_dimension_shelf


_SPECIAL_MULTIPLE_VALUES = "Multiple Values"


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
        hide_axes: bool = False,
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
        self.hide_axes = hide_axes
        self.table_calc_overrides = table_calc_overrides or {}

    @staticmethod
    def _is_special(expression: Optional[str]) -> bool:
        return str(expression or "").strip() == _SPECIAL_MULTIPLE_VALUES

    def _field_ref(self, instances, expression: str, ds_name: str) -> str:
        if self._is_special(expression):
            return f"[{ds_name}].[Multiple Values]"
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

        def nested(index: int) -> str:
            if index == len(refs) - 1:
                return refs[index]
            return f"({refs[index]} + {nested(index + 1)})"

        return nested(0)

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
            ci = self._instance_for_expression(instances, expression)
            if ci is None:
                continue
            ref = self.field_registry.resolve_full_reference(ci.instance_name)
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

    def _apply_table_calc_overrides(
        self,
        view: etree._Element,
        instances,
        ds_name: str,
    ) -> None:
        """Apply explicit, per-instance Tableau table-calculation addressing."""

        if not self.table_calc_overrides:
            return
        dependencies = view.find(
            f"datasource-dependencies[@datasource='{ds_name}']"
        )
        if dependencies is None:
            return

        for expression, specifications in self.table_calc_overrides.items():
            instance = self._instance_for_expression(instances, expression)
            if instance is None:
                raise ValueError(
                    f"Could not resolve table-calc override field: {expression}"
                )
            column_instance = dependencies.find(
                f"column-instance[@name='{instance.instance_name}']"
            )
            if column_instance is None:
                raise ValueError(
                    f"Missing column instance for table-calc override: {expression}"
                )
            for old in list(column_instance.findall("table-calc")):
                column_instance.remove(old)

            for specification in specifications:
                attributes: dict[str, str] = {}
                for key, value in specification.items():
                    xml_key = key.replace("_", "-")
                    if xml_key == "field":
                        field = self.field_registry._find_field(str(value))
                        attributes[xml_key] = f"[{ds_name}].{field.local_name}"
                    elif xml_key == "ordering-field":
                        ordering_instance = self._instance_for_expression(
                            instances,
                            str(value),
                        )
                        if ordering_instance is None:
                            raise ValueError(
                                "Could not resolve table-calc ordering field: "
                                f"{value}"
                            )
                        attributes[xml_key] = (
                            self.field_registry.resolve_full_reference(
                                ordering_instance.instance_name
                            )
                        )
                    else:
                        attributes[xml_key] = str(value)
                etree.SubElement(column_instance, "table-calc", attributes)

    def _apply_color_map(self, instances, pane_spec: dict[str, Any]) -> None:
        color_map = pane_spec.get("color_map")
        color = pane_spec.get("color")
        if not color_map or not color:
            return
        instance = self._instance_for_expression(instances, color)
        if instance is None:
            raise ValueError(f"Could not resolve layered color field: {color}")
        full_ref = self.field_registry.resolve_full_reference(
            instance.instance_name
        )
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
            if old.get("attr") == "color" and old.get("field") == full_ref:
                mark_rule.remove(old)
        encoding = etree.SubElement(
            mark_rule,
            "encoding",
            {"attr": "color", "field": full_ref, "type": "palette"},
        )
        for value, hex_color in color_map.items():
            mapping = etree.SubElement(encoding, "map", {"to": str(hex_color)})
            bucket = etree.SubElement(mapping, "bucket")
            bucket.text = f'"{value}"'

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
        all_measure_values: list[str] = []
        for pane_spec in self.panes:
            for key in ("axis", "color", "size", "label", "detail"):
                include(pane_spec.get(key))
            for expression in pane_spec.get("labels", []):
                include(expression)
            tooltip = pane_spec.get("tooltip")
            for expression in ([tooltip] if isinstance(tooltip, str) else tooltip or []):
                include(expression)
            for expression in pane_spec.get("measure_values", []):
                include(expression)
                if expression not in all_measure_values:
                    all_measure_values.append(expression)

        instances = self._parse_and_prepare_instances(expressions, None)
        for pane_spec in self.panes:
            self._add_tooltip_instances(
                instances,
                expressions,
                pane_spec.get("tooltip"),
            )
        self._setup_datasource_dependencies(view, ds_name, instances, expressions)
        self._apply_table_calc_overrides(view, instances, ds_name)
        self._append_measure_names_filter(
            view,
            instances,
            ds_name,
            all_measure_values,
        )

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
                if axis_ref not in axis_refs:
                    axis_refs.append(axis_ref)
            pane_view = etree.SubElement(pane, "view")
            etree.SubElement(pane_view, "breakdown", {"value": "auto"})
            self._setup_pane(
                pane,
                pane_spec.get("mark_type", "Automatic"),
                pane_spec.get("mark_type", "Automatic"),
                instances,
                pane_spec.get("color"),
                pane_spec.get("size"),
                pane_spec.get("label"),
                pane_spec.get("detail"),
                None,
                pane_spec.get("tooltip"),
                False,
                None,
                None,
                ds_name,
            )
            self._append_extra_labels(
                pane,
                instances,
                pane_spec.get("labels", []),
            )
            if pane_spec.get("label_runs"):
                self.editor._build_rich_label(
                    pane,
                    instances,
                    pane_spec["label_runs"],
                )
            if pane_spec.get("mark_sizing_off"):
                mark_sizing = etree.Element(
                    "mark-sizing",
                    {"mark-sizing-setting": "marks-scaling-off"},
                )
                mark = pane.find("mark")
                if mark is not None:
                    mark.addnext(mark_sizing)
                else:
                    pane.insert(1, mark_sizing)
            self._apply_pane_style(pane, pane_spec.get("mark_style", {}))
            self._apply_color_map(instances, pane_spec)

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
                rows_element.text = build_dimension_shelf(
                    self.editor,
                    instances,
                    self.rows,
                )
        if columns_element is not None:
            if self.axis_shelf in {"columns", "cols"}:
                columns_element.text = self._build_axis_shelf(
                    instances,
                    self.columns,
                    ds_name,
                )
            else:
                columns_element.text = build_dimension_shelf(
                    self.editor,
                    instances,
                    self.columns,
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
                    "class": str(class_index),
                    "field": axis_ref,
                    "field-type": "quantitative",
                    "fold": "true",
                    "scope": "rows" if self.axis_shelf == "rows" else "cols",
                    "type": "space",
                }
                if self.synchronized:
                    attributes["synchronized"] = "true"
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
