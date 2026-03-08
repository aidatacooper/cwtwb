"""Map Chart Builder."""

from typing import Optional, Union
from lxml import etree

from .builder_base import BaseChartBuilder

class MapChartBuilder(BaseChartBuilder):
    """Builder for Map charts (Automatic mark over geography)."""

    def __init__(self, editor, worksheet_name: str,
                 geographic_field: str,
                 color: Optional[str] = None,
                 size: Optional[str] = None,
                 label: Optional[str] = None,
                 detail: Optional[str] = None,
                 tooltip: Optional[Union[str, list[str]]] = None,
                 map_fields: Optional[list[str]] = None,
                 filters: Optional[list[dict]] = None) -> None:
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
            None, None, self.color, self.size, self.label, self.detail, None,
            None, self.tooltip, self.filters, self.geographic_field, None
        )
        instances = self._parse_and_prepare_instances(all_exprs, self.filters)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        # Map charts force Mark type to Multipolygon
        pane = self._get_or_create_pane(table)
        self._setup_pane(
            pane, "Multipolygon", "Map", instances,
            self.color, self.size, self.label, self.detail, None, self.tooltip,
            True, self.geographic_field, self.map_fields, ds_name
        )

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
