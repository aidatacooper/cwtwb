"""Pie Chart Builder."""

from typing import Optional, Union
from lxml import etree

from .builder_base import BaseChartBuilder

class PieChartBuilder(BaseChartBuilder):
    """Builder for Pie charts."""

    def __init__(self, editor, worksheet_name: str,
                 color: Optional[str] = None,
                 wedge_size: Optional[str] = None,
                 label: Optional[str] = None,
                 detail: Optional[str] = None,
                 tooltip: Optional[Union[str, list[str]]] = None,
                 filters: Optional[list[dict]] = None) -> None:
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
