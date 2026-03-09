"""Layout-related MCP tools."""

from __future__ import annotations

import json
from pathlib import Path

from .app import server


@server.tool()
def generate_layout_json(
    output_path: str,
    layout_tree: dict,
    ascii_preview: str,
) -> str:
    """Generate and save a dashboard layout JSON file."""

    try:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        output_data = {}
        if ascii_preview:
            output_data["_ascii_layout_preview"] = ascii_preview.strip().split("\n")

        output_data["layout_schema"] = layout_tree

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        return (
            f"Layout JSON successfully written to: {path.absolute()}\n"
            f"You can now call `add_dashboard` and set the `layout` parameter to exactly this file path."
        )
    except Exception as e:
        return f"Failed to generate layout JSON: {str(e)}"
