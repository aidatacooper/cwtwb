"""Public chart facade for TWBEditor.

The public mixin stays stable, while routing, pattern mapping, and shared
builder helpers live in focused internal modules.
"""

from typing import Optional, Union

from .dispatcher import configure_chart as dispatch_configure_chart
from .dispatcher import configure_dual_axis as dispatch_configure_dual_axis
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
        label_extra: Optional[list[str]] = None,
        label_runs: Optional[list[dict]] = None,
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
            tooltip=tooltip,
            filters=filters,
            geographic_field=geographic_field,
            measure_values=measure_values,
            map_fields=map_fields,
            mark_sizing_off=mark_sizing_off,
            axis_fixed_range=axis_fixed_range,
            customized_label=customized_label,
            color_map=color_map,
            text_format=text_format,
            map_layers=map_layers,
            label_extra=label_extra,
            label_runs=label_runs,
        )

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
        )

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
        disable_tooltip: bool = False,
        pane_cell_style: Optional[dict] = None,
        pane_datalabel_style: Optional[dict] = None,
        pane_mark_style: Optional[dict] = None,
        pane_trendline_hidden: bool = False,
        label_formats: Optional[list] = None,
        cell_formats: Optional[list] = None,
        header_formats: Optional[list] = None,
        axis_style: Optional[dict] = None,
    ) -> str:
        """Apply worksheet-level styling after chart configuration."""
        ws = self._find_worksheet(worksheet_name)
        table = ws.find("table")
        if table is None:
            raise ValueError(f"Worksheet '{worksheet_name}' is malformed: missing <table>")
        hide_row_label_ref = None
        if hide_row_label:
            ci = self.field_registry.parse_expression(hide_row_label)
            hide_row_label_ref = self.field_registry.resolve_full_reference(ci.instance_name)

        # Resolve label_formats field references
        resolved_label_formats = None
        if label_formats:
            resolved_label_formats = []
            for lf in label_formats:
                resolved_lf = {}
                if "field" in lf:
                    ci = self.field_registry.parse_expression(lf["field"])
                    resolved_lf["_field_ref"] = self.field_registry.resolve_full_reference(ci.instance_name)
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
                    ci = self.field_registry.parse_expression(cf["field"])
                    resolved_cf["_field_ref"] = self.field_registry.resolve_full_reference(ci.instance_name)
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
                    ci = self.field_registry.parse_expression(hf["field"])
                    resolved_hf["_field_ref"] = self.field_registry.resolve_full_reference(ci.instance_name)
                for k, v in hf.items():
                    if k != "field":
                        resolved_hf[k] = v
                resolved_header_formats.append(resolved_hf)

        # Resolve axis_style per_field references
        resolved_axis_style = None
        if axis_style:
            resolved_axis_style = {k: v for k, v in axis_style.items() if k != "per_field"}
            if "per_field" in axis_style:
                resolved_per_field = []
                for pf in axis_style["per_field"]:
                    resolved_pf = {k: v for k, v in pf.items() if k != "field"}
                    if "field" in pf:
                        ci = self.field_registry.parse_expression(pf["field"])
                        resolved_pf["_field_ref"] = self.field_registry.resolve_full_reference(ci.instance_name)
                    resolved_per_field.append(resolved_pf)
                resolved_axis_style["per_field"] = resolved_per_field

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
            hide_droplines=hide_droplines,
            hide_reflines=hide_reflines,
            hide_table_dividers=hide_table_dividers,
            disable_tooltip=disable_tooltip,
            pane_cell_style=pane_cell_style,
            pane_datalabel_style=pane_datalabel_style,
            pane_mark_style=pane_mark_style,
            pane_trendline_hidden=pane_trendline_hidden,
            resolved_label_formats=resolved_label_formats,
            resolved_cell_formats=resolved_cell_formats,
            resolved_header_formats=resolved_header_formats,
            resolved_axis_style=resolved_axis_style,
        )
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
        ]:
            if flag_val:
                parts.append(flag_name)
        if pane_cell_style:
            parts.append("pane_cell_style")
        if pane_datalabel_style:
            parts.append("pane_datalabel_style")
        if pane_mark_style:
            parts.append("pane_mark_style")
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
        return apply_chart_macros(self, mark_type, columns, rows, color)

    def _build_dimension_shelf(self, instances: dict, exprs: list[str]) -> str:
        return build_dimension_shelf(self, instances, exprs)

    def _setup_table_style(self, table, mark_type) -> None:
        setup_table_style(table, mark_type)

    def _setup_mapsources(self, view) -> None:
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
        apply_measure_values(self, view, table, pane, ds_name, instances, measure_values)
