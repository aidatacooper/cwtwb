"""Migration-oriented MCP tools — re-target an existing TWB onto a new datasource.

PURPOSE
-------
These tools allow an AI agent to take an existing Tableau workbook (built
against one datasource/Excel file) and reconnect it to a different datasource
without rebuilding from scratch.  All calculated fields, dashboard layouts,
and chart configurations are preserved; only field name references change.

FIVE-STEP WORKFLOW (must be followed in order)
----------------------------------------------
  Step 1 — inspect_target_schema(target_source)
      Read the column names and data types from the new Excel file.
      Returns a JSON object: {"fields": [...], "sample_values": {...}}.

  Step 2 — profile_twb_for_migration(file_path, target_source, scope)
      Scan the TWB to discover which datasource is used, which worksheets
      are in scope ("workbook" | "worksheet:Name"), and which fields appear.
      Returns a JSON profile summary.

  Step 3 — propose_field_mapping(file_path, target_source, mapping_overrides)
      Fuzzy-match source field names to target field names and return a
      ranked candidate list with confidence scores.
      Use mapping_overrides={source: target} to force specific mappings.

  Step 4 — preview_twb_migration(file_path, target_source, mapping_overrides)
      Dry-run the full migration: report blocking issues (fields that cannot
      be mapped), warnings (low-confidence matches), and the rewrite summary.
      Does NOT write any files.

  Step 5a — apply_twb_migration(file_path, target_source, output_path)
      Write the migrated TWB to output_path plus a JSON report.
      Only call this after reviewing the preview and confirming no blockers.

  Step 5b — migrate_twb_guided(file_path, target_source, output_path)
      Combined convenience wrapper: runs preview, pauses if warnings exist
      for agent confirmation, then applies if apply_if_no_blockers=True.

SCOPE PARAMETER
---------------
  "workbook"          — migrate all worksheets (default)
  "worksheet:Name"    — migrate only the named worksheet
"""

from __future__ import annotations

from ..migration import (
    apply_twb_migration_json,
    inspect_target_schema as inspect_target_schema_impl,
    migrate_twb_guided_json,
    profile_twb_for_migration_json,
    propose_field_mapping_json,
    preview_twb_migration_json,
)
from .app import server


@server.tool()
def inspect_target_schema(target_source: str) -> str:
    """Inspect the first-sheet schema of a target Excel datasource."""

    import json
    from pathlib import Path

    path = Path(target_source)
    suffix = path.suffix.lower()
    if suffix not in (".xls", ".xlsx", ".xlsm", ".xlsb"):
        return f"Unsupported file type '{suffix}'. Only Excel files (.xls, .xlsx, .xlsm, .xlsb) are supported."

    try:
        return json.dumps(inspect_target_schema_impl(target_source), ensure_ascii=False, indent=2)
    except Exception as exc:
        return f"Unsupported or unreadable file: {exc}"


@server.tool()
def profile_twb_for_migration(
    file_path: str,
    scope: str = "workbook",
    target_source: str = "",
) -> str:
    """Profile workbook datasources and worksheet scope before migration."""

    return profile_twb_for_migration_json(
        file_path=file_path,
        scope=scope,
        target_source=target_source or None,
    )


@server.tool()
def propose_field_mapping(
    file_path: str,
    target_source: str,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
) -> str:
    """Scan source and target schema and propose a field mapping."""

    return propose_field_mapping_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
    )


@server.tool()
def preview_twb_migration(
    file_path: str,
    target_source: str,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
) -> str:
    """Preview a workbook migration onto a target datasource."""

    return preview_twb_migration_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
    )


@server.tool()
def apply_twb_migration(
    file_path: str,
    target_source: str,
    output_path: str,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
) -> str:
    """Apply a workbook migration and write a migrated TWB plus reports."""

    return apply_twb_migration_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        output_path=output_path,
    )


def migrate_twb_guided(
    file_path: str,
    target_source: str,
    output_path: str = "",
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    apply_if_no_blockers: bool = True,
) -> str:
    """Run the built-in migration workflow and pause for warning confirmation when needed."""

    return migrate_twb_guided_json(
        file_path=file_path,
        target_source=target_source,
        output_path=output_path or None,
        scope=scope,
        mapping_overrides=mapping_overrides,
        apply_if_no_blockers=apply_if_no_blockers,
    )
