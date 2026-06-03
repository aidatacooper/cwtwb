"""Declarative dashboard layout tree model, coordinate computation, and XML rendering."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from lxml import etree

logger = logging.getLogger(__name__)


def _coerce_text_run(run: dict[str, Any]) -> dict[str, Any]:
    """Normalize one declarative text run while preserving Tableau-like keys."""
    return {
        "text": str(run.get("text", "")),
        "bold": bool(run.get("bold", False)),
        "font_size": str(run.get("font_size", "12")),
        "font_color": str(run.get("font_color", "#111e29")),
        "font_alignment": str(run.get("font_alignment", "1")),
    }


class FlexNode:
    """A node in the declarative dashboard layout tree."""

    def __init__(self, d: dict[str, Any]):
        """Build a layout node from declarative config payload."""
        self.type = d.get("type", "container")
        self.direction = d.get("direction", "vertical")
        self.children = [FlexNode(c) for c in d.get("children", [])]
        self.fixed_size = d.get("fixed_size")
        self.weight = d.get("weight", 1)
        self.style = d.get("style", {})

        self.name = d.get("name")
        self.text_content = d.get("text", "")
        self.font_size = d.get("font_size", "12")
        self.font_color = d.get("font_color", "#111e29")
        self.bold = d.get("bold", False)
        self.text_runs = [
            _coerce_text_run(run)
            for run in d.get("runs", [])
            if isinstance(run, dict)
        ]
        self.layout_strategy = d.get("layout_strategy")
        self.fit = d.get("fit")

        self.worksheet = d.get("worksheet")
        self.field = d.get("field")
        self.mode = d.get("mode", "")
        self.show_title = d.get("show_title", True)

        self.parameter = d.get("parameter")

        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0

        self.px_x = 0.0
        self.px_y = 0.0
        self.px_w = 0.0
        self.px_h = 0.0

    def compute_layout(
        self,
        px_x: float,
        px_y: float,
        px_w: float,
        px_h: float,
        dash_w: float,
        dash_h: float,
    ) -> None:
        """Recursively compute the pixel bounds and Tableau percentage coordinates."""
        self.px_x = px_x
        self.px_y = px_y
        self.px_w = px_w
        self.px_h = px_h

        if dash_w == 0 or dash_h == 0:
            dash_w = 1200
            dash_h = 800

        self.x = int(round((px_x / dash_w) * 100000))
        self.y = int(round((px_y / dash_h) * 100000))
        self.w = int(round((px_w / dash_w) * 100000))
        self.h = int(round((px_h / dash_h) * 100000))

        if self.type != "container" or not self.children:
            return

        if self.direction == "horizontal":
            self._compute_horizontal_children(px_x, px_y, px_w, px_h, dash_w, dash_h)
            return

        self._compute_vertical_children(px_x, px_y, px_w, px_h, dash_w, dash_h)

    def render_to_xml(
        self,
        parent_el,
        get_id_fn: Callable[[], str],
        context: Optional[dict[str, Any]] = None,
    ):
        """Compatibility wrapper to render the node into Tableau XML."""
        return render_flex_node(self, parent_el, get_id_fn, context)

    def _compute_horizontal_children(
        self,
        px_x: float,
        px_y: float,
        px_w: float,
        px_h: float,
        dash_w: float,
        dash_h: float,
    ) -> None:
        """Lay out child nodes left-to-right using fixed sizes and weights."""
        total_fixed = sum(c.fixed_size for c in self.children if c.fixed_size is not None)
        total_weight = sum(c.weight for c in self.children if c.fixed_size is None)
        remaining_px = max(0, px_w - total_fixed)

        curr_x = px_x
        for child in self.children:
            child_px_w = (
                float(child.fixed_size)
                if child.fixed_size is not None
                else (remaining_px * child.weight / total_weight if total_weight else 0.0)
            )
            child.compute_layout(curr_x, px_y, child_px_w, px_h, dash_w, dash_h)
            curr_x += child_px_w

    def _compute_vertical_children(
        self,
        px_x: float,
        px_y: float,
        px_w: float,
        px_h: float,
        dash_w: float,
        dash_h: float,
    ) -> None:
        """Lay out child nodes top-to-bottom using fixed sizes and weights."""
        total_fixed = sum(c.fixed_size for c in self.children if c.fixed_size is not None)
        total_weight = sum(c.weight for c in self.children if c.fixed_size is None)
        remaining_px = max(0, px_h - total_fixed)

        curr_y = px_y
        for child in self.children:
            child_px_h = (
                float(child.fixed_size)
                if child.fixed_size is not None
                else (remaining_px * child.weight / total_weight if total_weight else 0.0)
            )
            child.compute_layout(px_x, curr_y, px_w, child_px_h, dash_w, dash_h)
            curr_y += child_px_h


def render_flex_node(
    node: FlexNode,
    parent_el: etree._Element,
    get_id_fn: Callable[[], str],
    context: Optional[dict[str, Any]] = None,
) -> etree._Element:
    """Render a computed layout node into a Tableau <zone> subtree."""
    context = context or {}
    zone = etree.SubElement(parent_el, "zone")
    zone.set("id", str(get_id_fn()))
    zone.set("x", str(node.x))
    zone.set("y", str(node.y))
    zone.set("w", str(node.w))
    zone.set("h", str(node.h))

    if node.fixed_size is not None:
        zone.set("fixed-size", str(node.fixed_size))
        zone.set("is-fixed", "true")

    if node.type == "container":
        _render_container(node, zone, get_id_fn, context)
    elif node.type == "worksheet":
        zone.set("type-v2", "NONE")
        if node.name:
            zone.set("name", node.name)
        zone.set("show-title", "false")
        
        fit = getattr(node, "fit", None)
        if fit:
            cache = etree.SubElement(zone, "layout-cache")
            if fit == "entire":
                cache.set("type-h", "scalable")
                cache.set("type-w", "scalable")
            elif fit == "width":
                cache.set("type-h", "cell")
                cache.set("type-w", "scalable")
            elif fit == "height":
                cache.set("type-h", "scalable")
                cache.set("type-w", "cell")
            elif fit == "standard":
                cache.set("type-h", "cell")
                cache.set("type-w", "cell")
    elif node.type == "text":
        _render_text(node, zone)
    elif node.type == "filter":
        _render_filter(node, zone, context)
    elif node.type == "paramctrl":
        _render_paramctrl(node, zone, context)
    elif node.type == "color":
        _render_color(node, zone, context)
    elif node.type == "empty":
        _render_empty(node, zone)

    style_dict = dict(node.style)
    if node.type in ("filter", "paramctrl"):
        if "background-color" not in style_dict and "background_color" not in style_dict:
            style_dict["background-color"] = "#ffffff"
    apply_zone_style(zone, style_dict)
    return zone


def apply_zone_style(zone: etree._Element, style_dict: dict[str, Any]) -> None:
    """Attach Tableau zone-style formatting to a zone."""
    zone_style = etree.SubElement(zone, "zone-style")

    defaults = {
        "border-color": "#000000",
        "border-style": "none",
        "border-width": "0",
    }

    merged: dict[str, str] = {}
    for key, value in defaults.items():
        if key not in style_dict and key.replace("-", "_") not in style_dict:
            merged[key] = str(value)

    for key, value in style_dict.items():
        attr_name = key.replace("_", "-")
        if attr_name == "bg-color":
            attr_name = "background-color"
        if value is None:
            continue
        merged[attr_name] = str(value)

    for key, value in merged.items():
        fmt = etree.SubElement(zone_style, "format")
        fmt.set("attr", key)
        fmt.set("value", str(value))


def generate_dashboard_zones(
    parent_zones_el: etree._Element,
    layout_config: dict[str, Any],
    width: int,
    height: int,
    get_id_fn: Callable[[], str],
    context: Optional[dict[str, Any]] = None,
) -> None:
    """Compute and render the full dashboard layout tree."""
    wrapper_node = FlexNode(
        {
            "type": "container",
            "direction": "vertical",
            "children": [layout_config],
        }
    )
    wrapper_node.compute_layout(
        0.0,
        0.0,
        float(width),
        float(height),
        float(width),
        float(height),
    )

    if wrapper_node.children:
        render_flex_node(wrapper_node.children[0], parent_zones_el, get_id_fn, context)


def _render_container(
    node: FlexNode,
    zone: etree._Element,
    get_id_fn: Callable[[], str],
    context: dict[str, Any],
) -> None:
    """Render a layout container zone and recursively emit its children."""
    zone.set("type-v2", "layout-flow")
    zone.set("param", "horz" if node.direction == "horizontal" else "vert")
    if node.layout_strategy:
        zone.set("layout-strategy-id", node.layout_strategy)
    for child in node.children:
        render_flex_node(child, zone, get_id_fn, context)


def _render_text(node: FlexNode, zone: etree._Element) -> None:
    """Render a text zone with one or more formatted-text runs."""
    zone.set("type-v2", "text")
    zone.set("forceUpdate", "true")
    formatted_text = etree.SubElement(zone, "formatted-text")

    if node.text_runs:
        for text_run in node.text_runs:
            run = etree.SubElement(formatted_text, "run")
            if text_run.get("bold"):
                run.set("bold", "true")
            run.set("fontalignment", str(text_run.get("font_alignment", "1")))
            run.set("fontcolor", str(text_run.get("font_color", "#111e29")))
            run.set("fontsize", str(text_run.get("font_size", "12")))
            run.text = str(text_run.get("text", ""))
        return

    run = etree.SubElement(formatted_text, "run")
    if node.bold:
        run.set("bold", "true")
    run.set("fontalignment", "1")
    run.set("fontcolor", node.font_color)
    run.set("fontsize", str(node.font_size))
    run.text = node.text_content


def _render_empty(node: FlexNode, zone: etree._Element) -> None:
    """Render an empty spacer zone."""
    zone.set("type-v2", "empty")


def _render_filter(
    node: FlexNode,
    zone: etree._Element,
    context: dict[str, Any],
) -> None:
    """Render a filter control zone and resolve its backing field reference."""
    zone.set("type-v2", "filter")
    if node.worksheet:
        zone.set("name", node.worksheet)
    if node.mode:
        zone.set("mode", node.mode)
    if not node.show_title:
        zone.set("show-title", "false")

    found_param = _find_filter_param(node, context)
    if found_param:
        zone.set("param", found_param)
    elif node.field and context.get("field_registry"):
        field_registry = context["field_registry"]
        try:
            ci = field_registry.parse_expression(node.field)
            zone.set("param", field_registry.resolve_full_reference(ci.instance_name))
        except (KeyError, ValueError) as exc:
            logger.warning("Failed to resolve filter field '%s': %s", node.field, exc)
            zone.set("param", node.field)
    elif node.field:
        zone.set("param", node.field)


def _render_paramctrl(
    node: FlexNode,
    zone: etree._Element,
    context: dict[str, Any],
) -> None:
    """Render a parameter control zone using workbook parameter metadata."""
    zone.set("type-v2", "paramctrl")
    if node.mode:
        zone.set("mode", node.mode)
    if node.parameter and context.get("parameters"):
        params = context["parameters"]
        param_info = params.get(node.parameter)
        if param_info:
            zone.set("param", f"[Parameters].{param_info['internal_name']}")
        else:
            zone.set("param", f"[Parameters].[{node.parameter}]")
    elif node.parameter:
        zone.set("param", f"[Parameters].[{node.parameter}]")


def _render_color(
    node: FlexNode,
    zone: etree._Element,
    context: dict[str, Any],
) -> None:
    """Render a color legend/control zone bound to a worksheet field."""
    zone.set("type-v2", "color")
    if node.worksheet:
        zone.set("name", node.worksheet)
    if node.field and context.get("field_registry"):
        field_registry = context["field_registry"]
        try:
            ci = field_registry.parse_expression(node.field)
            zone.set("param", field_registry.resolve_full_reference(ci.instance_name))
        except (KeyError, ValueError) as exc:
            logger.warning("Failed to resolve color field '%s': %s", node.field, exc)
            zone.set("param", node.field)


def _find_filter_param(node: FlexNode, context: dict[str, Any]) -> str | None:
    """Try reusing an existing worksheet filter column reference when available."""
    if not (node.field and context.get("editor") and node.worksheet):
        return None

    editor = context["editor"]
    try:
        worksheet_el = editor._find_worksheet(node.worksheet)
    except ValueError:
        return None

    if worksheet_el is None:
        return None

    for filter_el in worksheet_el.findall(".//filter"):
        column = filter_el.get("column", "")
        if node.field in column:
            return column
    return None
