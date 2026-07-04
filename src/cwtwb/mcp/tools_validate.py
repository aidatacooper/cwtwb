"""MCP tools for workbook validation via Tableau Cloud upload."""

from __future__ import annotations

from pathlib import Path

from .app import server


@server.tool()
def upload_workbook(
    twb_path: str,
    data_path: str | None = None,
    name: str | None = None,
    overwrite: bool = True,
    env_path: str | None = None,
) -> dict:
    """Upload a .twb/.twbx to Tableau Cloud to validate it.

    Upload success means the workbook structure is valid and Tableau Cloud
    can parse it. Use this after saving a generated workbook to verify
    correctness.

    Args:
        twb_path: Path to .twb or .twbx file.
        data_path: Optional data file (.xlsx/.xls/.hyper) to package.
        name: Workbook name on Tableau Cloud (defaults to filename stem).
        overwrite: Whether to overwrite existing workbook with same name.
        env_path: Optional path to a .env file with Tableau credentials.

    Returns:
        {success, workbook_id, workbook_url, views, twbx_path, twbx_size_kb, error}
    """
    from ..validate.uploader import TableauUploader

    uploader = TableauUploader(env_path=env_path)
    result = uploader.upload(twb_path, data_path, name, overwrite)
    return {
        "success": result.success,
        "workbook_id": result.workbook_id,
        "workbook_url": result.workbook_url,
        "views": result.views,
        "twbx_path": result.twbx_path,
        "twbx_size_kb": round(result.twbx_size_kb, 1),
        "error": result.error,
    }


@server.tool()
def validate_workbook_api(
    twb_path: str,
    validation_level: str = "semantic",
    env_path: str | None = None,
) -> dict:
    """Validate a .twb file via Tableau Cloud REST API (no publish).

    This performs semantic validation that checks whether the workbook will
    actually open in Tableau — beyond what local XSD schema validation can
    detect (calculated field formulas, field references, data source
    connectivity, etc.). The file is NOT stored on the server.

    Only .twb files are supported. For .twbx files, use upload_workbook.

    Requires Tableau Cloud June 2026+ / Server 2026.2+ (API version 3.29+).

    Args:
        twb_path: Path to .twb file.
        validation_level: "syntactic" (XSD only) or "semantic" (full, default).
        env_path: Optional path to a .env file with Tableau credentials.

    Returns:
        {success, validation_level, valid, errors, warnings, error}
    """
    from ..validate.uploader import TableauUploader

    uploader = TableauUploader(env_path=env_path)
    result = uploader.validate(twb_path, validation_level)
    return {
        "success": result.success,
        "validation_level": result.validation_level,
        "valid": result.valid,
        "errors": result.errors,
        "warnings": result.warnings,
        "error": result.error,
    }


@server.tool()
def screenshot_workbook(
    workbook_id: str,
    output_dir: str = "output/validation",
    view_index: int = 0,
    view_name: str | None = None,
) -> dict:
    """Screenshot a published workbook's view for human review.

    Use after upload_workbook to capture a visual snapshot. The screenshot
    is saved locally for human inspection.

    Args:
        workbook_id: The workbook ID returned by upload_workbook.
        output_dir: Directory to save screenshot (default: output/validation).
        view_index: Index of the view to screenshot (default: 0).
        view_name: Name of the view to screenshot (overrides view_index).

    Returns:
        {success, path, view_name, view_id, size_kb, error}
    """
    from ..validate.uploader import TableauUploader

    uploader = TableauUploader()
    result = uploader.screenshot(workbook_id, output_dir, view_index, view_name)
    return {
        "success": result.success,
        "path": result.path,
        "view_name": result.view_name,
        "view_id": result.view_id,
        "size_kb": round(result.size_kb, 1),
        "error": result.error,
    }
