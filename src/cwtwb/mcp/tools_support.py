"""Capability and template-analysis MCP tools."""

from __future__ import annotations

from ..capability_registry import format_capability_catalog, format_capability_detail
from ..twb_analyzer import analyze_workbook
from .app import server


@server.tool()
def list_capabilities() -> str:
    """List cwtwb's declared capability boundary."""

    return format_capability_catalog()


@server.tool()
def describe_capability(kind: str, name: str) -> str:
    """Describe one declared capability and its support tier."""

    return format_capability_detail(kind, name)


@server.tool()
def analyze_twb(file_path: str) -> str:
    """Analyze a TWB file against cwtwb's declared capabilities."""

    report = analyze_workbook(file_path)
    return report.to_text()


@server.tool()
def diff_template_gap(file_path: str) -> str:
    """Summarize the non-core capability gap of a TWB template."""

    report = analyze_workbook(file_path)
    return report.to_gap_text()
