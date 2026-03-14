"""Text chart builder.

Supports both standard Text marks and Measure Names/Values KPI-style text
layouts so the Text path is explicit in routing instead of being an implicit
helper branch.
"""

from __future__ import annotations

from typing import Optional, Union

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
        label_runs: Optional[list[dict]] = None,
    ) -> None:
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
        self.label_runs = label_runs or []

    def build(self) -> str:
        ws = self.editor._find_worksheet(self.worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{self.worksheet_name}' is malformed: missing <table>")
        view = table.find("view")
        if view is None:
            raise ValueError("Malformed structure: missing <view>")

        ds_name = self._datasource.get("name", "")
        all_exprs = self._gather_expressions(
            self.columns,
            self.rows,
            self.color,
            self.size,
            self.label,
            self.detail,
            None,
            self.sort_descending,
            self.tooltip,
            self.filters,
            None,
            self.measure_values,
        )
        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        pane = self._get_or_create_pane(table)
        self._setup_pane(
            pane,
            "Text",
            "Text",
            instances,
            self.color,
            self.size,
            self.label,
            self.detail,
            None,
            self.tooltip,
            False,
            None,
            None,
            ds_name,
        )

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
