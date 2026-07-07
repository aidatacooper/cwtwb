from __future__ import annotations

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

import yaml

from ..twb_editor import TWBEditor


def add_json_flag(parser: ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")


def emit(payload: Any, *, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if isinstance(payload, str):
        print(payload)
        return
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def load_data_file(path: str | Path) -> Any:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        if source.suffix.lower() in {".yaml", ".yml"}:
            return yaml.safe_load(handle)
        return json.load(handle)


def parse_mapping_pairs(values: list[str] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Expected KEY=VALUE mapping, got: {value}")
        key, mapped = value.split("=", 1)
        mapping[key.strip()] = mapped.strip()
    return mapping


def parse_json_object(value: str | None, *, option_name: str) -> dict[str, Any] | None:
    if not value:
        return None
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError(f"{option_name} must be a JSON object.")
    return loaded


def parse_json_list(value: str | None, *, option_name: str) -> list[Any] | None:
    if not value:
        return None
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError(f"{option_name} must be a JSON array.")
    return loaded


def ensure_output_allowed(output_path: str | Path, *, force: bool = False) -> Path:
    path = Path(output_path)
    if path.exists() and not force:
        raise FileExistsError(f"Output already exists: {path}. Use --force to overwrite.")
    return path


def resolve_output(
    input_path: str | Path,
    *,
    output_path: str | None,
    in_place: bool = False,
    force: bool = False,
) -> Path:
    if in_place:
        return Path(input_path)
    if not output_path:
        raise ValueError("Writing commands require --out unless --in-place is set.")
    return ensure_output_allowed(output_path, force=force)


def open_editor(path: str | Path) -> TWBEditor:
    return TWBEditor.open_existing(path)


def new_editor(template_path: str = "") -> TWBEditor:
    return TWBEditor(template_path)


def workbook_summary(editor: TWBEditor, file_path: str | Path | None = None) -> dict[str, Any]:
    fields = list(editor.field_registry._fields.values())
    dimensions = [field.display_name for field in fields if field.role == "dimension"]
    measures = [field.display_name for field in fields if field.role == "measure"]
    return {
        "file_path": str(file_path) if file_path is not None else None,
        "worksheets": editor.list_worksheets(),
        "dashboards": editor.list_dashboards(),
        "field_counts": {
            "dimensions": len(dimensions),
            "measures": len(measures),
            "total": len(fields),
        },
        "dimensions": sorted(dimensions),
        "measures": sorted(measures),
    }


def fields_payload(editor: TWBEditor) -> dict[str, Any]:
    fields = sorted(
        editor.field_registry._fields.values(),
        key=lambda field: (field.role, field.display_name),
    )
    return {
        "dimensions": [
            {
                "name": field.display_name,
                "datatype": field.datatype,
                "calculated": field.is_calculated,
            }
            for field in fields
            if field.role == "dimension"
        ],
        "measures": [
            {
                "name": field.display_name,
                "datatype": field.datatype,
                "calculated": field.is_calculated,
            }
            for field in fields
            if field.role == "measure"
        ],
    }

