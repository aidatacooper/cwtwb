"""Migration-oriented MCP tools."""

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

    return json.dumps(inspect_target_schema_impl(target_source), ensure_ascii=False, indent=2)


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
    use_ai_for_warnings: bool = True,
) -> str:
    """Scan source and target schema and propose a field mapping."""

    return propose_field_mapping_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        use_ai_for_warnings=use_ai_for_warnings,
    )


@server.tool()
def preview_twb_migration(
    file_path: str,
    target_source: str,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    use_ai_for_warnings: bool = True,
) -> str:
    """Preview a workbook migration onto a target datasource."""

    return preview_twb_migration_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        use_ai_for_warnings=use_ai_for_warnings,
    )


@server.tool()
def apply_twb_migration(
    file_path: str,
    target_source: str,
    output_path: str,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    use_ai_for_warnings: bool = True,
) -> str:
    """Apply a workbook migration and write a migrated TWB plus reports."""

    return apply_twb_migration_json(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        output_path=output_path,
        use_ai_for_warnings=use_ai_for_warnings,
    )


@server.tool()
def migrate_twb_guided(
    file_path: str,
    target_source: str,
    output_path: str = "",
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    apply_if_no_blockers: bool = True,
    use_ai_for_warnings: bool = True,
) -> str:
    """Run the built-in migration workflow: profile, map, preview, and optionally apply."""

    return migrate_twb_guided_json(
        file_path=file_path,
        target_source=target_source,
        output_path=output_path or None,
        scope=scope,
        mapping_overrides=mapping_overrides,
        apply_if_no_blockers=apply_if_no_blockers,
        use_ai_for_warnings=use_ai_for_warnings,
    )
