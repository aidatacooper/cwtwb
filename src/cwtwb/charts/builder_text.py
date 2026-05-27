"""Text chart builder.

Supports both standard Text marks and Measure Names/Values KPI-style text
layouts so the Text path is explicit in routing instead of being an implicit
helper branch.
"""

from __future__ import annotations

from typing import Optional, Union

from lxml import etree

from .builder_base import BaseChartBuilder


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
