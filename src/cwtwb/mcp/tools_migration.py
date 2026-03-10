"""Migration-oriented MCP tools."""

from __future__ import annotations

from ..migration import (
    apply_twb_migration_json,
    inspect_target_schema as inspect_target_schema_impl,
    preview_twb_migration_json,
)
from .app import server


@server.tool()
def inspect_target_schema(target_source: str) -> str:
    """Inspect the first-sheet schema of a target Excel datasource."""

    import json

    return json.dumps(inspect_target_schema_impl(target_source), ensure_ascii=False, indent=2)


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
