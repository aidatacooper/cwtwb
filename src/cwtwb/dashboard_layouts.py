"""Helpers for resolving and rendering dashboard layouts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lxml import etree

from .layout import generate_dashboard_zones

CONTAINER_TYPE_ALIASES = {
    "horizontal": "horizontal",
    "vertical": "vertical",
    "tiled": "vertical",
}

VALID_LAYOUT_NODE_TYPES = {
    "container",
    "worksheet",
    "text",
    "filter",
    "paramctrl",
    "color",
    "empty",
}


def resolve_dashboard_layout(
    layout: str | dict[str, Any],
    worksheet_names: list[str],
) -> dict[str, Any]:
    """Normalize simple layout shorthands and file-based layouts to a dict."""
    if isinstance(layout, dict):
        return normalize_dashboard_layout(layout)

    layout_path = Path(layout)
    if layout_path.exists() and layout_path.is_file():
        with open(layout_path, "r", encoding="utf-8") as f:
            loaded_json = json.load(f)
        if isinstance(loaded_json, dict) and "layout_schema" in loaded_json:
            return normalize_dashboard_layout(loaded_json["layout_schema"])
        if isinstance(loaded_json, dict):
            return normalize_dashboard_layout(loaded_json)
        raise ValueError("Dashboard layout JSON must contain an object layout tree.")

    if layout == "horizontal":
        return normalize_dashboard_layout({
            "type": "container",
            "direction": "horizontal",
            "layout_strategy": "distribute-evenly",
            "children": [{"type": "worksheet", "name": w} for w in worksheet_names],
        })

    if layout == "grid-2x2":
        row1_children = [{"type": "worksheet", "name": w} for w in worksheet_names[:2]]
        row2_children = [{"type": "worksheet", "name": w} for w in worksheet_names[2:4]]
        layout_dict: dict[str, Any] = {
            "type": "container",
            "direction": "vertical",
            "layout_strategy": "distribute-evenly",
            "children": [
                {
                    "type": "container",
                    "direction": "horizontal",
                    "layout_strategy": "distribute-evenly",
                    "children": row1_children,
                }
            ],
        }
        if row2_children:
            layout_dict["children"].append(
                {
                    "type": "container",
                    "direction": "horizontal",
                    "layout_strategy": "distribute-evenly",
                    "children": row2_children,
                }
            )
        return normalize_dashboard_layout(layout_dict)

    return normalize_dashboard_layout({
        "type": "container",
        "direction": "vertical",
        "layout_strategy": "distribute-evenly",
        "children": [{"type": "worksheet", "name": w} for w in worksheet_names],
    })


def normalize_dashboard_layout(node: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy layout aliases and validate the declarative tree."""
    if not isinstance(node, dict):
        raise ValueError("Dashboard layout nodes must be objects.")
    return _normalize_dashboard_layout_node(node, path="layout")


def _normalize_dashboard_layout_node(node: dict[str, Any], path: str) -> dict[str, Any]:
    node_type = str(node.get("type", "container")).strip() or "container"
    normalized = dict(node)

    if node_type in CONTAINER_TYPE_ALIASES:
        normalized["type"] = "container"
        normalized.setdefault("direction", CONTAINER_TYPE_ALIASES[node_type])
    elif node_type not in VALID_LAYOUT_NODE_TYPES:
        raise ValueError(
            f"Unsupported dashboard layout node type '{node_type}' at {path}. "
            f"Expected one of: {', '.join(sorted(VALID_LAYOUT_NODE_TYPES | set(CONTAINER_TYPE_ALIASES)))}."
        )
    else:
        normalized["type"] = node_type

    children = normalized.get("children")
    if children is None:
        normalized["children"] = []
        return normalized

    if not isinstance(children, list):
        raise ValueError(f"Dashboard layout node children must be a list at {path}.")

    normalized["children"] = [
        _normalize_dashboard_layout_node(child, f"{path}.children[{index}]")
        for index, child in enumerate(children)
    ]
    return normalized


def extract_layout_worksheets(node: dict[str, Any]) -> list[str]:
    """Collect worksheet names referenced in a declarative layout tree."""
    sheets: list[str] = []
    if node.get("type") == "worksheet":
        name = node.get("name")
        if name:
            sheets.append(name)
    for child in node.get("children", []):
        sheets.extend(extract_layout_worksheets(child))
    return sheets

def extract_layout_options(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Collect worksheet names and their options referenced in a layout tree."""
    sheets: dict[str, dict[str, Any]] = {}
    if node.get("type") == "worksheet":
        name = node.get("name")
        if name:
            options = {}
            if "fit" in node:
                options["fit"] = node["fit"]
            sheets[name] = options
            
    for child in node.get("children", []):
        sheets.update(extract_layout_options(child))
    return sheets


def validate_layout_worksheets(layout_dict: dict[str, Any]) -> list[str]:
    """Ensure every worksheet appears at most once in a dashboard layout."""
    used_sheets = extract_layout_worksheets(layout_dict)
    seen_sheets: set[str] = set()
    for sheet in used_sheets:
        if sheet in seen_sheets:
            raise ValueError(
                "A worksheet can only be used once per dashboard. "
                f"Found duplicate: '{sheet}'. Please add and configure a duplicate worksheet instead."
            )
        seen_sheets.add(sheet)
    return used_sheets


def render_dashboard_layout(
    parent_zones_el: etree._Element,
    layout_dict: dict[str, Any],
    width: int,
    height: int,
    get_id_fn,
    *,
    field_registry,
    parameters,
    editor,
) -> None:
    """Render a normalized layout dict into the dashboard's <zones> tree."""
    context = {
        "field_registry": field_registry,
        "parameters": parameters,
        "editor": editor,
    }
    generate_dashboard_zones(parent_zones_el, layout_dict, width, height, get_id_fn, context)
