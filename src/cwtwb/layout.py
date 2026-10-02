"""Declarative dashboard layout tree model, coordinate computation, and XML rendering."""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from lxml import etree

logger = logging.getLogger(__name__)


def _coerce_text_run(run: dict[str, Any]) -> dict[str, Any]:
    """Normalize one declarative text run while preserving Tableau-like keys."""
    res = {
        "text": str(run.get("text", "")),
        "bold": bool(run.get("bold", False)),
        "font_size": str(run.get("font_size", "12")),
        "font_color": str(run.get("font_color", "#111e29")),
        "font_alignment": str(run.get("font_alignment", "1")),
    }
    if "font_name" in run or "fontname" in run:
        res["font_name"] = str(run.get("font_name") or run.get("fontname"))
    if "parameter" in run:
        res["parameter"] = run["parameter"]
    if "hyperlink" in run:
        res["hyperlink"] = str(run.get("hyperlink"))
    return res


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
        self.show_apply = d.get("show_apply")
        self.values = d.get("values")
        self.show_all = d.get("show_all")
        self.visibility = d.get("visibility")
        self.corner_radius = d.get("corner_radius")
        self.absolute = d.get("absolute")

        self.parameter = d.get("parameter") or d.get("param")
        self.target_dashboard = d.get("target_dashboard")
        self.caption = d.get("caption", "GO BACK")
        self.control_caption = d.get("caption")
        self.background_color = d.get("background_color", "#1ba3c6")

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

        if self.direction == "floating":
            for child in self.children:
                if getattr(child, "absolute", None) and isinstance(child.absolute, dict):
                    c_abs = child.absolute
                    c_px_x = (float(c_abs.get("x", 0)) / 100000.0) * dash_w
                    c_px_y = (float(c_abs.get("y", 0)) / 100000.0) * dash_h
                    c_px_w = (float(c_abs.get("w", 100000)) / 100000.0) * dash_w
                    c_px_h = (float(c_abs.get("h", 100000)) / 100000.0) * dash_h
                    child.compute_layout(c_px_x, c_px_y, c_px_w, c_px_h, dash_w, dash_h)
                else:
                    child.compute_layout(px_x, px_y, px_w, px_h, dash_w, dash_h)
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
    if getattr(node, "absolute", None) and isinstance(node.absolute, dict):
        abs_pos = node.absolute
        zone.set("x", str(abs_pos.get("x", node.x)))
        zone.set("y", str(abs_pos.get("y", node.y)))
        zone.set("w", str(abs_pos.get("w", node.w)))
        zone.set("h", str(abs_pos.get("h", node.h)))
    else:
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
        if not node.show_title:
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
        _render_text(node, zone, context)
    elif node.type == "filter":
        _render_filter(node, zone, context)
    elif node.type == "paramctrl":
        _render_paramctrl(node, zone, context)
    elif node.type == "color":
        _render_color(node, zone, context)
    elif node.type == "navigation_button":
        _render_navigation_button(node, zone, context)
    elif node.type == "empty":
        _render_empty(node, zone)

    style_dict = dict(node.style)
    if node.type in ("filter", "paramctrl"):
        if "background-color" not in style_dict and "background_color" not in style_dict:
            style_dict["background-color"] = "#ffffff"
    apply_zone_style(zone, style_dict)
    if node.corner_radius is not None:
        from math import isfinite
        radius = node.corner_radius
        if isinstance(radius, bool) or not isinstance(radius, (int, float)) or not isfinite(radius) or radius < 0:
            raise ValueError("corner_radius must be a finite nonnegative number")
        editor = context.get("editor")
        if editor is None:
            raise ValueError("Rounded dashboard corners require editor context")
        feature = "_.fcp.DashboardRoundedCorners.true..."
        manifest = editor.root.find("document-format-change-manifest")
        if manifest is None:
            manifest = etree.Element("document-format-change-manifest")
            editor.root.insert(0, manifest)
        if manifest.find(feature + "DashboardRoundedCorners") is None:
            etree.SubElement(manifest, feature + "DashboardRoundedCorners")
        etree.SubElement(zone.find("zone-style"), feature + "format", attr="corner-radius", value=str(radius))
    if node.visibility is not None:
        visibility = node.visibility
        if not isinstance(visibility, dict) or not isinstance(visibility.get("field"), str) or not visibility["field"].strip():
            raise ValueError("visibility requires a nonempty field expression")
        if "initially_visible" in visibility and not isinstance(visibility["initially_visible"], bool):
            raise ValueError("visibility.initially_visible must be boolean")
        editor = context.get("editor")
        if editor is None:
            raise ValueError("Dynamic zone visibility requires editor context")
        field_info = editor.field_registry._find_field(visibility["field"])
        if field_info.datatype != "boolean":
            raise ValueError("Dynamic zone visibility requires a boolean field")
        if not visibility.get("initially_visible", True):
            for child_zone in zone.iter("zone"):
                child_zone.set("hidden-by-user", "true")
        context.setdefault("visibility_bindings", []).append((zone.get("id"), field_info.local_name))
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
    if node.direction == "floating" or node.type == "floating":
        zone.set("type-v2", "layout-basic")
    else:
        zone.set("type-v2", "layout-flow")
        zone.set("param", "horz" if node.direction == "horizontal" else "vert")
    if node.layout_strategy:
        zone.set("layout-strategy-id", node.layout_strategy)
    for child in node.children:
        target_parent = zone
        if node.direction == "floating" and child.type == "navigation_button":
            # Floating dashboard objects are peers of the tiled root zone.
            # Nesting navigation objects inside layout-basic clips the button.
            ancestor = zone.getparent()
            while ancestor is not None and ancestor.tag != "zones":
                ancestor = ancestor.getparent()
            if ancestor is not None:
                target_parent = ancestor
        render_flex_node(child, target_parent, get_id_fn, context)


def _render_text(node: FlexNode, zone: etree._Element, context: dict[str, Any]) -> None:
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
            if text_run.get("font_name"):
                run.set("fontname", str(text_run["font_name"]))
            if text_run.get("hyperlink"):
                run.set("hyperlink", str(text_run["hyperlink"]))
            if "parameter" in text_run:
                parameter = text_run["parameter"]
                parameters = context.get("parameters", {})
                if not isinstance(parameter, str) or parameter not in parameters:
                    raise ValueError(f"Unknown text run parameter: {parameter}")
                if text_run.get("text"):
                    raise ValueError("A text run accepts text or parameter, not both")
                run.text = f"<[Parameters].{parameters[parameter]['internal_name']}>"
            else:
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


def _render_navigation_button(
    node: FlexNode,
    zone: etree._Element,
    context: dict[str, Any],
) -> None:
    """Render a text navigation button targeting another dashboard."""

    editor = context.get("editor")
    if editor is None:
        raise ValueError("Navigation button rendering requires editor context.")
    target = str(node.target_dashboard or "").strip()
    if not target:
        raise ValueError("navigation_button requires target_dashboard.")
    target_dashboard = editor.root.find(
        f"./dashboards/dashboard[@name='{target}']"
    )
    if target_dashboard is None:
        raise ValueError(f"Target dashboard '{target}' was not found.")
    target_window = editor.root.find(
        f"./windows/window[@class='dashboard'][@name='{target}']"
    )
    simple_id = target_window.find("simple-id") if target_window is not None else None
    if simple_id is None or not simple_id.get("uuid"):
        raise ValueError(f"Target dashboard '{target}' has no dashboard window id.")

    manifest = editor.root.find("document-format-change-manifest")
    if manifest is None:
        manifest = etree.Element("document-format-change-manifest")
        editor.root.insert(0, manifest)
    for feature in ("BasicButtonObject", "BasicButtonObjectTextSupport", "NavigationAction"):
        if manifest.find(feature) is None:
            attributes = {"ignorable": "true", "predowngraded": "true"} if feature == "BasicButtonObjectTextSupport" else {}
            etree.SubElement(manifest, feature, **attributes)

    zone.set("type", "dashboard-object")
    button = etree.SubElement(zone, "button")
    button.set(
        "action",
        f'tabdoc:goto-sheet window-id="{simple_id.get("uuid")}"',
    )
    button.set("button-type", "text")
    visual_state = etree.SubElement(button, "button-visual-state")
    caption = etree.SubElement(visual_state, "caption")
    caption.text = str(node.caption)
    font = etree.SubElement(visual_state, "button-caption-font-style")
    font.set("bold", "true" if node.bold else "false")
    font.set("fontcolor", str(node.font_color or "#ffffff"))
    font.set("fontname", "Tableau Medium")
    background = etree.SubElement(visual_state, "format")
    background.set("attr", "background-color")
    background.set("value", str(node.background_color))


def _render_control_caption(node: FlexNode, zone: etree._Element) -> None:
    """Override a control title without changing its field/parameter identity."""
    if node.control_caption is not None:
        zone.set("custom-title", "true")
        formatted = etree.SubElement(zone, "formatted-text")
        etree.SubElement(formatted, "run").text = str(node.control_caption)


def _render_filter(
    node: FlexNode,
    zone: etree._Element,
    context: dict[str, Any],
) -> None:
    """Render a filter control zone and resolve its backing field reference."""
    zone.set("type-v2", "filter")
    _render_control_caption(node, zone)
    if node.worksheet:
        zone.set("name", node.worksheet)
    if node.mode:
        zone.set("mode", node.mode)
    if node.values is not None:
        if node.values not in ("relevant", "all", "database"):
            raise ValueError("filter values must be relevant, all, or database")
        zone.set("values", node.values)
    if node.show_all is not None:
        if not isinstance(node.show_all, bool):
            raise ValueError("filter show_all must be boolean")
        zone.set("show-all", str(node.show_all).lower())
    if not node.show_title:
        zone.set("show-title", "false")
    if getattr(node, "show_apply", None):
        zone.set("show-apply", "true")

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
    _render_control_caption(node, zone)
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
    if not node.show_title:
        zone.set("show-title", "false")
    if node.mode:
        zone.set("leg-item-layout", node.mode)
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
