"""Declarative dashboard layout tree model and coordinate computation."""

from __future__ import annotations

from typing import Any, Callable, Optional


class FlexNode:
    """A node in the declarative dashboard layout tree."""

    def __init__(self, d: dict[str, Any]):
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
        self.layout_strategy = d.get("layout_strategy")

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
        from .layout_rendering import render_flex_node

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
