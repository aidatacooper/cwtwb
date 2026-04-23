"""Layout helper MCP tools — dashboard layout JSON generation.

The add_dashboard tool accepts either a simple string ("vertical", "horizontal")
or a path to a layout JSON file for complex multi-zone dashboards.

This module provides the tool for generating that JSON file:

  generate_layout_json(output_path, layout_tree, ascii_preview)
      Saves a dashboard layout definition to a JSON file that can then be
      passed as the `layout` parameter to add_dashboard().

LAYOUT JSON STRUCTURE
---------------------
  {
    "_ascii_layout_preview": ["line 1", "line 2", ...],   // human-readable preview
    "layout_schema": {                                     // the actual layout tree
      "type": "container",
      "direction": "vertical" | "horizontal",
      "children": [
        {"type": "worksheet", "name": "Sheet1", "fixed_size": 400},
        {"type": "container", "direction": "horizontal", "children": [...]}
      ]
    }
  }

Legacy container aliases are accepted and normalized recursively:
  {"type": "horizontal", "children": [...]} -> {"type": "container", "direction": "horizontal", ...}
  {"type": "vertical", "children": [...]}   -> {"type": "container", "direction": "vertical", ...}

The ascii_preview field is stored for documentation only; add_dashboard ignores it.
The layout_schema tree is parsed by dashboard_layouts.resolve_dashboard_layout()
to produce Tableau's <zone> XML elements inside the <dashboard> element.

TYPICAL WORKFLOW
----------------
  1. Design the layout in your head / with the user → produce an ASCII sketch.
  2. Call generate_layout_json() to persist it.
  3. Call add_dashboard(layout="/path/to/layout.json") to apply it.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..dashboard_layouts import normalize_dashboard_layout
from .app import server


@server.tool()
def generate_layout_json(
    output_path: str,
    layout_tree: dict,
    ascii_preview: str,
) -> str:
    """Generate and save a dashboard layout JSON file."""

    try:
        if not isinstance(layout_tree, dict):
            return "Failed to generate layout JSON: layout_tree must be an object."

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        output_data = {}
        if ascii_preview:
            output_data["_ascii_layout_preview"] = ascii_preview.strip().split("\n")

        # Validate and canonicalize to the exact declarative DSL expected by
        # add_dashboard(layout=...).
        output_data["layout_schema"] = normalize_dashboard_layout(layout_tree)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        return (
            f"Layout JSON successfully written to: {path.absolute()}\n"
            f"You can now call `add_dashboard` and set the `layout` parameter to exactly this file path."
        )
    except ValueError as e:
        return (
            "Failed to generate layout JSON: layout_tree is not a supported add_dashboard layout DSL. "
            f"{str(e)}"
        )
    except Exception as e:
        return f"Failed to generate layout JSON: {str(e)}"
