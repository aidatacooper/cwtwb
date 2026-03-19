"""Capability and template-analysis MCP tools."""

from __future__ import annotations

from typing import Optional

from ..capability_registry import format_capability_catalog, format_capability_detail
from ..twb_analyzer import analyze_workbook
from .app import server
from .state import get_editor


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


@server.tool()
def validate_workbook(file_path: Optional[str] = None) -> str:
    """Validate a workbook against the official Tableau TWB XSD schema (2026.1).

    Checks whether the generated XML conforms to Tableau's published schema.
    Errors are informational — Tableau itself occasionally produces workbooks
    that deviate slightly from the schema — but recurring errors indicate
    structural problems worth fixing.

    Args:
        file_path: Path to a .twb or .twbx file to validate. If omitted,
                   validates the currently open workbook (in memory, before save).

    Returns:
        PASS/FAIL summary with error details.
    """
    from ..validator import validate_against_schema

    if file_path:
        import io
        import zipfile
        from pathlib import Path
        from lxml import etree

        p = Path(file_path)
        if not p.exists():
            return f"ERROR  File not found: {file_path}"

        parser = etree.XMLParser(remove_blank_text=False)
        if p.suffix.lower() == ".twbx":
            with zipfile.ZipFile(p) as zf:
                twb_names = [n for n in zf.namelist() if n.lower().endswith(".twb")]
                if not twb_names:
                    return f"ERROR  No .twb found inside {file_path}"
                tree = etree.parse(io.BytesIO(zf.read(twb_names[0])), parser)
        else:
            tree = etree.parse(str(p), parser)

        result = validate_against_schema(tree.getroot())
    else:
        editor = get_editor()
        result = validate_against_schema(editor.root)

    return result.to_text()
