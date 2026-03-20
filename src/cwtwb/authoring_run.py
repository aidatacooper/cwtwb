"""Run-based guided authoring helpers for the MCP dashboard workflow."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any

import xlrd

from .authoring_contract import review_authoring_contract_payload, suggest_profile_matches
from .config import DEFAULT_AUTHORING_RUNS_DIR
from .connections import inspect_hyper_schema

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None

RUN_INDEX_NAME = "index.json"
MANIFEST_NAME = "manifest.json"
APPROVALS_NAME = "approvals.json"

SCHEMA_STAGE = "schema"
ANALYSIS_STAGE = "analysis"
CONTRACT_STAGE = "contract"
WIREFRAME_STAGE = "wireframe"
EXECUTION_STAGE = "execution_plan"
CONFIRMABLE_STAGES = {
    SCHEMA_STAGE,
    ANALYSIS_STAGE,
    CONTRACT_STAGE,
    WIREFRAME_STAGE,
    EXECUTION_STAGE,
}

STATUS_INITIALIZED = "initialized"
STATUS_SCHEMA_INTAKED = "schema_intaked"
STATUS_SCHEMA_CONFIRMED = "schema_confirmed"
STATUS_ANALYSIS_BUILT = "analysis_built"
STATUS_ANALYSIS_FINALIZED = "analysis_finalized"
STATUS_ANALYSIS_CONFIRMED = "analysis_confirmed"
STATUS_CONTRACT_DRAFTED = "contract_drafted"
STATUS_CONTRACT_REVIEWED = "contract_reviewed"
STATUS_CONTRACT_FINALIZED = "contract_finalized"
STATUS_CONTRACT_CONFIRMED = "contract_confirmed"
STATUS_WIREFRAME_BUILT = "wireframe_built"
STATUS_WIREFRAME_FINALIZED = "wireframe_finalized"
STATUS_WIREFRAME_CONFIRMED = "wireframe_confirmed"
STATUS_EXECUTION_PLANNED = "execution_planned"
STATUS_EXECUTION_CONFIRMED = "execution_confirmed"
STATUS_GENERATION_STARTED = "workbook_generation_started"
STATUS_GENERATION_FAILED = "workbook_generation_failed"
STATUS_GENERATED = "workbook_generated"
STATUS_VALIDATED = "validated"
STATUS_ANALYZED = "analyzed"

SUPPORTED_EXCEL_SUFFIXES = {".xls", ".xlsx", ".xlsm"}
SUPPORTED_DATASOURCE_SUFFIXES = SUPPORTED_EXCEL_SUFFIXES | {".hyper"}

ARTIFACT_SCHEMA = "schema_summary"
ARTIFACT_ANALYSIS_BRIEF = "analysis_brief"
ARTIFACT_CONTRACT_DRAFT = "contract_draft"
ARTIFACT_CONTRACT_REVIEW = "contract_review"
ARTIFACT_CONTRACT_FINAL = "contract_final"
ARTIFACT_WIREFRAME = "wireframe"
ARTIFACT_EXECUTION_PLAN = "execution_plan"
ARTIFACT_VALIDATION = "validation_report"
ARTIFACT_ANALYSIS = "analysis_report"

ARTIFACT_KEYS = (
    ARTIFACT_SCHEMA,
    ARTIFACT_ANALYSIS_BRIEF,
    ARTIFACT_CONTRACT_DRAFT,
    ARTIFACT_CONTRACT_REVIEW,
    ARTIFACT_CONTRACT_FINAL,
    ARTIFACT_WIREFRAME,
    ARTIFACT_EXECUTION_PLAN,
    ARTIFACT_VALIDATION,
    ARTIFACT_ANALYSIS,
)

EXECUTION_STEP_WHITELIST = (
    "create_workbook",
    "open_workbook",
    "add_calculated_field",
    "add_parameter",
    "add_worksheet",
    "configure_chart",
    "configure_dual_axis",
    "configure_chart_recipe",
    "configure_worksheet_style",
    "add_dashboard",
    "add_dashboard_action",
    "set_worksheet_caption",
    "set_excel_connection",
    "set_mysql_connection",
    "set_tableauserver_connection",
    "set_hyper_connection",
)

POST_CHECK_WHITELIST = ("validate_workbook", "analyze_twb")


def _now() -> datetime:
    return datetime.now()


def _now_token() -> str:
    return _now().strftime("%Y%m%d-%H%M%S-%f")


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).expanduser().resolve())


def _detect_datasource_type(datasource_path: str | Path) -> str:
    suffix = Path(datasource_path).suffix.lower()
    if suffix in SUPPORTED_EXCEL_SUFFIXES:
        return "excel"
    if suffix == ".hyper":
        return "hyper"
    raise ValueError(
        f"Unsupported datasource type '{suffix}'. Supported: "
        f"{', '.join(sorted(SUPPORTED_DATASOURCE_SUFFIXES))}"
    )


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _index_path(root_dir: Path) -> Path:
    return root_dir / RUN_INDEX_NAME


def _new_artifact_state() -> dict[str, Any]:
    return {
        "current": "",
        "versions": [],
        "review_current": "",
        "review_versions": [],
    }


def _default_manifest(
    output_root: Path,
    run_dir: Path,
    run_id: str,
    datasource_path: str,
    datasource_type: str,
) -> dict[str, Any]:
    now = _now_iso()
    return {
        "run_id": run_id,
        "output_root": str(output_root),
        "run_dir": str(run_dir),
        "datasource_path": datasource_path,
        "datasource_type": datasource_type,
        "status": STATUS_INITIALIZED,
        "created_at": now,
        "updated_at": now,
        "selected_primary_object": "",
        "artifacts": {key: _new_artifact_state() for key in ARTIFACT_KEYS},
        "final_workbook": "",
        "approvals_file": APPROVALS_NAME,
        "last_error": {},
    }


def _empty_approvals() -> dict[str, Any]:
    return {"events": []}


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load_index(root_dir: Path) -> dict[str, Any]:
    index_path = _index_path(root_dir)
    if not index_path.exists():
        return {"runs": {}}
    return _read_json(index_path)


def _save_index(root_dir: Path, index_payload: dict[str, Any]) -> None:
    _write_json(_index_path(root_dir), index_payload)


def _update_index_entry(manifest: dict[str, Any]) -> None:
    entry = {
        "run_dir": manifest["run_dir"],
        "datasource_path": manifest["datasource_path"],
        "status": manifest["status"],
        "created_at": manifest["created_at"],
        "updated_at": manifest["updated_at"],
    }
    for root_dir in {Path(manifest["output_root"]), DEFAULT_AUTHORING_RUNS_DIR}:
        index_payload = _load_index(root_dir)
        runs = index_payload.setdefault("runs", {})
        runs[manifest["run_id"]] = entry
        _save_index(root_dir, index_payload)


def _artifact_entry(manifest: dict[str, Any], artifact_key: str) -> dict[str, Any]:
    entry = manifest.setdefault("artifacts", {}).setdefault(
        artifact_key,
        _new_artifact_state(),
    )
    entry.setdefault("current", "")
    entry.setdefault("versions", [])
    entry.setdefault("review_current", "")
    entry.setdefault("review_versions", [])
    return entry


def _write_versioned_artifact(
    manifest: dict[str, Any],
    artifact_key: str,
    payload: dict[str, Any],
    *,
    markdown_content: str | None = None,
) -> Path:
    run_dir = Path(manifest["run_dir"])
    token = _now_token()
    filename = f"{artifact_key}.{token}.json"
    path = run_dir / filename
    _write_json(path, payload)
    entry = _artifact_entry(manifest, artifact_key)
    entry["current"] = filename
    versions = entry.setdefault("versions", [])
    versions.append(filename)
    if markdown_content is not None:
        review_filename = f"{artifact_key}.{token}.md"
        _write_text(run_dir / review_filename, markdown_content)
        entry["review_current"] = review_filename
        review_versions = entry.setdefault("review_versions", [])
        review_versions.append(review_filename)
    return path


def _current_artifact_path(manifest: dict[str, Any], artifact_key: str) -> Path:
    current = _artifact_entry(manifest, artifact_key).get("current", "")
    if not current:
        raise ValueError(
            f"No current artifact for '{artifact_key}' in run '{manifest['run_id']}'."
        )
    path = Path(manifest["run_dir"]) / current
    if not path.exists():
        raise FileNotFoundError(f"Expected artifact missing: {path}")
    return path


def _load_current_artifact(manifest: dict[str, Any], artifact_key: str) -> dict[str, Any]:
    return _read_json(_current_artifact_path(manifest, artifact_key))


def _current_review_artifact_path(manifest: dict[str, Any], artifact_key: str) -> Path:
    current = _artifact_entry(manifest, artifact_key).get("review_current", "")
    if not current:
        raise ValueError(
            f"No current review artifact for '{artifact_key}' in run '{manifest['run_id']}'."
        )
    path = Path(manifest["run_dir"]) / current
    if not path.exists():
        raise FileNotFoundError(f"Expected review artifact missing: {path}")
    return path


def _load_approvals(manifest: dict[str, Any]) -> dict[str, Any]:
    approvals_path = Path(manifest["run_dir"]) / APPROVALS_NAME
    if not approvals_path.exists():
        approvals = _empty_approvals()
        _write_json(approvals_path, approvals)
        return approvals
    return _read_json(approvals_path)


def _save_approvals(manifest: dict[str, Any], payload: dict[str, Any]) -> None:
    approvals_path = Path(manifest["run_dir"]) / APPROVALS_NAME
    _write_json(approvals_path, payload)


def _update_manifest(
    manifest: dict[str, Any],
    *,
    status: str | None = None,
    last_error: dict[str, Any] | None = None,
) -> None:
    if status is not None:
        manifest["status"] = status
    if last_error is not None:
        manifest["last_error"] = last_error
    manifest["updated_at"] = _now_iso()
    manifest_path = Path(manifest["run_dir"]) / MANIFEST_NAME
    _write_json(manifest_path, manifest)
    _update_index_entry(manifest)


def _load_manifest_by_id(run_id: str) -> dict[str, Any]:
    default_path = DEFAULT_AUTHORING_RUNS_DIR / run_id / MANIFEST_NAME
    if default_path.exists():
        return _read_json(default_path)

    root_dir = DEFAULT_AUTHORING_RUNS_DIR
    index_payload = _load_index(root_dir)
    candidate = index_payload.get("runs", {}).get(run_id, {}).get("run_dir", "")
    if candidate:
        manifest_path = Path(candidate) / MANIFEST_NAME
        if manifest_path.exists():
            return _read_json(manifest_path)

    if root_dir.exists():
        for manifest_path in root_dir.rglob(MANIFEST_NAME):
            manifest = _read_json(manifest_path)
            if manifest.get("run_id") == run_id:
                return manifest

    raise FileNotFoundError(f"Authoring run '{run_id}' not found.")


def _require_status(manifest: dict[str, Any], allowed: tuple[str, ...], action: str) -> None:
    if manifest["status"] not in allowed:
        raise RuntimeError(
            f"Cannot {action} while run '{manifest['run_id']}' is in status "
            f"'{manifest['status']}'. Allowed: {', '.join(allowed)}"
        )


def _sanitize_header(value: Any, index: int, seen: dict[str, int], notes: list[str]) -> str:
    base = str(value).strip()
    if not base:
        base = f"Column_{index + 1}"
        notes.append(f"Column {index + 1} had no header; renamed to '{base}'.")
    count = seen.get(base, 0) + 1
    seen[base] = count
    if count > 1:
        renamed = f"{base}__dup{count}"
        notes.append(f"Duplicate header '{base}' detected; renamed to '{renamed}'.")
        return renamed
    return base


def _sample_rows_from_xls(path: Path) -> list[dict[str, Any]]:
    workbook = xlrd.open_workbook(str(path))
    sheets: list[dict[str, Any]] = []
    for sheet in workbook.sheets():
        rows = [
            sheet.row_values(row_index)
            for row_index in range(min(sheet.nrows, 151))
        ]
        sheets.append({"name": sheet.name, "rows": rows})
    return sheets


def _sample_rows_from_openpyxl(path: Path) -> list[dict[str, Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise RuntimeError(
            "Reading .xlsx/.xlsm files requires openpyxl to be installed."
        ) from exc

    workbook = load_workbook(str(path), read_only=True, data_only=True)
    sheets: list[dict[str, Any]] = []
    for worksheet in workbook.worksheets:
        rows = []
        for row in worksheet.iter_rows(min_row=1, max_row=151, values_only=True):
            rows.append(list(row))
        sheets.append({"name": worksheet.title, "rows": rows})
    workbook.close()
    return sheets


def _infer_column_type(header: str, values: list[Any]) -> str:
    lower = header.casefold()
    non_blank = [value for value in values if value not in ("", None)]
    if any(token in lower for token in ("date", "month", "year", "day", "time")):
        return "date"
    if any(token in lower for token in ("latitude", "longitude", "lat", "lon")):
        return "real"
    if not non_blank:
        return "string"
    if any(isinstance(value, (datetime, date)) for value in non_blank):
        return "date"
    if all(isinstance(value, bool) for value in non_blank):
        return "boolean"
    numeric_values: list[float] = []
    all_numeric = True
    for value in non_blank:
        if isinstance(value, bool):
            all_numeric = False
            break
        if isinstance(value, (int, float)):
            numeric_values.append(float(value))
            continue
        try:
            numeric_values.append(float(str(value).strip()))
        except Exception:
            all_numeric = False
            break
    if all_numeric and numeric_values:
        if all(float(v).is_integer() for v in numeric_values):
            return "integer"
        return "real"
    return "string"


def _infer_role(field_name: str, datatype: str) -> str:
    lower = field_name.casefold()
    if datatype in {"integer", "real"} and not any(
        token in lower for token in ("id", "code", "zip", "postal")
    ):
        return "measure"
    return "dimension"


def _infer_field_type(role: str, datatype: str) -> str:
    if datatype == "date":
        return "ordinal"
    if role == "measure":
        return "quantitative"
    return "nominal"


def _is_geo_field(field_name: str) -> bool:
    normalized = " ".join(field_name.casefold().replace("_", " ").replace("-", " ").split())
    return normalized in {
        "country",
        "region",
        "state",
        "province",
        "state/province",
        "city",
        "postal code",
        "zip code",
        "zipcode",
        "latitude",
        "longitude",
        "lat",
        "lon",
    }


def _build_field_payloads(source_object: str, rows: list[list[Any]], notes: list[str]) -> list[dict[str, Any]]:
    if not rows:
        notes.append(f"'{source_object}' had no rows to inspect.")
        return []
    header_row = rows[0]
    seen: dict[str, int] = {}
    headers = [
        _sanitize_header(value, index, seen, notes)
        for index, value in enumerate(header_row)
    ]
    value_rows = rows[1:]
    fields: list[dict[str, Any]] = []
    for index, header in enumerate(headers):
        values = [row[index] if index < len(row) else None for row in value_rows]
        datatype = _infer_column_type(header, values)
        role = _infer_role(header, datatype)
        field_type = _infer_field_type(role, datatype)
        fields.append(
            {
                "name": header,
                "source_object": source_object,
                "inferred_type": datatype,
                "role": role,
                "field_type": field_type,
                "semantic_role": "geographic" if _is_geo_field(header) else "",
            }
        )
    return fields


def _collect_field_candidates(fields: list[dict[str, Any]]) -> dict[str, list[str]]:
    dimensions: list[str] = []
    measures: list[str] = []
    date_fields: list[str] = []
    geo_fields: list[str] = []
    for field in fields:
        name = field["name"]
        datatype = field["inferred_type"]
        role = field["role"]
        if role == "measure":
            measures.append(name)
        else:
            dimensions.append(name)
        if datatype == "date":
            date_fields.append(name)
        if field.get("semantic_role") == "geographic":
            geo_fields.append(name)
    return {
        "dimensions": dimensions,
        "measures": measures,
        "date_fields": date_fields,
        "geo_fields": geo_fields,
    }


def _build_excel_schema_summary(path: Path, preferred_sheet: str = "") -> dict[str, Any]:
    notes: list[str] = []
    if path.suffix.lower() == ".xls":
        sheet_payloads = _sample_rows_from_xls(path)
    else:
        sheet_payloads = _sample_rows_from_openpyxl(path)

    if not sheet_payloads:
        raise ValueError(f"No worksheets found in Excel file: {path}")

    sheets: list[dict[str, Any]] = []
    selected_sheet = ""
    if preferred_sheet:
        if any(payload["name"] == preferred_sheet for payload in sheet_payloads):
            selected_sheet = preferred_sheet
        else:
            notes.append(
                f"Preferred sheet '{preferred_sheet}' was not found. Review available sheets before confirming schema."
            )
    if not selected_sheet and len(sheet_payloads) == 1:
        selected_sheet = sheet_payloads[0]["name"]

    selected_fields: list[dict[str, Any]] = []
    for payload in sheet_payloads:
        sheet_notes: list[str] = []
        fields = _build_field_payloads(payload["name"], payload["rows"], sheet_notes)
        sheets.append(
            {
                "name": payload["name"],
                "row_count": max(len(payload["rows"]) - 1, 0),
                "fields": fields,
                "notes": sheet_notes,
            }
        )
        notes.extend(sheet_notes)
        if payload["name"] == selected_sheet:
            selected_fields = fields

    if not selected_sheet:
        selected_fields = sheets[0]["fields"]
        if len(sheets) > 1:
            notes.append(
                "Multiple Excel sheets were discovered. Re-run intake_datasource_schema with preferred_sheet before confirming schema."
            )
        else:
            selected_sheet = sheets[0]["name"]

    field_candidates = _collect_field_candidates(selected_fields)
    profile_matches = suggest_profile_matches(
        available_fields=[field["name"] for field in selected_fields]
    )
    return {
        "datasource": {
            "path": _normalize_path(path),
            "type": "excel",
        },
        "sheets": sheets,
        "selected_primary_object": selected_sheet,
        "fields": selected_fields,
        "field_candidates": field_candidates,
        "recommended_profile_matches": profile_matches,
        "notes": notes,
    }


def _build_hyper_schema_summary(path: Path) -> dict[str, Any]:
    notes: list[str] = []
    schema = inspect_hyper_schema(str(path))
    tables = schema.get("tables", [])
    if not tables:
        raise ValueError(f"No tables found in Hyper file: {path}")

    selected_table = tables[0]["name"]
    if len(tables) > 1:
        notes.append(
            "Multiple Hyper tables were discovered. V1 treats the first table as primary and does not plan joins automatically."
        )

    table_payloads: list[dict[str, Any]] = []
    selected_fields: list[dict[str, Any]] = []
    for table in tables:
        fields: list[dict[str, Any]] = []
        for column in table.get("columns", []):
            datatype = str(column.get("type", "string")).strip().casefold()
            if "date" in datatype or "timestamp" in datatype:
                inferred = "date"
            elif any(token in datatype for token in ("double", "numeric", "real", "float", "decimal")):
                inferred = "real"
            elif any(token in datatype for token in ("int", "bigint", "smallint")):
                inferred = "integer"
            elif "bool" in datatype:
                inferred = "boolean"
            else:
                inferred = "string"
            name = str(column.get("name", "")).strip()
            role = _infer_role(name, inferred)
            fields.append(
                {
                    "name": name,
                    "source_object": table["name"],
                    "inferred_type": inferred,
                    "role": role,
                    "field_type": _infer_field_type(role, inferred),
                    "semantic_role": "geographic" if _is_geo_field(name) else "",
                }
            )
        table_payloads.append(
            {
                "schema": table.get("schema", ""),
                "name": table["name"],
                "fields": fields,
                "notes": [],
            }
        )
        if table["name"] == selected_table:
            selected_fields = fields

    field_candidates = _collect_field_candidates(selected_fields)
    profile_matches = suggest_profile_matches(
        available_fields=[field["name"] for field in selected_fields]
    )
    return {
        "datasource": {
            "path": _normalize_path(path),
            "type": "hyper",
        },
        "tables": table_payloads,
        "selected_primary_object": selected_table,
        "fields": selected_fields,
        "field_candidates": field_candidates,
        "recommended_profile_matches": profile_matches,
        "notes": notes,
    }


def _extract_audience(brief: str) -> str:
    lines = [line.strip(" -\t") for line in brief.splitlines() if line.strip()]
    for line in lines:
        lower = line.casefold()
        if lower.startswith("audience:") or lower.startswith("audience -"):
            return line.split(":", 1)[1].strip() if ":" in line else line.split("-", 1)[1].strip()
        if lower.startswith("受众：") or lower.startswith("受众:"):
            return line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()
    for line in lines:
        lower = line.casefold()
        if lower.startswith("for "):
            return line[4:].strip()
        if "管理层" in line or "leaders" in lower or "executive" in lower or "manager" in lower:
            return line
    return ""


def _extract_primary_question(brief: str) -> str:
    lines = [line.strip(" -\t") for line in brief.splitlines() if line.strip()]
    for line in lines:
        lower = line.casefold()
        if lower.startswith("primary question:") or lower.startswith("primary question -"):
            return line.split(":", 1)[1].strip() if ":" in line else line.split("-", 1)[1].strip()
        if lower.startswith("question:") or lower.startswith("question -"):
            return line.split(":", 1)[1].strip() if ":" in line else line.split("-", 1)[1].strip()
        if line.startswith("核心问题：") or line.startswith("核心问题:"):
            return line.split(":", 1)[1].strip() if ":" in line else line.split("：", 1)[1].strip()
    for line in lines:
        if line.endswith("?") or "？" in line:
            return line
    if lines:
        return lines[0]
    return ""


def _infer_interaction_requirement(brief: str) -> bool | None:
    lower = brief.casefold()
    if any(token in lower for token in ("no interaction", "static only", "不要交互", "无需交互")):
        return False
    if any(
        token in lower
        for token in (
            "filter",
            "drill",
            "interaction",
            "click",
            "link",
            "url",
            "go-to-sheet",
            "jump",
            "跳转",
            "联动",
            "筛选",
            "交互",
        )
    ):
        return True
    return None


def _choose_measure(fields: dict[str, list[str]], fallback: str = "Sales") -> str:
    return fields["measures"][0] if fields["measures"] else fallback


def _choose_dimension(fields: dict[str, list[str]], fallback: str = "Category") -> str:
    return fields["dimensions"][0] if fields["dimensions"] else fallback


def _choose_geo(fields: dict[str, list[str]], fallback: str = "State/Province") -> str:
    geo_fields = fields.get("geo_fields", [])
    if not geo_fields:
        return fallback

    preferred_order = [
        "region",
        "state/province",
        "state",
        "province",
        "country/region",
        "country",
        "city",
        "postal code",
        "zip code",
        "zipcode",
        "latitude",
        "longitude",
        "lat",
        "lon",
    ]
    ranked = {
        name: index
        for index, name in enumerate(preferred_order)
    }

    def _rank(field_name: str) -> tuple[int, str]:
        normalized = " ".join(
            field_name.casefold().replace("_", " ").replace("-", " ").split()
        )
        return (ranked.get(normalized, len(preferred_order)), field_name)

    return sorted(geo_fields, key=_rank)[0]


def _choose_date(fields: dict[str, list[str]], fallback: str = "Order Date") -> str:
    return fields["date_fields"][0] if fields["date_fields"] else fallback


def _resolve_mark_type(question: str, priority: str, field_candidates: dict[str, list[str]]) -> str:
    lower = " ".join((question or "", priority or "")).casefold()
    if "map" in lower or "region" in lower or "state" in lower or "geograph" in lower:
        if field_candidates["geo_fields"]:
            return "Map"
    if any(token in lower for token in ("trend", "month", "time", "over time", "timeline")):
        if field_candidates["date_fields"]:
            return "Line"
    if priority == "summary":
        return "Text"
    return "Bar"


def _default_worksheet_specs(field_candidates: dict[str, list[str]]) -> list[dict[str, Any]]:
    primary_measure = _choose_measure(field_candidates)
    primary_dimension = _choose_dimension(field_candidates)
    geo_dimension = _choose_geo(field_candidates)
    date_field = _choose_date(field_candidates)
    return [
        {
            "name": "Summary View",
            "question": f"What high-level {primary_measure} summary should this dashboard show first?",
            "mark_type": "Text",
            "priority": "summary",
        },
        {
            "name": "Primary View",
            "question": f"Which {geo_dimension or primary_dimension} is driving {primary_measure}?",
            "mark_type": "Map" if field_candidates["geo_fields"] else "Bar",
            "priority": "primary",
        },
        {
            "name": "Detail View",
            "question": f"How is {primary_measure} changing over {date_field}?",
            "mark_type": "Line" if field_candidates["date_fields"] else "Bar",
            "priority": "detail",
        },
    ]


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in ("", None):
            continue
        cleaned = str(value).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _json_code_fence(payload: dict[str, Any]) -> str:
    return "```yaml\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"


def _format_bullets(items: list[str]) -> str:
    if not items:
        return "- (none)"
    return "\n".join(f"- {item}" for item in items)


def _extract_override_block(markdown_text: str) -> str:
    in_block = False
    block_lines: list[str] = []
    for line in markdown_text.splitlines():
        stripped = line.strip()
        if not in_block and stripped.startswith("```"):
            label = stripped[3:].strip().casefold()
            if label in {"yaml", "yml"}:
                in_block = True
            continue
        if in_block and stripped.startswith("```"):
            break
        if in_block:
            block_lines.append(line)
    block = "\n".join(block_lines).strip()
    if not block:
        raise ValueError("No fenced YAML override block was found in the Markdown artifact.")
    return block


def _parse_override_block(block: str) -> dict[str, Any]:
    try:
        if yaml is not None:
            parsed = yaml.safe_load(block)
        else:
            parsed = json.loads(block)
    except Exception as exc:  # pragma: no cover - exact parser varies by env
        raise ValueError(
            "Failed to parse the fenced YAML override block. "
            "Use JSON-compatible YAML in the code fence for V1.1."
        ) from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError("The fenced YAML override block must parse to an object.")
    return parsed


def _load_markdown_overrides(markdown_path: str | Path) -> dict[str, Any]:
    normalized_path = Path(markdown_path).expanduser().resolve()
    if not normalized_path.exists():
        raise FileNotFoundError(f"Markdown review artifact not found: {normalized_path}")
    markdown_text = normalized_path.read_text(encoding="utf-8")
    return _parse_override_block(_extract_override_block(markdown_text))


def _combined_overrides(
    *,
    markdown_path: str = "",
    user_answers_json: str = "",
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if markdown_path.strip():
        overrides = _load_markdown_overrides(markdown_path)
    if user_answers_json.strip():
        parsed = json.loads(user_answers_json)
        if not isinstance(parsed, dict):
            raise ValueError("user_answers_json must be a JSON object.")
        overrides = _deep_merge(overrides, parsed)
    return overrides


def _choose_named_field(fields: list[str], preferred_names: list[str]) -> str:
    normalized_map = {
        " ".join(field.casefold().replace("_", " ").replace("-", " ").split()): field
        for field in fields
    }
    for preferred in preferred_names:
        normalized = " ".join(preferred.casefold().replace("_", " ").replace("-", " ").split())
        if normalized in normalized_map:
            return normalized_map[normalized]
    return ""


def _suggest_kpis(field_candidates: dict[str, list[str]]) -> list[str]:
    measures = field_candidates.get("measures", [])
    kpis: list[str] = []
    for preferred in ("Sales", "Profit", "Quantity", "Discount"):
        chosen = _choose_named_field(measures, [preferred])
        if chosen:
            kpis.append(chosen)
    if _choose_named_field(measures, ["Sales"]) and _choose_named_field(measures, ["Profit"]):
        kpis.append("Profit Ratio")
    if not kpis and measures:
        kpis.extend(measures[:3])
    return _unique_strings(kpis)


def _suggest_filters(field_candidates: dict[str, list[str]]) -> list[str]:
    dimensions = field_candidates.get("dimensions", [])
    filters: list[str] = []
    date_field = _choose_date(field_candidates, "")
    geo_field = _choose_geo(field_candidates, "")
    if date_field:
        filters.append(date_field)
    if geo_field:
        filters.append(geo_field)
    for preferred in ("Category", "Sub-Category", "Segment"):
        chosen = _choose_named_field(dimensions, [preferred])
        if chosen:
            filters.append(chosen)
    if not filters:
        filters.extend(dimensions[:3])
    return _unique_strings(filters)


def _worksheet_plan(
    *,
    summary_question: str,
    primary_name: str,
    primary_question: str,
    primary_mark: str,
    detail_question: str,
    detail_mark: str,
) -> list[dict[str, Any]]:
    return [
        {
            "name": "Summary View",
            "question": summary_question,
            "mark_type": "Text",
            "priority": "summary",
        },
        {
            "name": primary_name,
            "question": primary_question,
            "mark_type": primary_mark,
            "priority": "primary",
        },
        {
            "name": "Detail View",
            "question": detail_question,
            "mark_type": detail_mark,
            "priority": "detail",
        },
    ]


def _analysis_direction(
    *,
    direction_id: str,
    title: str,
    business_question: str,
    why_it_matters: str,
    recommended_kpis: list[str],
    primary_view: dict[str, Any],
    detail_view: dict[str, Any],
    recommended_filters: list[str],
    interaction_pattern: str,
    caveats: list[str],
    layout_pattern: str = "executive overview",
) -> dict[str, Any]:
    worksheet_plan = _worksheet_plan(
        summary_question=f"What top-level summary should {title} show first?",
        primary_name=primary_view["name"],
        primary_question=primary_view["question"],
        primary_mark=primary_view["mark_type"],
        detail_question=detail_view["question"],
        detail_mark=detail_view["mark_type"],
    )
    return {
        "id": direction_id,
        "title": title,
        "business_question": business_question,
        "why_it_matters": why_it_matters,
        "recommended_kpis": recommended_kpis,
        "primary_view": primary_view,
        "detail_view": detail_view,
        "recommended_filters": recommended_filters,
        "interaction_pattern": interaction_pattern,
        "caveats": caveats,
        "contract_seed": {
            "dashboard_name": title,
            "layout_pattern": layout_pattern,
            "kpis": recommended_kpis,
            "filters": recommended_filters,
            "interaction_pattern": interaction_pattern,
            "worksheets": worksheet_plan,
        },
    }


def _build_analysis_directions(schema_summary: dict[str, Any]) -> list[dict[str, Any]]:
    field_candidates = schema_summary.get("field_candidates", {})
    measures = field_candidates.get("measures", [])
    dimensions = field_candidates.get("dimensions", [])
    primary_measure = _choose_named_field(measures, ["Sales", "Profit"]) or _choose_measure(field_candidates)
    profit_measure = _choose_named_field(measures, ["Profit"]) or primary_measure
    quantity_measure = _choose_named_field(measures, ["Quantity"])
    geo_field = _choose_geo(field_candidates, "")
    date_field = _choose_date(field_candidates, "")
    category_field = _choose_named_field(dimensions, ["Category"]) or _choose_dimension(field_candidates)
    subcategory_field = _choose_named_field(dimensions, ["Sub-Category"])
    segment_field = _choose_named_field(dimensions, ["Segment"])

    common_kpis = _suggest_kpis(field_candidates)
    common_filters = _suggest_filters(field_candidates)
    directions: list[dict[str, Any]] = []

    primary_axis = geo_field or category_field or _choose_dimension(field_candidates)
    directions.append(
        _analysis_direction(
            direction_id="executive_overview",
            title="Executive Overview",
            business_question=(
                f"Which {primary_axis} and categories are driving {primary_measure}"
                + (f" and {profit_measure}" if profit_measure != primary_measure else "")
                + "?"
            ),
            why_it_matters="Gives leaders a fast cross-cut of performance, mix, and drill paths.",
            recommended_kpis=common_kpis,
            primary_view={
                "name": "Primary View",
                "question": f"Which {primary_axis} is driving {primary_measure}?",
                "mark_type": "Map" if geo_field else "Bar",
            },
            detail_view={
                "name": "Detail View",
                "question": f"How is {primary_measure} changing over {date_field or 'time'}?",
                "mark_type": "Line" if date_field else "Bar",
            },
            recommended_filters=common_filters,
            interaction_pattern="Click Primary View to filter Detail View.",
            caveats=[
                "Keep the dashboard to one executive page.",
                "URL-style interactions should be confirmed before plan generation.",
            ],
        )
    )

    if geo_field:
        directions.append(
            _analysis_direction(
                direction_id="geographic_performance",
                title="Regional Performance",
                business_question=f"Which {geo_field} are outperforming or underperforming on {primary_measure} and {profit_measure}?",
                why_it_matters="Helps regional leaders spot where to drill deeper and compare markets quickly.",
                recommended_kpis=_unique_strings([primary_measure, profit_measure, quantity_measure, "Profit Ratio"]),
                primary_view={
                    "name": "Primary View",
                    "question": f"Which {geo_field} is driving the biggest performance gap?",
                    "mark_type": "Map",
                },
                detail_view={
                    "name": "Detail View",
                    "question": f"How does each {geo_field} trend over {date_field or 'time'}?",
                    "mark_type": "Line" if date_field else "Bar",
                },
                recommended_filters=_unique_strings([date_field, geo_field, category_field]),
                interaction_pattern="Click a region to filter the detail trend.",
                caveats=["Direct dashboard-title interactions may require a worksheet-zone fallback."],
            )
        )

    if category_field:
        directions.append(
            _analysis_direction(
                direction_id="product_mix",
                title="Product Mix",
                business_question=(
                    f"Which {subcategory_field or category_field} are driving {primary_measure}"
                    + (f" and {profit_measure}" if profit_measure != primary_measure else "")
                    + "?"
                ),
                why_it_matters="Useful when leaders want to understand category contribution and margin tradeoffs.",
                recommended_kpis=_unique_strings([primary_measure, profit_measure, quantity_measure]),
                primary_view={
                    "name": "Primary View",
                    "question": f"Which {category_field} is driving {primary_measure}?",
                    "mark_type": "Bar",
                },
                detail_view={
                    "name": "Detail View",
                    "question": f"How do {subcategory_field or category_field} compare inside the selected slice?",
                    "mark_type": "Bar",
                },
                recommended_filters=_unique_strings([date_field, category_field, segment_field]),
                interaction_pattern="Click Primary View to filter Detail View.",
                caveats=["Works best when category fields are clean and stable."],
            )
        )

    if segment_field:
        directions.append(
            _analysis_direction(
                direction_id="segment_health",
                title="Segment Health",
                business_question=f"Which {segment_field} segments are strongest on {primary_measure} and {profit_measure}?",
                why_it_matters="Good for leadership teams comparing consumer, corporate, or enterprise performance.",
                recommended_kpis=_unique_strings([primary_measure, profit_measure, quantity_measure]),
                primary_view={
                    "name": "Primary View",
                    "question": f"Which {segment_field} is driving performance?",
                    "mark_type": "Bar",
                },
                detail_view={
                    "name": "Detail View",
                    "question": f"How does the selected {segment_field} trend over {date_field or 'time'}?",
                    "mark_type": "Line" if date_field else "Bar",
                },
                recommended_filters=_unique_strings([date_field, segment_field, geo_field]),
                interaction_pattern="Click a segment to filter the detail view.",
                caveats=["Segment dashboards are best when the audience cares about customer mix."],
            )
        )

    return directions[:4]


def _build_analysis_brief_payload(run_id: str, schema_summary: dict[str, Any]) -> dict[str, Any]:
    directions = _build_analysis_directions(schema_summary)
    if not directions:
        raise RuntimeError("Could not derive any analysis directions from the current schema.")
    return {
        "run_id": run_id,
        "source_schema": schema_summary.get("selected_primary_object", ""),
        "field_candidates": schema_summary.get("field_candidates", {}),
        "directions": directions,
        "selected_direction_id": directions[0]["id"],
        "selected_direction_title": directions[0]["title"],
        "notes": [
            "V1.1 uses schema-driven heuristics instead of a full exploratory analysis engine.",
            "Choose the direction that best matches the business conversation before drafting the contract.",
        ],
    }


def _selected_analysis_direction(analysis_brief: dict[str, Any]) -> dict[str, Any]:
    selected_id = str(analysis_brief.get("selected_direction_id", "")).strip()
    for direction in analysis_brief.get("directions", []):
        if isinstance(direction, dict) and direction.get("id") == selected_id:
            return direction
    raise RuntimeError("The analysis brief does not have a valid selected_direction_id.")


def _render_schema_summary_markdown(schema_summary: dict[str, Any]) -> str:
    field_candidates = schema_summary.get("field_candidates", {})
    selected_primary_object = schema_summary.get("selected_primary_object", "")
    datasource = schema_summary.get("datasource", {})
    return (
        "# Schema Review\n\n"
        f"- Datasource: `{datasource.get('path', '')}`\n"
        f"- Type: `{datasource.get('type', '')}`\n"
        f"- Selected primary object: `{selected_primary_object or '(not selected)'}`\n"
        f"- Measures: {', '.join(field_candidates.get('measures', []) or ['(none)'])}\n"
        f"- Dimensions: {', '.join(field_candidates.get('dimensions', []) or ['(none)'])}\n"
        f"- Date fields: {', '.join(field_candidates.get('date_fields', []) or ['(none)'])}\n"
        f"- Geo fields: {', '.join(field_candidates.get('geo_fields', []) or ['(none)'])}\n\n"
        "## Notes\n"
        f"{_format_bullets(schema_summary.get('notes', []))}\n"
    )


def _render_analysis_brief_markdown(analysis_brief: dict[str, Any]) -> str:
    direction_lines: list[str] = []
    for direction in analysis_brief.get("directions", []):
        if not isinstance(direction, dict):
            continue
        direction_lines.append(
            f"### {direction.get('title', '')}\n"
            f"- id: `{direction.get('id', '')}`\n"
            f"- Business question: {direction.get('business_question', '')}\n"
            f"- Why it matters: {direction.get('why_it_matters', '')}\n"
            f"- KPIs: {', '.join(direction.get('recommended_kpis', []) or ['(none)'])}\n"
            f"- Primary view: {direction.get('primary_view', {}).get('question', '')}\n"
            f"- Detail view: {direction.get('detail_view', {}).get('question', '')}\n"
            f"- Filters: {', '.join(direction.get('recommended_filters', []) or ['(none)'])}\n"
            f"- Interaction: {direction.get('interaction_pattern', '')}\n"
            f"- Caveats: {'; '.join(direction.get('caveats', []) or ['(none)'])}\n"
        )
    overrides = {
        "selected_direction_id": analysis_brief.get("selected_direction_id", ""),
    }
    return (
        "# Analysis Brief Review\n\n"
        "Choose one candidate dashboard direction before drafting the contract.\n\n"
        + "\n".join(direction_lines)
        + "\n## Editable Overrides\n"
        "Use this JSON-compatible YAML block to change the selected direction.\n\n"
        + _json_code_fence(overrides)
        + "\n"
    )


def _render_contract_markdown(contract: dict[str, Any]) -> str:
    constraints = contract.get("constraints", {})
    summary_lines = [
        f"- Goal: {contract.get('goal', '')}",
        f"- Audience: {contract.get('audience', '')}",
        f"- Primary question: {contract.get('primary_question', '')}",
        f"- Dashboard name: {contract.get('dashboard', {}).get('name', '')}",
        f"- KPIs: {', '.join(constraints.get('kpis', []) or ['(none)'])}",
        f"- Filters: {', '.join(constraints.get('filters', []) or ['(none)'])}",
        f"- Interaction required: {contract.get('require_interaction')}",
    ]
    return (
        "# Contract Review\n\n"
        + "\n".join(summary_lines)
        + "\n\n## Editable Overrides\n"
        "Edit the JSON-compatible YAML block if you want to change the contract before approval.\n\n"
        + _json_code_fence(contract)
        + "\n"
    )


def _worksheet_by_priority(contract: dict[str, Any], priority: str) -> dict[str, Any] | None:
    for worksheet in contract.get("worksheets", []):
        if (
            isinstance(worksheet, dict)
            and str(worksheet.get("priority", "")).strip().casefold() == priority.casefold()
        ):
            return worksheet
    return None


def _normalize_wireframe_actions(
    contract: dict[str, Any],
    field_candidates: dict[str, list[str]],
) -> list[dict[str, Any]]:
    worksheets = [
        worksheet for worksheet in contract.get("worksheets", []) if isinstance(worksheet, dict)
    ]
    worksheet_names = [
        str(worksheet.get("name", "")).strip()
        for worksheet in worksheets
        if str(worksheet.get("name", "")).strip()
    ]
    primary_sheet, detail_sheet = _choose_default_action_sheets(worksheets, worksheet_names)
    summary_sheet = _worksheet_by_priority(contract, "summary")
    summary_name = str(summary_sheet.get("name", "")).strip() if summary_sheet else ""
    action_field = (
        _choose_geo(field_candidates, "")
        if field_candidates.get("geo_fields")
        else _choose_dimension(field_candidates, "")
    )
    normalized_actions: list[dict[str, Any]] = []

    raw_actions = contract.get("actions") or []
    if not raw_actions and contract.get("require_interaction") and primary_sheet and detail_sheet:
        raw_actions = [
            {
                "type": "filter",
                "source": primary_sheet,
                "target": detail_sheet,
                "fields": [action_field] if action_field else [],
                "caption": f"Filter {detail_sheet} from {primary_sheet}",
            }
        ]

    for action in raw_actions:
        if not isinstance(action, dict):
            continue
        action_type = str(action.get("type", "filter")).strip().casefold() or "filter"
        requested_source = str(action.get("source", "")).strip()
        requested_target = str(action.get("target", "")).strip()
        resolved_source = requested_source
        resolved_target = requested_target
        support_level = "supported"
        note = ""

        if action_type == "filter":
            if not resolved_source:
                resolved_source = primary_sheet
                note = "Defaulted filter source to the primary worksheet."
            if not resolved_target:
                resolved_target = detail_sheet
                note = (note + " " if note else "") + "Defaulted filter target to the detail worksheet."
            if not resolved_source or not resolved_target or resolved_source == resolved_target:
                support_level = "unsupported"
                note = "Filter action could not be resolved to distinct source and target worksheets."
        elif action_type == "url":
            if requested_source.casefold() in {
                "dashboard",
                "dashboard_title",
                "title",
                "title_zone",
                "executive overview",
            }:
                resolved_source = summary_name or primary_sheet or (worksheet_names[0] if worksheet_names else "")
                support_level = "workaround" if resolved_source else "unsupported"
                note = (
                    "Dashboard-title URL actions are modeled as a top worksheet-zone click in V1.1."
                    if resolved_source
                    else "No worksheet zone was available for a URL-action workaround."
                )
            elif not resolved_source:
                resolved_source = summary_name or primary_sheet or (worksheet_names[0] if worksheet_names else "")
                support_level = "workaround" if resolved_source else "unsupported"
                note = (
                    "Defaulted URL action to the top summary zone."
                    if resolved_source
                    else "No worksheet zone was available for a URL action."
                )

        normalized_actions.append(
            {
                "type": action_type,
                "requested_source": requested_source,
                "requested_target": requested_target,
                "source": resolved_source,
                "target": resolved_target,
                "fields": action.get("fields", []),
                "caption": action.get("caption", ""),
                "url": action.get("url", ""),
                "support_level": support_level,
                "note": note,
            }
        )

    return normalized_actions


def _ascii_box(lines: list[str], width: int = 70) -> str:
    horizontal = "+" + "-" * width + "+"
    rendered = [horizontal]
    for line in lines:
        content = line[:width].ljust(width)
        rendered.append(f"|{content}|")
    rendered.append(horizontal)
    return "\n".join(rendered)


def _build_wireframe_payload(
    *,
    run_id: str,
    contract: dict[str, Any],
    schema_summary: dict[str, Any],
) -> dict[str, Any]:
    field_candidates = schema_summary.get("field_candidates", {})
    constraints = contract.get("constraints", {})
    primary_view = _worksheet_by_priority(contract, "primary") or {"name": "Primary View", "question": ""}
    detail_view = _worksheet_by_priority(contract, "detail") or {"name": "Detail View", "question": ""}
    summary_view = _worksheet_by_priority(contract, "summary") or {"name": "Summary View", "question": ""}
    filters = constraints.get("filters", []) or _suggest_filters(field_candidates)
    actions = _normalize_wireframe_actions(contract, field_candidates)
    support_notes = [action["note"] for action in actions if action.get("note")]
    if not support_notes:
        support_notes = ["No extra workaround notes were needed for the current interaction design."]

    ascii_lines = [
        contract.get("dashboard", {}).get("name", "Analytical Dashboard"),
        "",
        "KPI Zone: " + " | ".join((constraints.get("kpis", []) or ["(define KPIs)"])[:4]),
        "",
        f"Primary View: {primary_view.get('name', 'Primary View')}",
        str(primary_view.get("question", "")),
        "",
        f"Detail View: {detail_view.get('name', 'Detail View')}",
        str(detail_view.get("question", "")),
        "",
        "Filters: " + " | ".join(filters or ["(none)"]),
        "Actions: " + " ; ".join(
            [
                f"{action['type']} {action.get('source', '')}->{action.get('target', '') or action.get('url', '')} [{action.get('support_level', '')}]"
                for action in actions
            ]
            or ["(none)"]
        ),
        "Notes: " + " ; ".join(support_notes),
    ]

    return {
        "run_id": run_id,
        "dashboard_name": contract.get("dashboard", {}).get("name", "Analytical Dashboard"),
        "zones": {
            "title_zone": contract.get("dashboard", {}).get("name", "Analytical Dashboard"),
            "summary_zone": summary_view.get("name", "Summary View"),
            "primary_zone": primary_view.get("name", "Primary View"),
            "detail_zone": detail_view.get("name", "Detail View"),
            "filter_zone": filters,
        },
        "actions": actions,
        "support_notes": support_notes,
        "ascii_wireframe": _ascii_box(ascii_lines),
    }


def _render_wireframe_markdown(wireframe: dict[str, Any]) -> str:
    overrides = {
        "support_notes": wireframe.get("support_notes", []),
        "actions": wireframe.get("actions", []),
    }
    return (
        "# Wireframe Review\n\n"
        "Use this ASCII wireframe to confirm the information hierarchy and action bindings.\n\n"
        "```text\n"
        + wireframe.get("ascii_wireframe", "")
        + "\n```\n\n"
        "## Editable Overrides\n"
        "Edit the JSON-compatible YAML block if you need to adjust notes or normalized actions before approval.\n\n"
        + _json_code_fence(overrides)
        + "\n"
    )


def _render_execution_plan_markdown(plan: dict[str, Any]) -> str:
    step_lines = [
        f"{index}. `{step.get('tool', '')}`"
        for index, step in enumerate(plan.get("steps", []), start=1)
    ]
    return (
        "# Execution Plan Review\n\n"
        "This plan is read-only in V1.1. If you want changes, reopen `contract` or `wireframe`, rebuild, and confirm again.\n\n"
        "## Planned Steps\n"
        + "\n".join(step_lines)
        + "\n\n## Post Checks\n"
        + _format_bullets([check.get("tool", "") for check in plan.get("post_checks", [])])
        + "\n"
    )


def _json_response(**payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _artifact_names(manifest: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for entry in manifest.get("artifacts", {}).values():
        current = entry.get("current", "")
        if current:
            names.append(current)
        review_current = entry.get("review_current", "")
        if review_current:
            names.append(review_current)
    approvals = Path(manifest["run_dir"]) / APPROVALS_NAME
    if approvals.exists():
        names.append(APPROVALS_NAME)
    if manifest.get("final_workbook"):
        names.append(Path(manifest["final_workbook"]).name)
    return sorted(set(names))


def start_authoring_run(
    datasource_path: str,
    output_dir: str | Path = DEFAULT_AUTHORING_RUNS_DIR,
    resume_if_exists: bool = False,
) -> str:
    """Create a new guided authoring run rooted in tmp/agentic_run/{run_id}."""

    normalized_path = _normalize_path(datasource_path)
    if not Path(normalized_path).exists():
        raise FileNotFoundError(f"Datasource file not found: {normalized_path}")

    root_dir = _ensure_dir(Path(output_dir))
    if resume_if_exists:
        index_payload = _load_index(root_dir)
        for run_id, info in index_payload.get("runs", {}).items():
            if info.get("datasource_path") == normalized_path:
                manifest_path = Path(info["run_dir"]) / MANIFEST_NAME
                if manifest_path.exists():
                    manifest = _read_json(manifest_path)
                    return _json_response(
                        run_id=run_id,
                        run_dir=manifest["run_dir"],
                        status=manifest["status"],
                        resumed=True,
                    )

    datasource_type = _detect_datasource_type(normalized_path)
    hash_seed = f"{normalized_path}|{_now().timestamp()}".encode("utf-8")
    run_id = f"{_now_token()}-{hashlib.sha1(hash_seed).hexdigest()[:8]}"
    run_dir = _ensure_dir(root_dir / run_id)
    manifest = _default_manifest(root_dir, run_dir, run_id, normalized_path, datasource_type)
    _write_json(run_dir / MANIFEST_NAME, manifest)
    _write_json(run_dir / APPROVALS_NAME, _empty_approvals())
    _update_index_entry(manifest)
    return _json_response(
        run_id=run_id,
        run_dir=str(run_dir),
        datasource_path=normalized_path,
        datasource_type=datasource_type,
        status=manifest["status"],
        resumed=False,
    )


def list_authoring_runs(output_dir: str | Path = DEFAULT_AUTHORING_RUNS_DIR) -> str:
    """List run ids, timestamps, status, and datasource paths for all runs."""

    root_dir = Path(output_dir)
    index_payload = _load_index(root_dir)
    runs: list[dict[str, Any]] = []
    for run_id, info in sorted(
        index_payload.get("runs", {}).items(),
        key=lambda item: item[1].get("created_at", ""),
        reverse=True,
    ):
        manifest_path = Path(info.get("run_dir", "")) / MANIFEST_NAME
        manifest = _read_json(manifest_path) if manifest_path.exists() else info
        runs.append(
            {
                "run_id": run_id,
                "created_at": manifest.get("created_at", ""),
                "updated_at": manifest.get("updated_at", ""),
                "status": manifest.get("status", ""),
                "datasource_path": manifest.get("datasource_path", ""),
                "artifacts_present": _artifact_names(manifest),
            }
        )
    return _json_response(runs=runs)


def get_run_status(run_id: str) -> str:
    """Return the current manifest-backed state for one authoring run."""

    manifest = _load_manifest_by_id(run_id)
    return _json_response(
        run_id=manifest["run_id"],
        status=manifest["status"],
        datasource_path=manifest["datasource_path"],
        datasource_type=manifest["datasource_type"],
        selected_primary_object=manifest.get("selected_primary_object", ""),
        created_at=manifest.get("created_at", ""),
        updated_at=manifest.get("updated_at", ""),
        artifacts=manifest.get("artifacts", {}),
        artifacts_present=_artifact_names(manifest),
        final_workbook=manifest.get("final_workbook", ""),
        last_error=manifest.get("last_error", {}),
    )


def resume_authoring_run(run_id: str) -> str:
    """Resume an interrupted authoring run by returning its current status."""

    manifest = _load_manifest_by_id(run_id)
    return _json_response(
        run_id=manifest["run_id"],
        status=manifest["status"],
        run_dir=manifest["run_dir"],
        needs_attention=(manifest["status"] == STATUS_GENERATION_FAILED),
        last_error=manifest.get("last_error", {}),
        artifacts_present=_artifact_names(manifest),
    )


def intake_datasource_schema(run_id: str, preferred_sheet: str = "") -> str:
    """Inspect the manifest datasource and write schema_summary.json + .md."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(manifest, (STATUS_INITIALIZED, STATUS_SCHEMA_INTAKED), "intake datasource schema")

    datasource_path = Path(manifest["datasource_path"])
    if manifest["datasource_type"] == "excel":
        summary = _build_excel_schema_summary(datasource_path, preferred_sheet=preferred_sheet)
    elif manifest["datasource_type"] == "hyper":
        summary = _build_hyper_schema_summary(datasource_path)
    else:
        raise ValueError(f"Unsupported datasource type: {manifest['datasource_type']}")

    manifest["selected_primary_object"] = summary.get("selected_primary_object", "")
    artifact_path = _write_versioned_artifact(
        manifest,
        ARTIFACT_SCHEMA,
        summary,
        markdown_content=_render_schema_summary_markdown(summary),
    )
    _update_manifest(manifest, status=STATUS_SCHEMA_INTAKED, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        selected_primary_object=manifest.get("selected_primary_object", ""),
        artifact=str(artifact_path),
        review_artifact=str(_current_review_artifact_path(manifest, ARTIFACT_SCHEMA)),
    )


def build_analysis_brief(run_id: str) -> str:
    """Generate a light analyst-copilot brief with 2-4 candidate dashboard directions."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(
        manifest,
        (STATUS_SCHEMA_CONFIRMED, STATUS_ANALYSIS_BUILT, STATUS_ANALYSIS_FINALIZED),
        "build analysis brief",
    )
    schema_summary = _load_current_artifact(manifest, ARTIFACT_SCHEMA)
    payload = _build_analysis_brief_payload(run_id, schema_summary)
    artifact_path = _write_versioned_artifact(
        manifest,
        ARTIFACT_ANALYSIS_BRIEF,
        payload,
        markdown_content=_render_analysis_brief_markdown(payload),
    )
    _update_manifest(manifest, status=STATUS_ANALYSIS_BUILT, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        artifact=str(artifact_path),
        review_artifact=str(_current_review_artifact_path(manifest, ARTIFACT_ANALYSIS_BRIEF)),
        direction_count=len(payload.get("directions", [])),
    )


def finalize_analysis_brief(
    run_id: str,
    user_answers_json: str = "",
    markdown_path: str = "",
) -> str:
    """Finalize the selected analysis direction from chat overrides or a Markdown review file."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(
        manifest,
        (STATUS_ANALYSIS_BUILT, STATUS_ANALYSIS_FINALIZED),
        "finalize analysis brief",
    )
    analysis_brief = _load_current_artifact(manifest, ARTIFACT_ANALYSIS_BRIEF)
    overrides = _combined_overrides(
        markdown_path=markdown_path,
        user_answers_json=user_answers_json,
    )
    merged = _deep_merge(analysis_brief, overrides)
    direction = _selected_analysis_direction(merged)
    merged["selected_direction_title"] = direction.get("title", "")
    artifact_path = _write_versioned_artifact(
        manifest,
        ARTIFACT_ANALYSIS_BRIEF,
        merged,
        markdown_content=_render_analysis_brief_markdown(merged),
    )
    _update_manifest(manifest, status=STATUS_ANALYSIS_FINALIZED, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        selected_direction_id=merged.get("selected_direction_id", ""),
        selected_direction_title=merged.get("selected_direction_title", ""),
        artifact=str(artifact_path),
        review_artifact=str(_current_review_artifact_path(manifest, ARTIFACT_ANALYSIS_BRIEF)),
    )


def draft_authoring_contract(run_id: str, human_brief: str, rewrite: bool = False) -> str:
    """Draft a contract from the human brief plus the current schema summary."""

    manifest = _load_manifest_by_id(run_id)
    allowed = (STATUS_ANALYSIS_CONFIRMED,)
    if rewrite:
        allowed = (STATUS_CONTRACT_REVIEWED, STATUS_CONTRACT_FINALIZED, STATUS_CONTRACT_DRAFTED)
    _require_status(manifest, allowed, "draft authoring contract")

    schema_summary = _load_current_artifact(manifest, ARTIFACT_SCHEMA)
    analysis_brief = _load_current_artifact(manifest, ARTIFACT_ANALYSIS_BRIEF)
    selected_direction = _selected_analysis_direction(analysis_brief)
    seed = selected_direction.get("contract_seed", {})
    from .config import CONTRACTS_DIR

    template = _read_json(CONTRACTS_DIR / "dashboard_authoring_v1.json")
    field_candidates = schema_summary.get("field_candidates", {})
    brief = human_brief.strip()

    contract = deepcopy(template)
    contract["goal"] = brief
    contract["audience"] = _extract_audience(brief)
    contract["dataset"] = Path(manifest["datasource_path"]).stem
    recommended_profiles = schema_summary.get("recommended_profile_matches", [])
    contract["dataset_profile"] = recommended_profiles[0]["id"] if recommended_profiles else ""
    contract["workbook_template"] = ""
    contract["available_fields"] = [field["name"] for field in schema_summary.get("fields", [])]
    contract["primary_question"] = _extract_primary_question(brief) or selected_direction.get(
        "business_question", ""
    )
    interaction_requirement = _infer_interaction_requirement(brief)
    contract["require_interaction"] = (
        interaction_requirement
        if interaction_requirement is not None
        else bool(seed.get("interaction_pattern"))
    )
    contract["worksheets"] = deepcopy(seed.get("worksheets", [])) or _default_worksheet_specs(field_candidates)
    contract["constraints"]["kpis"] = deepcopy(seed.get("kpis", [])) or contract["constraints"].get("kpis", [])
    contract["constraints"]["filters"] = deepcopy(seed.get("filters", [])) or contract["constraints"].get("filters", [])
    contract["constraints"]["interaction_pattern"] = seed.get("interaction_pattern", "")
    contract["constraints"]["layout_pattern"] = seed.get("layout_pattern", "executive overview")
    contract["dashboard"]["name"] = seed.get("dashboard_name", contract["dashboard"].get("name", ""))
    contract["dashboard"]["layout_pattern"] = seed.get(
        "layout_pattern",
        contract["dashboard"].get("layout_pattern", ""),
    )
    contract["analysis_direction_id"] = selected_direction.get("id", "")
    contract["analysis_direction_title"] = selected_direction.get("title", "")
    if contract["worksheets"]:
        for worksheet in contract["worksheets"]:
            worksheet["mark_type"] = worksheet["mark_type"] or _resolve_mark_type(
                worksheet.get("question", ""),
                worksheet.get("priority", ""),
                field_candidates,
            )

    artifact_path = _write_versioned_artifact(manifest, ARTIFACT_CONTRACT_DRAFT, contract)
    _update_manifest(manifest, status=STATUS_CONTRACT_DRAFTED, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        artifact=str(artifact_path),
    )


def review_authoring_contract_for_run(run_id: str) -> str:
    """Review the current contract draft and persist the review result."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(manifest, (STATUS_CONTRACT_DRAFTED,), "review contract")
    contract = _load_current_artifact(manifest, ARTIFACT_CONTRACT_DRAFT)
    review = json.loads(review_authoring_contract_payload(json.dumps(contract)).to_json())
    artifact_path = _write_versioned_artifact(manifest, ARTIFACT_CONTRACT_REVIEW, review)
    _update_manifest(manifest, status=STATUS_CONTRACT_REVIEWED, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        valid=review["valid"],
        clarification_questions=review["clarification_questions"],
        artifact=str(artifact_path),
    )


def finalize_authoring_contract(
    run_id: str,
    user_answers_json: str = "",
    markdown_path: str = "",
) -> str:
    """Merge review defaults with human overrides and write contract_final.json + .md."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(
        manifest,
        (STATUS_CONTRACT_REVIEWED, STATUS_CONTRACT_FINALIZED),
        "finalize contract",
    )
    review_payload = _load_current_artifact(manifest, ARTIFACT_CONTRACT_REVIEW)
    normalized_contract = deepcopy(review_payload["normalized_contract"])
    overrides = _combined_overrides(
        markdown_path=markdown_path,
        user_answers_json=user_answers_json,
    )
    merged = _deep_merge(normalized_contract, overrides)
    refreshed = json.loads(review_authoring_contract_payload(json.dumps(merged)).to_json())
    final_contract = refreshed["normalized_contract"]
    artifact_path = _write_versioned_artifact(
        manifest,
        ARTIFACT_CONTRACT_FINAL,
        final_contract,
        markdown_content=_render_contract_markdown(final_contract),
    )
    _update_manifest(manifest, status=STATUS_CONTRACT_FINALIZED, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        valid=refreshed["valid"],
        missing_required=refreshed["missing_required"],
        artifact=str(artifact_path),
        review_artifact=str(_current_review_artifact_path(manifest, ARTIFACT_CONTRACT_FINAL)),
    )


def build_wireframe(run_id: str) -> str:
    """Build a human-reviewable ASCII wireframe from the confirmed contract."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(
        manifest,
        (STATUS_CONTRACT_CONFIRMED, STATUS_WIREFRAME_BUILT, STATUS_WIREFRAME_FINALIZED),
        "build wireframe",
    )
    contract = _load_current_artifact(manifest, ARTIFACT_CONTRACT_FINAL)
    schema_summary = _load_current_artifact(manifest, ARTIFACT_SCHEMA)
    payload = _build_wireframe_payload(
        run_id=run_id,
        contract=contract,
        schema_summary=schema_summary,
    )
    artifact_path = _write_versioned_artifact(
        manifest,
        ARTIFACT_WIREFRAME,
        payload,
        markdown_content=_render_wireframe_markdown(payload),
    )
    _update_manifest(manifest, status=STATUS_WIREFRAME_BUILT, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        artifact=str(artifact_path),
        review_artifact=str(_current_review_artifact_path(manifest, ARTIFACT_WIREFRAME)),
    )


def finalize_wireframe(
    run_id: str,
    user_answers_json: str = "",
    markdown_path: str = "",
) -> str:
    """Finalize the wireframe review artifact before execution planning."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(
        manifest,
        (STATUS_WIREFRAME_BUILT, STATUS_WIREFRAME_FINALIZED),
        "finalize wireframe",
    )
    wireframe = _load_current_artifact(manifest, ARTIFACT_WIREFRAME)
    overrides = _combined_overrides(
        markdown_path=markdown_path,
        user_answers_json=user_answers_json,
    )
    merged = _deep_merge(wireframe, overrides)
    artifact_path = _write_versioned_artifact(
        manifest,
        ARTIFACT_WIREFRAME,
        merged,
        markdown_content=_render_wireframe_markdown(merged),
    )
    _update_manifest(manifest, status=STATUS_WIREFRAME_FINALIZED, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        artifact=str(artifact_path),
        review_artifact=str(_current_review_artifact_path(manifest, ARTIFACT_WIREFRAME)),
    )


def confirm_authoring_stage(run_id: str, stage: str, approved: bool, notes: str = "") -> str:
    """Record a human confirmation decision and advance or roll back state."""

    if stage not in CONFIRMABLE_STAGES:
        raise ValueError(
            f"Unsupported stage '{stage}'. Expected one of: {', '.join(sorted(CONFIRMABLE_STAGES))}"
        )

    manifest = _load_manifest_by_id(run_id)
    stage_current: dict[str, Any] = {}
    if stage == SCHEMA_STAGE:
        _require_status(manifest, (STATUS_SCHEMA_INTAKED,), "confirm schema")
        schema_payload = _load_current_artifact(manifest, ARTIFACT_SCHEMA)
        if approved and not schema_payload.get("selected_primary_object"):
            raise RuntimeError(
                "Schema cannot be confirmed until a primary sheet/table is selected."
            )
        next_status = STATUS_SCHEMA_CONFIRMED if approved else STATUS_SCHEMA_INTAKED
        stage_current = {
            "artifact": _artifact_entry(manifest, ARTIFACT_SCHEMA).get("current", ""),
            "selected_primary_object": schema_payload.get("selected_primary_object", ""),
        }
    elif stage == ANALYSIS_STAGE:
        _require_status(manifest, (STATUS_ANALYSIS_FINALIZED,), "confirm analysis brief")
        analysis_payload = _load_current_artifact(manifest, ARTIFACT_ANALYSIS_BRIEF)
        if approved:
            _selected_analysis_direction(analysis_payload)
            next_status = STATUS_ANALYSIS_CONFIRMED
        else:
            next_status = STATUS_ANALYSIS_BUILT
        stage_current = {
            "artifact": _artifact_entry(manifest, ARTIFACT_ANALYSIS_BRIEF).get("current", ""),
            "selected_direction_id": analysis_payload.get("selected_direction_id", ""),
            "selected_direction_title": analysis_payload.get("selected_direction_title", ""),
        }
    elif stage == CONTRACT_STAGE:
        _require_status(
            manifest,
            (STATUS_CONTRACT_FINALIZED, STATUS_CONTRACT_REVIEWED),
            "confirm contract",
        )
        if approved:
            final_contract = _load_current_artifact(manifest, ARTIFACT_CONTRACT_FINAL)
            refreshed = json.loads(review_authoring_contract_payload(json.dumps(final_contract)).to_json())
            if not refreshed["valid"]:
                raise RuntimeError(
                    "Contract cannot be confirmed until all required intent is captured."
                )
            next_status = STATUS_CONTRACT_CONFIRMED
            stage_current = {
                "artifact": _artifact_entry(manifest, ARTIFACT_CONTRACT_FINAL).get("current", ""),
                "missing_required": refreshed["missing_required"],
            }
        else:
            next_status = STATUS_CONTRACT_REVIEWED
            stage_current = {
                "artifact": _artifact_entry(manifest, ARTIFACT_CONTRACT_REVIEW).get("current", ""),
                "rewrite_hint": "rewrite" in notes.casefold() or "重写" in notes,
            }
    elif stage == WIREFRAME_STAGE:
        _require_status(manifest, (STATUS_WIREFRAME_FINALIZED,), "confirm wireframe")
        wireframe_payload = _load_current_artifact(manifest, ARTIFACT_WIREFRAME)
        next_status = STATUS_WIREFRAME_CONFIRMED if approved else STATUS_WIREFRAME_BUILT
        stage_current = {
            "artifact": _artifact_entry(manifest, ARTIFACT_WIREFRAME).get("current", ""),
            "support_notes": wireframe_payload.get("support_notes", []),
        }
    else:
        _require_status(manifest, (STATUS_EXECUTION_PLANNED,), "confirm execution plan")
        next_status = STATUS_EXECUTION_CONFIRMED if approved else STATUS_EXECUTION_PLANNED
        stage_current = {
            "artifact": _artifact_entry(manifest, ARTIFACT_EXECUTION_PLAN).get("current", ""),
        }

    approvals = _load_approvals(manifest)
    approvals.setdefault("events", []).append(
        {
            "stage": stage,
            "approved": approved,
            "notes": notes,
            "timestamp": _now_iso(),
            "artifact": stage_current.get("artifact", ""),
        }
    )
    _save_approvals(manifest, approvals)
    _update_manifest(manifest, status=next_status, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        stage=stage,
        approved=approved,
        notes=notes,
        current=stage_current,
    )


def reopen_authoring_stage(run_id: str, stage: str, notes: str = "") -> str:
    """Reopen one editable guided-run stage after a generation failure."""

    if stage not in {ANALYSIS_STAGE, CONTRACT_STAGE, WIREFRAME_STAGE, EXECUTION_STAGE}:
        raise ValueError(
            "reopen_authoring_stage only supports 'analysis', 'contract', 'wireframe', or 'execution_plan'."
        )

    manifest = _load_manifest_by_id(run_id)
    _require_status(manifest, (STATUS_GENERATION_FAILED,), "reopen authoring stage")
    status_map = {
        ANALYSIS_STAGE: STATUS_ANALYSIS_FINALIZED,
        CONTRACT_STAGE: STATUS_CONTRACT_FINALIZED,
        WIREFRAME_STAGE: STATUS_WIREFRAME_FINALIZED,
        EXECUTION_STAGE: STATUS_EXECUTION_PLANNED,
    }
    artifact_map = {
        ANALYSIS_STAGE: ARTIFACT_ANALYSIS_BRIEF,
        CONTRACT_STAGE: ARTIFACT_CONTRACT_FINAL,
        WIREFRAME_STAGE: ARTIFACT_WIREFRAME,
        EXECUTION_STAGE: ARTIFACT_EXECUTION_PLAN,
    }
    artifact_name = _artifact_entry(manifest, artifact_map[stage]).get("current", "")
    if not artifact_name:
        raise RuntimeError(f"Cannot reopen '{stage}' because no current artifact exists for that stage.")

    approvals = _load_approvals(manifest)
    approvals.setdefault("events", []).append(
        {
            "stage": stage,
            "approved": None,
            "notes": notes,
            "timestamp": _now_iso(),
            "artifact": artifact_name,
            "event_type": "reopen",
        }
    )
    _save_approvals(manifest, approvals)
    _update_manifest(manifest, status=status_map[stage], last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        stage=stage,
        artifact=artifact_name,
        notes=notes,
    )


def _plan_calculated_fields(contract: dict[str, Any], available_fields: list[str]) -> list[dict[str, Any]]:
    known_formulas = {
        "Profit Ratio": "SUM([Profit])/SUM([Sales])",
    }
    steps: list[dict[str, Any]] = []
    for kpi in contract.get("constraints", {}).get("kpis", []):
        if not isinstance(kpi, str):
            continue
        if kpi in available_fields:
            continue
        formula = known_formulas.get(kpi)
        if formula:
            steps.append(
                {
                    "tool": "add_calculated_field",
                    "args": {
                        "field_name": kpi,
                        "formula": formula,
                        "datatype": "real",
                    },
                }
            )
    return steps


def _build_chart_step(
    worksheet: dict[str, Any],
    field_candidates: dict[str, list[str]],
) -> dict[str, Any]:
    name = worksheet.get("name", "Worksheet")
    question = worksheet.get("question", "")
    priority = worksheet.get("priority", "")
    mark_type = worksheet.get("mark_type") or _resolve_mark_type(question, priority, field_candidates)
    primary_measure = _choose_measure(field_candidates)
    primary_dimension = _choose_dimension(field_candidates)
    geo_dimension = _choose_geo(field_candidates)
    date_field = _choose_date(field_candidates)

    args: dict[str, Any] = {
        "worksheet_name": name,
        "mark_type": mark_type,
    }
    if mark_type == "Map":
        args["geographic_field"] = geo_dimension
        args["color"] = f"SUM({primary_measure})"
    elif mark_type == "Line":
        args["columns"] = [f"MONTH({date_field})"]
        args["rows"] = [f"SUM({primary_measure})"]
    elif mark_type == "Text":
        args["measure_values"] = [f"SUM({primary_measure})"]
    else:
        args["rows"] = [primary_dimension]
        args["columns"] = [f"SUM({primary_measure})"]

    return {"tool": "configure_chart", "args": args}


def _choose_default_action_sheets(
    worksheets: list[dict[str, Any]],
    worksheet_names: list[str],
) -> tuple[str, str]:
    primary_name = ""
    detail_name = ""

    for worksheet in worksheets:
        if not isinstance(worksheet, dict):
            continue
        name = str(worksheet.get("name", "")).strip()
        if not name or name not in worksheet_names:
            continue
        priority = str(worksheet.get("priority", "")).strip().casefold()
        if priority == "primary" and not primary_name:
            primary_name = name
        elif priority == "detail" and not detail_name:
            detail_name = name

    non_summary_names = [
        str(worksheet.get("name", "")).strip()
        for worksheet in worksheets
        if isinstance(worksheet, dict)
        and str(worksheet.get("name", "")).strip() in worksheet_names
        and str(worksheet.get("priority", "")).strip().casefold() != "summary"
    ]

    if not primary_name and non_summary_names:
        primary_name = non_summary_names[0]
    if not detail_name and len(non_summary_names) >= 2:
        detail_name = non_summary_names[1]

    if not primary_name and worksheet_names:
        primary_name = worksheet_names[0]
    if not detail_name and len(worksheet_names) >= 2:
        detail_name = worksheet_names[1]

    return primary_name, detail_name


def build_execution_plan(run_id: str) -> str:
    """Create a mechanical MCP tool sequence from the current final contract."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(manifest, (STATUS_WIREFRAME_CONFIRMED,), "build execution plan")
    contract = _load_current_artifact(manifest, ARTIFACT_CONTRACT_FINAL)
    schema_summary = _load_current_artifact(manifest, ARTIFACT_SCHEMA)
    wireframe = _load_current_artifact(manifest, ARTIFACT_WIREFRAME)
    field_candidates = schema_summary.get("field_candidates", {})
    available_fields = [field["name"] for field in schema_summary.get("fields", [])]
    workbook_template = contract.get("workbook_template", "") or ""

    steps: list[dict[str, Any]] = [
        {
            "tool": "create_workbook",
            "args": {
                "template_path": workbook_template,
                "workbook_name": contract.get("dashboard", {}).get("name", ""),
            },
        }
    ]

    if manifest["datasource_type"] == "excel":
        steps.append(
            {
                "tool": "set_excel_connection",
                "args": {
                    "filepath": manifest["datasource_path"],
                    "sheet_name": schema_summary.get("selected_primary_object", ""),
                    "fields": schema_summary.get("fields", []),
                },
            }
        )
    elif manifest["datasource_type"] == "hyper":
        steps.append(
            {
                "tool": "set_hyper_connection",
                "args": {
                    "filepath": manifest["datasource_path"],
                    "table_name": schema_summary.get("selected_primary_object", "Extract"),
                    "tables": [
                        {
                            "name": table["name"],
                            "columns": [field["name"] for field in table.get("fields", [])],
                        }
                        for table in schema_summary.get("tables", [])
                    ],
                },
            }
        )

    steps.extend(_plan_calculated_fields(contract, available_fields))

    worksheet_names: list[str] = []
    for worksheet in contract.get("worksheets", []):
        if not isinstance(worksheet, dict):
            continue
        name = str(worksheet.get("name", "")).strip()
        if not name:
            continue
        worksheet_names.append(name)
        steps.append({"tool": "add_worksheet", "args": {"worksheet_name": name}})
        steps.append(_build_chart_step(worksheet, field_candidates))
        caption = str(worksheet.get("question", "")).strip()
        if caption:
            steps.append(
                {
                    "tool": "set_worksheet_caption",
                    "args": {"worksheet_name": name, "caption": caption},
                }
            )

    dashboard_name = contract.get("dashboard", {}).get("name") or "Analytical Dashboard"
    steps.append(
        {
            "tool": "add_dashboard",
            "args": {
                "dashboard_name": dashboard_name,
                "worksheet_names": worksheet_names,
                "layout": contract.get("dashboard", {}).get("layout_pattern")
                or contract.get("constraints", {}).get("layout_pattern", "vertical"),
            },
        }
    )

    actions = wireframe.get("actions") or []
    if actions:
        for action in actions:
            if not isinstance(action, dict) or action.get("support_level") == "unsupported":
                continue
            steps.append(
                {
                    "tool": "add_dashboard_action",
                    "args": {
                        "dashboard_name": dashboard_name,
                        "action_type": action.get("type", "filter"),
                        "source_sheet": action.get("source", worksheet_names[0] if worksheet_names else ""),
                        "target_sheet": action.get("target", ""),
                        "fields": action.get("fields", []),
                        "caption": action.get("caption", ""),
                        "url": action.get("url", ""),
                    },
                }
            )
    elif contract.get("require_interaction") and len(worksheet_names) >= 2:
        source_sheet, target_sheet = _choose_default_action_sheets(
            [
                worksheet
                for worksheet in contract.get("worksheets", [])
                if isinstance(worksheet, dict)
            ],
            worksheet_names,
        )
        action_field = (
            _choose_geo(field_candidates)
            if field_candidates.get("geo_fields")
            else _choose_dimension(field_candidates)
        )
        if source_sheet and target_sheet and source_sheet != target_sheet:
            steps.append(
                {
                    "tool": "add_dashboard_action",
                    "args": {
                        "dashboard_name": dashboard_name,
                        "action_type": "filter",
                        "source_sheet": source_sheet,
                        "target_sheet": target_sheet,
                        "fields": [action_field] if action_field else [],
                        "caption": f"Filter {target_sheet} from {source_sheet}",
                    },
                }
            )

    plan = {
        "run_id": run_id,
        "source_contract": _artifact_entry(manifest, ARTIFACT_CONTRACT_FINAL).get("current", ""),
        "source_wireframe": _artifact_entry(manifest, ARTIFACT_WIREFRAME).get("current", ""),
        "workbook_template": workbook_template,
        "steps": steps,
        "post_checks": [
            {"tool": "validate_workbook", "args": {}},
            {"tool": "analyze_twb", "args": {}},
        ],
    }
    artifact_path = _write_versioned_artifact(
        manifest,
        ARTIFACT_EXECUTION_PLAN,
        plan,
        markdown_content=_render_execution_plan_markdown(plan),
    )
    _update_manifest(manifest, status=STATUS_EXECUTION_PLANNED, last_error={})
    return _json_response(
        run_id=run_id,
        status=manifest["status"],
        artifact=str(artifact_path),
        review_artifact=str(_current_review_artifact_path(manifest, ARTIFACT_EXECUTION_PLAN)),
        step_count=len(steps),
    )


def load_execution_plan_for_run(run_id: str) -> dict[str, Any]:
    """Load the current execution plan and enforce confirmation state."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(
        manifest,
        (STATUS_EXECUTION_CONFIRMED, STATUS_GENERATION_STARTED, STATUS_GENERATION_FAILED),
        "load execution plan",
    )
    return _load_current_artifact(manifest, ARTIFACT_EXECUTION_PLAN)


def mark_generation_started(run_id: str) -> dict[str, Any]:
    """Set the run to workbook_generation_started and return the manifest."""

    manifest = _load_manifest_by_id(run_id)
    _require_status(manifest, (STATUS_EXECUTION_CONFIRMED,), "generate workbook")
    _update_manifest(manifest, status=STATUS_GENERATION_STARTED, last_error={})
    return manifest


def mark_generation_failed(run_id: str, step_tool: str, error_message: str) -> dict[str, Any]:
    """Persist a generation failure payload and return the manifest."""

    manifest = _load_manifest_by_id(run_id)
    _update_manifest(
        manifest,
        status=STATUS_GENERATION_FAILED,
        last_error={
            "failed_at": _now_iso(),
            "step_tool": step_tool,
            "message": error_message,
        },
    )
    return manifest


def mark_generation_success(run_id: str, final_workbook: str) -> dict[str, Any]:
    """Persist a successful workbook generation result and return the manifest."""

    manifest = _load_manifest_by_id(run_id)
    manifest["final_workbook"] = final_workbook
    _update_manifest(manifest, status=STATUS_GENERATED, last_error={})
    return manifest


def write_post_check_artifact(run_id: str, artifact_key: str, payload: dict[str, Any], status: str) -> dict[str, Any]:
    """Write a validation or analysis artifact and advance the run state."""

    manifest = _load_manifest_by_id(run_id)
    _write_versioned_artifact(manifest, artifact_key, payload)
    _update_manifest(manifest, status=status, last_error={})
    return manifest
