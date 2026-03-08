"""Basic (Single Pane) Chart Builder."""

from typing import Optional, Union
from lxml import etree

from .builder_base import BaseChartBuilder

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
                 filters: Optional[list[dict]] = None) -> None:
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

    def build(self) -> str:
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
        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        pane = self._get_or_create_pane(table)
        self._setup_pane(
            pane, mark_type, self.mark_type, instances,
            self.color, self.size, self.label, self.detail, None, self.tooltip,
            False, None, None, ds_name
        )

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

        return f"Configured worksheet '{self.worksheet_name}' as {self.mark_type} chart"
