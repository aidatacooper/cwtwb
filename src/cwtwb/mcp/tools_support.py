"""Capability catalog and workbook analysis MCP tools.

These tools help an AI agent understand what cwtwb can and cannot do before
attempting to build or migrate a workbook.

TOOL INVENTORY
--------------
  list_capabilities()
      Return the full capability catalog from capability_registry.py as a
      formatted text table.  Shows every declared chart type, encoding, and
      feature with its support level (core / advanced / recipe / unsupported).
      This is a feature-support catalog, not a list of callable MCP tools.
      Tool discovery should come from the MCP tool list itself.

  describe_capability(kind, name)
      Return details for a single capability entry — level, description, and
      any caveats.  Use when the catalog shows something unexpected.

  analyze_twb(file_path)
      Parse an existing .twb file and report:
        - Which chart types and encodings it uses.
        - Which capabilities are core, advanced, recipe-level, or unsupported.
        - The full capability gap section (features used that cwtwb cannot yet
          reproduce automatically).
      Combines twb_analyzer.to_text() + to_gap_text() in one call.

  diff_template_gap(file_path)
      Return only the capability gap section (a subset of analyze_twb output).
      Useful when you already understand the workbook structure and just need
      to know what the SDK cannot handle.

  validate_workbook(file_path=None)
      Validate a saved .twb/.twbx file — or the current in-memory editor —
      against the official Tableau XSD schema (2026.1).  Failures are
      informational: Tableau Desktop is the true validator.

  inspect_excel_connection(file_path, sheet_name="")
      Preview how cwtwb will interpret an Excel workbook before mutating the
      active workbook.  Reports per-sheet fields, inferred datatypes, and any
      shared-field relationships that would trigger multi-table Excel support.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Optional

from ..authoring_contract import review_authoring_contract_payload
from ..capability_registry import format_capability_catalog, format_capability_detail
from ..connections import (
    _column_values_from_rows,
    _excel_grid_origin,
    _infer_external_field_type,
    _infer_external_role,
    _infer_excel_datatype,
    _list_excel_sheet_names,
    _read_excel_sheet_rows,
    _sanitize_headers,
    infer_tableau_semantic_role,
)
from ..twb_analyzer import analyze_workbook
from ..validator import TWBValidationError, load_workbook_root, validate_against_schema
from .app import server
from .state import get_editor


@server.tool()
def list_capabilities() -> str:
    """List cwtwb's declared capability boundary.

    This reports what workbook features/charts are supported by cwtwb. It does
    not enumerate callable MCP tools and should not be used to infer whether a
    tool like add_dashboard or save_workbook exists.
    """

    guardrails = [
        "Workflow guardrails:",
        "- This output is a capability catalog, not a list of callable MCP tools.",
        "- Recommended workbook flow: create_workbook/open_workbook -> list_fields -> add_worksheet/configure_chart -> add_dashboard -> save_workbook.",
        "- add_dashboard and save_workbook are default MCP tools. If they seem missing, refresh the MCP client session and uvx cache.",
        "- inspect_excel_connection is the read-only preview helper for multi-table Excel workbooks.",
    ]
    return "\n".join(guardrails) + "\n\n" + format_capability_catalog()


@server.tool()
def describe_capability(kind: str, name: str) -> str:
    """Describe one declared capability and its support tier."""

    return format_capability_detail(kind, name)


@server.tool()
def analyze_twb(file_path: str) -> str:
    """Analyze an existing TWB/TWBX file against cwtwb's declared capabilities.

    This tool requires a file_path that already exists on disk. It cannot
    analyze the active in-memory workbook directly and it does not save the
    current workbook. For a newly generated workbook, call save_workbook first,
    then pass that saved path to analyze_twb.
    """

    schema_note = (
        "Schema check: SKIPPED (analysis only). "
        "Important: analyze_twb reports capability fit, not loadability."
    )
    try:
        root = load_workbook_root(file_path)
        schema_result = validate_against_schema(root)
        if schema_result.valid:
            schema_note = "Schema check: PASS."
        else:
            schema_note = (
                f"Schema check: FAIL ({len(schema_result.errors)} error(s)). "
                "Important: capability analysis can still run on invalid workbooks."
            )
    except TWBValidationError as exc:
        schema_note = (
            "Schema check: FAIL (unable to parse workbook structure). "
            f"Details: {exc}"
        )

    report = analyze_workbook(file_path)
    return schema_note + "\n\n" + report.to_text() + "\n\n" + report.to_gap_text()


@server.tool()
def diff_template_gap(file_path: str) -> str:
    """Summarize the non-core capability gap of a TWB template."""

    report = analyze_workbook(file_path)
    return report.to_gap_text()


@server.tool()
def validate_workbook(file_path: Optional[str] = None) -> str:
    """Validate a workbook against the official Tableau TWB XSD schema (2026.1).

    Checks whether the generated XML conforms to Tableau's published schema.
    This tool does not save or export the active workbook. If file_path is
    omitted, it validates the current in-memory workbook before save; if
    file_path is provided, it validates an existing .twb/.twbx file on disk.
    Call save_workbook when you need to write the workbook to a file.

    Args:
        file_path: Path to a .twb or .twbx file to validate. If omitted,
                   validates the currently open workbook (in memory, before save).

    Returns:
        PASS/FAIL summary with error details.
    """
    from ..validator import TWBValidationError, load_workbook_root, validate_against_schema

    if file_path:
        from pathlib import Path

        p = Path(file_path)
        if not p.exists():
            return f"ERROR  File not found: {file_path}"

        try:
            root = load_workbook_root(p)
        except TWBValidationError as exc:
            return f"ERROR  {exc}"
        result = validate_against_schema(root)
    else:
        editor = get_editor()
        result = validate_against_schema(editor.root)

    result_text = result.to_text()
    if file_path:
        return result_text
    return (
        result_text
        + "\n\n"
        + "Note: validate_workbook only validates the in-memory workbook; it does not save files. "
        + "Use save_workbook(output_path=...) to write a .twb/.twbx file."
    )


@server.tool()
def inspect_excel_connection(file_path: str, sheet_name: str = "") -> str:
    """Preview how an Excel workbook will be interpreted before connection setup."""

    sheet_names = _list_excel_sheet_names(file_path)
    if not sheet_names:
        return json.dumps(
            {
                "file_path": file_path,
                "multi_table": False,
                "tables": [],
                "relationships": [],
                "note": "No readable sheets were found.",
            },
            ensure_ascii=False,
            indent=2,
        )

    ordered_sheet_names = sheet_names
    if sheet_name and sheet_name in sheet_names:
        ordered_sheet_names = [sheet_name] + [name for name in sheet_names if name != sheet_name]

    tables: list[dict] = []
    for index, candidate_sheet in enumerate(ordered_sheet_names):
        actual_sheet_name, rows = _read_excel_sheet_rows(file_path, sheet_name=candidate_sheet)
        if not rows:
            continue

        headers = _sanitize_headers(rows[0])
        value_rows = rows[1:]
        fields: list[dict] = []
        for ordinal, header in enumerate(headers):
            values = _column_values_from_rows(value_rows, ordinal)
            datatype = _infer_excel_datatype(header, values)
            role = _infer_external_role(header, datatype)
            fields.append(
                {
                    "name": header,
                    "ordinal": ordinal,
                    "datatype": datatype,
                    "role": role,
                    "field_type": _infer_external_field_type(role, datatype),
                    "semantic_role": infer_tableau_semantic_role(header),
                }
            )

        tables.append(
            {
                "name": actual_sheet_name,
                "grid_origin": _excel_grid_origin(rows),
                "outcome": "6" if len(rows) > 1 else "2",
                "row_count": max(len(rows) - 1, 0),
                "column_count": len(headers),
                "fields": fields,
            }
        )

    shared_name_counts = Counter(
        field["name"]
        for table in tables
        for field in table["fields"]
    )
    relationships: list[dict] = []
    if tables:
        primary = tables[0]
        primary_field_names = {field["name"] for field in primary["fields"]}
        for secondary in tables[1:]:
            shared_fields = [
                field["name"]
                for field in secondary["fields"]
                if field["name"] in primary_field_names and shared_name_counts[field["name"]] > 1
            ]
            if shared_fields:
                relationships.append(
                    {
                        "from_table": primary["name"],
                        "to_table": secondary["name"],
                        "shared_fields": shared_fields,
                    }
                )

    preview = {
        "file_path": file_path,
        "sheet_name_hint": sheet_name,
        "sheet_count": len(sheet_names),
        "multi_table": len(tables) > 1,
        "tables": tables,
        "relationships": relationships,
    }
    return json.dumps(preview, ensure_ascii=False, indent=2)


def review_authoring_contract(contract_json: str) -> str:
    """Review a draft authoring contract and apply profile-aware defaults."""

    return review_authoring_contract_payload(contract_json).to_json()
