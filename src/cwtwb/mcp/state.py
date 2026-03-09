"""Mutable workbook state for the MCP server."""

from __future__ import annotations

from typing import Optional

from ..twb_editor import TWBEditor

_editor: Optional[TWBEditor] = None


def get_editor() -> TWBEditor:
    """Get the current editor instance, raising if none exists."""

    if _editor is None:
        raise RuntimeError("No active workbook. Call create_workbook first.")
    return _editor


def set_editor(editor: TWBEditor) -> None:
    """Replace the current editor instance."""

    global _editor
    _editor = editor
