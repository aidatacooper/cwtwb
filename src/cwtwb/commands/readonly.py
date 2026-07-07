from __future__ import annotations

from pathlib import Path
from typing import Any

from ..capability_registry import (
    format_capability_catalog,
    get_level_summary,
    list_capabilities,
)
from ..twb_analyzer import analyze_workbook
from ..validator import TWBValidationError, load_workbook_root, validate_against_schema
from .common import emit, fields_payload, open_editor, workbook_summary


def inspect_workbook(args: Any) -> int:
    editor = open_editor(args.workbook)
    payload = workbook_summary(editor, args.workbook)
    if args.json:
        emit(payload, as_json=True)
        return 0
    lines = [f"Workbook: {args.workbook}", ""]
    lines.append(
        "Fields: "
        f"{payload['field_counts']['dimensions']} dimensions, "
        f"{payload['field_counts']['measures']} measures"
    )
    lines.append("")
    lines.append("Worksheets:")
    lines.extend(f"  {name}" for name in payload["worksheets"] or ["(none)"])
    lines.append("")
    lines.append("Dashboards:")
    if payload["dashboards"]:
        for dashboard in payload["dashboards"]:
            worksheets = ", ".join(dashboard["worksheets"]) or "(no worksheet zones)"
            lines.append(f"  {dashboard['name']}: {worksheets}")
    else:
        lines.append("  (none)")
    emit("\n".join(lines))
    return 0


def fields(args: Any) -> int:
    editor = open_editor(args.workbook)
    payload = fields_payload(editor)
    if args.json:
        emit(payload, as_json=True)
    else:
        emit(editor.list_fields())
    return 0


def worksheets(args: Any) -> int:
    editor = open_editor(args.workbook)
    payload = {"worksheets": editor.list_worksheets()}
    if args.json:
        emit(payload, as_json=True)
    else:
        emit("\n".join(payload["worksheets"]) if payload["worksheets"] else "(none)")
    return 0


def dashboards(args: Any) -> int:
    editor = open_editor(args.workbook)
    payload = {"dashboards": editor.list_dashboards()}
    if args.json:
        emit(payload, as_json=True)
    else:
        if not payload["dashboards"]:
            emit("(none)")
        else:
            emit(
                "\n".join(
                    f"{dashboard['name']}: {', '.join(dashboard['worksheets']) or '(no worksheet zones)'}"
                    for dashboard in payload["dashboards"]
                )
            )
    return 0


def validate(args: Any) -> int:
    path = Path(args.workbook)
    try:
        root = load_workbook_root(path)
    except TWBValidationError as exc:
        payload = {"valid": False, "error": str(exc)}
        emit(payload if args.json else f"ERROR  {exc}", as_json=args.json)
        return 1
    result = validate_against_schema(root)
    payload = {
        "valid": result.valid,
        "schema_available": result.schema_available,
        "schema_version": result.schema_version,
        "errors": result.errors,
        "compatibility_warnings": result.compatibility_warnings,
    }
    emit(payload if args.json else result.to_text(), as_json=args.json)
    return 0 if result.valid or result.compatibility_only else 1


def analyze(args: Any) -> int:
    report = analyze_workbook(args.workbook)
    payload = {
        "file_path": report.file_path,
        "fit_level": report.fit_level,
        "summary": report.summary,
        "detected": [item.__dict__ for item in report.detected],
        "unknown": [item.__dict__ for item in report.unknown],
    }
    emit(payload if args.json else report.to_text() + "\n\n" + report.to_gap_text(), as_json=args.json)
    return 0


def capabilities(args: Any) -> int:
    items = list_capabilities(kind=args.kind, level=args.level)
    payload = {
        "summary": get_level_summary(),
        "capabilities": [
            {
                "key": item.key,
                "kind": item.kind,
                "level": item.level,
                "canonical": item.canonical,
                "aliases": list(item.aliases),
                "rationale": item.rationale,
                "notes": item.notes,
            }
            for item in items
        ],
    }
    if args.json:
        emit(payload, as_json=True)
    else:
        emit(format_capability_catalog(level_filter=args.level))
    return 0

