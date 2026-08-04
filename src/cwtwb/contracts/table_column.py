"""TableColumn dataclass for multi-column text table configuration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TableColumn:
    """Configuration for a single column in a multi-column text table.

    A column consists of a value pane (MIN(1) axis) and a header spacer pane (MIN(0) axis).

    Attrs:
        header: Display header title string for the column.
        bold_field: Field expression for bold text (e.g. highlighted condition).
        normal_field: Field expression for normal text.
        axis_field: Axis measure field expression for value pane (e.g. "MIN(1) A").
        spacer_field: Axis measure field expression for header spacer pane (e.g. "MIN(0) Sales").
        instance_kind: Column instance type ("qk", "ok", "nk").
        text_align: Alignment of text inside the cell ("left", "right", "center").
        vertical_align: Whether to vertically center text.
        spacer_color: Color hex string for spacer, or None for transparent.
        axis_index: Pane index string when reusing axis_field across multiple columns (e.g. "1").
        header_font: Optional font name for the column header axis title.
    """

    header: str
    bold_field: str
    normal_field: str
    axis_field: str
    spacer_field: str
    instance_kind: str = "qk"
    text_align: str = "left"
    vertical_align: bool = False
    spacer_color: Optional[str] = None
    axis_index: Optional[str] = None
    header_font: Optional[str] = None
