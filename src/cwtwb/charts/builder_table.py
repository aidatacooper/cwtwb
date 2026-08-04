"""Multi-column spacer text table builder for TWBEditor.

Builds complex MIN(1)/MIN(0) multi-column text tables (fake tables in Tableau
used for cell-level formatting, custom alignments, and cell backgrounds).
"""
from __future__ import annotations

from typing import Optional
from lxml import etree

from .builder_base import BaseChartBuilder
from ..contracts.table_column import TableColumn


class TableChartBuilder(BaseChartBuilder):
    """Builder for MIN(1)/MIN(0) multi-column text tables."""

    def __init__(
        self,
        editor,
        worksheet_name: str,
        row_field: str,
        columns: list[TableColumn],
        color_field: Optional[str] = None,
        row_height: int = 38,
        header_height: int = 44,
        mark_size: str = "1.626187801361084",
        spacer_size: str = "0.0099999997764825821",
    ) -> None:
        super().__init__(editor)
        self.worksheet_name = worksheet_name
        self.row_field = row_field
        self.columns_config = columns
        self.color_field = color_field
        self.row_height = row_height
        self.header_height = header_height
        self.mark_size = mark_size
        self.spacer_size = spacer_size

    def build(self) -> str:
        ws = self.editor._find_worksheet(self.worksheet_name)
        old_table = ws.find("table")
        table = etree.Element("table")
        if old_table is not None:
            old_table.addprevious(table)
            ws.remove(old_table)
        else:
            simple_id = ws.find("simple-id")
            if simple_id is not None:
                simple_id.addprevious(table)
            else:
                ws.append(table)
        view = etree.SubElement(table, "view")

        ds_name = self._datasource.get("name", "")
        ds_caption = self._datasource.get("caption", ds_name)

        dss = etree.SubElement(view, "datasources")
        etree.SubElement(dss, "datasource", caption=ds_caption, name=ds_name)
        etree.SubElement(dss, "datasource", name="Parameters")

        all_exprs = [self.row_field]
        if self.color_field:
            all_exprs.append(self.color_field)

        for col in self.columns_config:
            all_exprs.extend([
                col.axis_field,
                col.spacer_field,
                col.bold_field,
                col.normal_field,
            ])

        instances = self._parse_and_prepare_instances(all_exprs, None)
        self._setup_datasource_dependencies(view, ds_name, instances, all_exprs)

        etree.SubElement(view, "aggregation", value="true")

        style = etree.SubElement(table, "style")
        axis_rule = etree.SubElement(style, "style-rule", element="axis")

        axis_class_counts: dict[str, int] = {}

        for col in self.columns_config:
            axis_ci = instances[col.axis_field]
            fld = self.field_registry.resolve_full_reference(axis_ci.instance_name)
            cls_idx = str(axis_class_counts.get(col.axis_field, 0))
            axis_class_counts[col.axis_field] = axis_class_counts.get(col.axis_field, 0) + 1

            enc = etree.SubElement(axis_rule, "encoding")
            for k, v in [
                ("attr", "space"), ("class", cls_idx), ("field", fld),
                ("field-type", "quantitative"), ("major-origin", "0"),
                ("major-show", "false"), ("major-spacing", "1"),
                ("max", "1"), ("min", "0"), ("minor-origin", "0"),
                ("minor-show", "false"), ("minor-spacing", "1"),
                ("range-type", "fixed"), ("scope", "cols"), ("type", "space"),
            ]:
                enc.set(k, v)

            t_fmt = etree.SubElement(axis_rule, "format", attr="title", value="", scope="cols", field=fld)
            t_fmt.set("class", cls_idx)
            etree.SubElement(axis_rule, "format", attr="height", value="20", field=fld)

        for col in self.columns_config:
            spacer_ci = instances[col.spacer_field]
            fld = self.field_registry.resolve_full_reference(spacer_ci.instance_name)
            enc = etree.SubElement(axis_rule, "encoding")
            for k, v in [
                ("attr", "space"), ("class", "0"), ("field", fld),
                ("field-type", "quantitative"), ("fold", "true"),
                ("major-origin", "0"), ("major-show", "false"),
                ("major-spacing", "1"), ("minor-origin", "0"),
                ("minor-show", "false"), ("minor-spacing", "1"),
                ("scope", "cols"), ("synchronized", "true"),
                ("type", "space"),
            ]:
                enc.set(k, v)

            t_fmt = etree.SubElement(axis_rule, "format", attr="title", value=col.header, scope="cols", field=fld)
            t_fmt.set("class", "0")
            etree.SubElement(axis_rule, "format", attr="height", value="20", field=fld)

        etree.SubElement(axis_rule, "format", attr="tick-color", value="#00000000")

        cell_rule = etree.SubElement(style, "style-rule", element="cell")
        row_ci = instances[self.row_field]
        row_ref = self.field_registry.resolve_full_reference(row_ci.instance_name)
        etree.SubElement(cell_rule, "format", attr="height", value=str(self.row_height), field=row_ref)

        header_rule = etree.SubElement(style, "style-rule", element="header")
        etree.SubElement(header_rule, "format", attr="height-header", value=str(self.header_height))
        etree.SubElement(header_rule, "format", attr="border-width", value="0", scope="cols", **{"data-class": "total"})
        etree.SubElement(header_rule, "format", attr="border-style", value="none", scope="cols", **{"data-class": "total"})

        label_rule = etree.SubElement(style, "style-rule", element="label")
        etree.SubElement(label_rule, "format", attr="display", value="false", field=row_ref)
        etree.SubElement(label_rule, "format", attr="text-align", value="left", scope="rows")

        pane_rule = etree.SubElement(style, "style-rule", element="pane")
        etree.SubElement(pane_rule, "format", attr="border-width", value="0", scope="cols", **{"data-class": "total"})
        etree.SubElement(pane_rule, "format", attr="border-style", value="none", scope="cols", **{"data-class": "total"})

        grid_rule = etree.SubElement(style, "style-rule", element="gridline")
        etree.SubElement(grid_rule, "format", attr="stroke-size", value="0", scope="cols")
        etree.SubElement(grid_rule, "format", attr="line-visibility", value="off", scope="cols")

        zero_rule = etree.SubElement(style, "style-rule", element="zeroline")
        etree.SubElement(zero_rule, "format", attr="stroke-size", value="0")
        etree.SubElement(zero_rule, "format", attr="line-visibility", value="off")

        tdiv_rule = etree.SubElement(style, "style-rule", element="table-div")
        etree.SubElement(tdiv_rule, "format", attr="line-pattern-only", value="solid", scope="cols")
        etree.SubElement(tdiv_rule, "format", attr="div-level", value="0", scope="cols")
        etree.SubElement(tdiv_rule, "format", attr="stroke-size", value="0", scope="cols")
        etree.SubElement(tdiv_rule, "format", attr="line-visibility", value="off", scope="cols")

        atitle_rule = etree.SubElement(style, "style-rule", element="axis-title")
        for col in self.columns_config:
            if col.header_font:
                sp_ci = instances[col.spacer_field]
                sp_ref = self.field_registry.resolve_full_reference(sp_ci.instance_name)
                etree.SubElement(atitle_rule, "format", attr="font-family", value=col.header_font, field=sp_ref)

        wsr_rule = etree.SubElement(style, "style-rule", element="worksheet")
        etree.SubElement(wsr_rule, "format", attr="display-field-labels", value="false", scope="cols")

        panes = etree.SubElement(table, "panes")

        anchor = etree.SubElement(panes, "pane", **{"selection-relaxation-option": "selection-relaxation-disallow"})
        aview = etree.SubElement(anchor, "view")
        etree.SubElement(aview, "breakdown", value="auto")
        etree.SubElement(anchor, "mark", **{"class": "Bar"})

        astyle = etree.SubElement(anchor, "style")
        dl = etree.SubElement(astyle, "style-rule", element="datalabel")
        etree.SubElement(dl, "format", attr="color-mode", value="user")
        etree.SubElement(dl, "format", attr="font-size", value="9")
        etree.SubElement(dl, "format", attr="color", value="#333333")

        mk = etree.SubElement(astyle, "style-rule", element="mark")
        etree.SubElement(mk, "format", attr="has-stroke", value="false")

        pr = etree.SubElement(astyle, "style-rule", element="pane")
        etree.SubElement(pr, "format", attr="minheight", value="646")
        etree.SubElement(pr, "format", attr="maxheight", value="646")
        etree.SubElement(pr, "format", attr="minwidth", value="102")
        etree.SubElement(pr, "format", attr="maxwidth", value="102")
        etree.SubElement(pr, "format", attr="aspect", value="0")

        pane_id = 0
        color_ci_ref = self.field_registry.resolve_full_reference(instances[self.color_field].instance_name) if self.color_field else None

        for col in self.columns_config:
            pane_id += 1
            axis_ci = instances[col.axis_field]
            axis_ref = self.field_registry.resolve_full_reference(axis_ci.instance_name)

            p_attrs = {
                "id": str(pane_id),
                "selection-relaxation-option": "selection-relaxation-disallow",
                "x-axis-name": axis_ref,
            }
            if col.axis_index:
                p_attrs["x-index"] = col.axis_index

            pane = etree.SubElement(panes, "pane", **p_attrs)
            pview = etree.SubElement(pane, "view")
            etree.SubElement(pview, "breakdown", value="auto")
            etree.SubElement(pane, "mark", **{"class": "Bar"})
            etree.SubElement(pane, "mark-sizing", **{"mark-sizing-setting": "marks-scaling-off"})

            bold_ci = instances[col.bold_field]
            normal_ci = instances[col.normal_field]
            bold_ref = self.field_registry.resolve_full_reference(bold_ci.instance_name)
            normal_ref = self.field_registry.resolve_full_reference(normal_ci.instance_name)

            enc = etree.SubElement(pane, "encodings")
            if color_ci_ref:
                etree.SubElement(enc, "color", column=color_ci_ref)
            etree.SubElement(enc, "text", column=bold_ref)
            etree.SubElement(enc, "text", column=normal_ref)

            clabel = etree.SubElement(pane, "customized-label")
            cft = etree.SubElement(clabel, "formatted-text")
            r1 = etree.SubElement(cft, "run", bold="true")
            r1.text = f"<{bold_ref}>"
            r2 = etree.SubElement(cft, "run")
            r2.text = f"<{normal_ref}>"

            pstyle = etree.SubElement(pane, "style")
            cellr = etree.SubElement(pstyle, "style-rule", element="cell")
            if col.vertical_align:
                etree.SubElement(cellr, "format", attr="vertical-align", value="center")
            etree.SubElement(cellr, "format", attr="text-align", value=col.text_align)

            dl = etree.SubElement(pstyle, "style-rule", element="datalabel")
            etree.SubElement(dl, "format", attr="color-mode", value="user")
            etree.SubElement(dl, "format", attr="font-size", value="9")
            etree.SubElement(dl, "format", attr="color", value="#333333")

            mk = etree.SubElement(pstyle, "style-rule", element="mark")
            etree.SubElement(mk, "format", attr="mark-labels-show", value="true")
            etree.SubElement(mk, "format", attr="mark-labels-cull", value="true")
            etree.SubElement(mk, "format", attr="size", value=self.mark_size)
            etree.SubElement(mk, "format", attr="has-stroke", value="false")

        for col in self.columns_config:
            pane_id += 1
            spacer_ci = instances[col.spacer_field]
            spacer_ref = self.field_registry.resolve_full_reference(spacer_ci.instance_name)

            pane = etree.SubElement(panes, "pane", id=str(pane_id), **{
                "selection-relaxation-option": "selection-relaxation-disallow",
                "x-axis-name": spacer_ref,
            })
            pview = etree.SubElement(pane, "view")
            etree.SubElement(pview, "breakdown", value="auto")
            etree.SubElement(pane, "mark", **{"class": "Bar"})
            etree.SubElement(pane, "mark-sizing", **{"mark-sizing-setting": "marks-scaling-off"})

            pstyle = etree.SubElement(pane, "style")
            dl = etree.SubElement(pstyle, "style-rule", element="datalabel")
            etree.SubElement(dl, "format", attr="color-mode", value="user")
            etree.SubElement(dl, "format", attr="font-size", value="9")
            etree.SubElement(dl, "format", attr="color", value="#333333")

            mk = etree.SubElement(pstyle, "style-rule", element="mark")
            if col.spacer_color:
                etree.SubElement(mk, "format", attr="size", value="1.9780110120773315")
                etree.SubElement(mk, "format", attr="mark-color", value=col.spacer_color)
                etree.SubElement(mk, "format", attr="has-stroke", value="false")
                etree.SubElement(mk, "format", attr="mark-transparency", value="254")
            else:
                etree.SubElement(mk, "format", attr="size", value=self.spacer_size)
                etree.SubElement(mk, "format", attr="mark-transparency", value="0")
                etree.SubElement(mk, "format", attr="mark-color", value="#ffffff")
                etree.SubElement(mk, "format", attr="has-stroke", value="false")

            pr = etree.SubElement(pstyle, "style-rule", element="pane")
            etree.SubElement(pr, "format", attr="minheight", value="-1")
            etree.SubElement(pr, "format", attr="maxheight", value="-1")

        rows = etree.SubElement(table, "rows")
        rows.text = row_ref

        cols = etree.SubElement(table, "cols")
        cols_refs = []
        for col in self.columns_config:
            ax_ci = instances[col.axis_field]
            sp_ci = instances[col.spacer_field]
            cols_refs.append(self.field_registry.resolve_full_reference(ax_ci.instance_name))
            cols_refs.append(self.field_registry.resolve_full_reference(sp_ci.instance_name))

        def _nested_sum(refs: list[str]) -> str:
            if not refs:
                return ""
            if len(refs) == 1:
                return refs[0]
            return f"({refs[0]} + {_nested_sum(refs[1:])})"

        cols.text = _nested_sum(cols_refs)

        return f"Configured multi-column table for worksheet '{self.worksheet_name}'"
