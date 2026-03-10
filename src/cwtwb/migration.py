"""Workbook migration helpers for reusing TWB templates with a new datasource."""

from __future__ import annotations

import difflib
import json
import os
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from lxml import etree
import xlrd

from .twb_analyzer import analyze_workbook


@dataclass
class MappingCandidate:
    source_field: str
    target_field: str
    confidence: float
    reason: str


@dataclass
class MigrationIssue:
    issue_type: str
    severity: str
    message: str
    worksheet: str | None = None
    calculation: str | None = None
    field: str | None = None


@dataclass
class MigrationPreview:
    template_file: str
    target_source: str
    source_datasource: str
    source_datasource_caption: str | None
    target_datasource: str
    target_datasource_caption: str | None
    scope: str
    worksheets_in_scope: list[str]
    dashboards_in_scope: list[str]
    used_datasources: list[str]
    source_schema: list[str]
    target_schema: list[str]
    candidate_field_mapping: list[MappingCandidate]
    calculation_rewrite_summary: dict[str, int]
    issues: list[MigrationIssue] = field(default_factory=list)
    ai_review: dict[str, Any] = field(default_factory=dict)
    removable_datasources: list[str] = field(default_factory=list)
    capability_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def blocking_issue_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "blocking")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blocking_issue_count"] = self.blocking_issue_count
        return payload


@dataclass
class WorkbookMigrationProfile:
    template_file: str
    scope: str
    datasources: list[dict[str, Any]]
    worksheets_in_scope: list[str]
    dashboards_in_scope: list[str]
    used_datasources: list[str]
    source_datasource: str
    source_datasource_caption: str | None
    source_schema: list[str]
    source_excel_profile: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ColumnProfile:
    field: str
    index: int
    kind: str
    pattern: str
    blank_ratio: float
    distinct_ratio: float
    distinct_count: int
    avg_text_length: float
    top_frequencies: list[float]
    numeric_min: float | None
    numeric_max: float | None
    sample_values: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).resolve()).replace("\\", "/")


def _normalize_field_name(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _normalize_sample_value(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text.casefold()
    if number.is_integer():
        return str(int(number))
    return f"{number:.8f}".rstrip("0").rstrip(".")


def _sequence_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return difflib.SequenceMatcher(a=left, b=right).ratio()


def _is_ai_warning_review_enabled(use_ai_for_warnings: bool | None) -> bool:
    if use_ai_for_warnings is not None:
        return use_ai_for_warnings
    return bool(os.environ.get("OPENAI_API_KEY"))


def _get_ai_warning_review_model() -> str:
    return os.environ.get("CWTWB_OPENAI_MODEL") or os.environ.get("OPENAI_MODEL") or "gpt-5-mini"


def _extract_response_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"].strip():
        return payload["output_text"].strip()

    parts: list[str] = []
    for output_item in payload.get("output", []):
        for content_item in output_item.get("content", []):
            text_value = content_item.get("text")
            if isinstance(text_value, str) and text_value.strip():
                parts.append(text_value.strip())
    return "\n".join(parts).strip()


def _parse_json_object_from_text(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI response did not contain a JSON object.")
    return json.loads(stripped[start : end + 1])


def _request_ai_warning_review(prompt: str, model: str) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    base_url = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    body = {
        "model": model,
        "input": prompt,
    }
    request = urllib_request.Request(
        url=f"{base_url}/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    organization = os.environ.get("OPENAI_ORGANIZATION")
    if organization:
        request.add_header("OpenAI-Organization", organization)
    project = os.environ.get("OPENAI_PROJECT")
    if project:
        request.add_header("OpenAI-Project", project)

    try:
        with urllib_request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI warning review request failed: {exc.code} {detail}") from exc


def _review_warning_candidates_with_ai(
    warning_candidates: list[MappingCandidate],
    ranked_by_source: dict[str, list[tuple[float, str, list[str]]]],
    source_profiles: dict[str, ColumnProfile],
    target_profiles: dict[str, ColumnProfile],
    assigned_targets: set[str],
    use_ai_for_warnings: bool | None,
) -> dict[str, Any]:
    if not warning_candidates:
        return {
            "enabled": False,
            "attempted": False,
            "used": False,
            "status": "not-needed",
            "model": None,
            "reviewed_fields": [],
            "applied_suggestions": [],
        }

    enabled = _is_ai_warning_review_enabled(use_ai_for_warnings)
    if not enabled:
        return {
            "enabled": False,
            "attempted": False,
            "used": False,
            "status": "disabled",
            "model": None,
            "reviewed_fields": [candidate.source_field for candidate in warning_candidates],
            "applied_suggestions": [],
        }

    model = _get_ai_warning_review_model()
    if not os.environ.get("OPENAI_API_KEY"):
        return {
            "enabled": False,
            "attempted": False,
            "used": False,
            "status": "disabled",
            "model": model,
            "reviewed_fields": [candidate.source_field for candidate in warning_candidates],
            "applied_suggestions": [],
            "reason": "OPENAI_API_KEY is not configured",
        }
    review_payload = []
    for candidate in warning_candidates:
        ranked_options = []
        for confidence, target_field, reasons in ranked_by_source.get(candidate.source_field, [])[:4]:
            target_profile = target_profiles[target_field]
            ranked_options.append(
                {
                    "target_field": target_field,
                    "rule_confidence": confidence,
                    "reason": ", ".join(reasons[:4]),
                    "profile": target_profile.to_dict(),
                    "already_assigned": target_field in assigned_targets and target_field != candidate.target_field,
                }
            )
        review_payload.append(
            {
                "source_field": candidate.source_field,
                "current_target_field": candidate.target_field,
                "current_rule_confidence": candidate.confidence,
                "source_profile": source_profiles[candidate.source_field].to_dict(),
                "candidate_targets": ranked_options,
            }
        )

    prompt = (
        "You are reviewing low-confidence Tableau field mappings.\n"
        "Pick the best target field for each source field from the provided candidate_targets only.\n"
        "Prefer keeping the current_target_field unless another candidate is clearly better.\n"
        "Never reuse a target field that is marked already_assigned=true.\n"
        "Return JSON only in this exact shape: "
        "{\"suggestions\":[{\"source_field\":\"...\",\"target_field\":\"...\",\"confidence\":0.0,\"reason\":\"...\"}]}\n\n"
        f"{json.dumps({'warning_candidates': review_payload}, ensure_ascii=False)}"
    )

    try:
        response_payload = _request_ai_warning_review(prompt, model=model)
        output_text = _extract_response_output_text(response_payload)
        parsed = _parse_json_object_from_text(output_text)
    except Exception as exc:  # noqa: BLE001
        return {
            "enabled": True,
            "attempted": True,
            "used": False,
            "status": "error",
            "model": model,
            "reviewed_fields": [candidate.source_field for candidate in warning_candidates],
            "applied_suggestions": [],
            "error": str(exc),
        }

    suggestions = parsed.get("suggestions", [])
    if not isinstance(suggestions, list):
        suggestions = []

    return {
        "enabled": True,
        "attempted": True,
        "used": True,
        "status": "completed",
        "model": model,
        "reviewed_fields": [candidate.source_field for candidate in warning_candidates],
        "applied_suggestions": suggestions,
    }


def _sample_overlap_score(source_profile: ColumnProfile, target_profile: ColumnProfile) -> tuple[float, list[str]]:
    source_samples = [_normalize_sample_value(value) for value in source_profile.sample_values]
    target_samples = [_normalize_sample_value(value) for value in target_profile.sample_values]
    source_samples = [value for value in source_samples if value]
    target_samples = [value for value in target_samples if value]

    reasons: list[str] = []
    if not source_samples or not target_samples:
        return 0.0, reasons

    source_set = set(source_samples)
    target_set = set(target_samples)
    overlap = len(source_set & target_set) / max(min(len(source_set), len(target_set)), 1)
    aligned = sum(
        1
        for source_value, target_value in zip(source_samples, target_samples)
        if source_value == target_value
    ) / max(min(len(source_samples), len(target_samples)), 1)

    score = 0.0
    if overlap > 0:
        score += 0.72 * overlap
        reasons.append(f"sample overlap {overlap:.2f}")
    if aligned > 0:
        score += 0.38 * aligned
        reasons.append(f"sample order match {aligned:.2f}")
    return score, reasons


def _frequency_signature_score(source_profile: ColumnProfile, target_profile: ColumnProfile) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if not source_profile.top_frequencies or not target_profile.top_frequencies:
        return 0.0, reasons

    max_len = max(len(source_profile.top_frequencies), len(target_profile.top_frequencies))
    left = source_profile.top_frequencies + [0.0] * (max_len - len(source_profile.top_frequencies))
    right = target_profile.top_frequencies + [0.0] * (max_len - len(target_profile.top_frequencies))
    gap = sum(abs(a - b) for a, b in zip(left, right)) / max_len
    similarity = max(0.0, 1.0 - min(gap / 0.35, 1.0))
    if similarity > 0:
        reasons.append(f"frequency signature {similarity:.2f}")
    return 0.34 * similarity, reasons


def _numeric_range_score(source_profile: ColumnProfile, target_profile: ColumnProfile) -> tuple[float, list[str]]:
    reasons: list[str] = []
    if source_profile.numeric_min is None or target_profile.numeric_min is None:
        return 0.0, reasons

    source_span = max((source_profile.numeric_max or 0.0) - source_profile.numeric_min, 0.0)
    target_span = max((target_profile.numeric_max or 0.0) - target_profile.numeric_min, 0.0)
    if source_span == 0 and target_span == 0:
        return 0.18, ["same zero numeric range"]

    lower_gap = abs(source_profile.numeric_min - target_profile.numeric_min) / max(abs(source_profile.numeric_min), abs(target_profile.numeric_min), 1.0)
    span_gap = abs(source_span - target_span) / max(abs(source_span), abs(target_span), 1.0)
    similarity = max(0.0, 1.0 - min((lower_gap + span_gap) / 1.2, 1.0))
    if similarity > 0:
        reasons.append(f"numeric range {similarity:.2f}")
    return 0.22 * similarity, reasons


def _read_excel_headers(path: str | Path) -> dict[str, Any]:
    workbook = xlrd.open_workbook(_normalize_path(path))
    sheet = workbook.sheet_by_index(0)
    headers = [str(value).strip() for value in sheet.row_values(0) if str(value).strip()]
    return {
        "sheet_name": sheet.name,
        "headers": headers,
    }


def _strip_table_brackets(table_name: str | None) -> str | None:
    if not table_name:
        return None
    cleaned = table_name.strip()
    cleaned = cleaned.replace("[", "").replace("]", "")
    if "." in cleaned:
        cleaned = cleaned.split(".")[-1]
    if cleaned.endswith("$"):
        cleaned = cleaned[:-1]
    return cleaned or None


def _find_excel_connection_filename(datasource: etree._Element) -> str | None:
    connection = datasource.find(".//connection[@class='excel-direct']")
    if connection is None:
        return None
    filename = connection.get("filename")
    if not filename:
        return None
    return filename.replace("\\", "/")


def _resolve_linked_excel_path(
    workbook_path: str | Path,
    linked_path: str | Path | None,
) -> str | None:
    if not linked_path:
        return None

    workbook_parent = Path(workbook_path).resolve().parent
    raw = Path(str(linked_path).replace("\\", "/"))
    candidates: list[Path] = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(workbook_parent / raw)
    candidates.append(workbook_parent / raw.name)

    for candidate in candidates:
        if candidate.exists():
            return _normalize_path(candidate)
    return None


def _find_relation_sheet_name(datasource: etree._Element) -> str | None:
    relation = datasource.find(".//relation")
    if relation is None:
        return None
    return _strip_table_brackets(relation.get("table") or relation.get("name"))


def _open_excel_sheet(path: str | Path, sheet_name: str | None = None):
    workbook = xlrd.open_workbook(_normalize_path(path))
    if sheet_name:
        for worksheet in workbook.sheets():
            if worksheet.name == sheet_name:
                return workbook, worksheet
    return workbook, workbook.sheet_by_index(0)


def _infer_value_kind(values: list[Any]) -> str:
    non_blank = [value for value in values if value not in ("", None)]
    if not non_blank:
        return "empty"
    if all(isinstance(value, (int, float)) for value in non_blank):
        numeric = [float(value) for value in non_blank]
        if all(value.is_integer() for value in numeric):
            if numeric and min(numeric) >= 30000 and max(numeric) <= 60000:
                return "date_serial"
            return "integer"
        return "real"
    return "text"


def _infer_value_pattern(kind: str, values: list[Any], distinct_ratio: float, blank_ratio: float) -> str:
    if blank_ratio >= 0.8:
        return "blank-heavy"
    non_blank = [value for value in values if value not in ("", None)]
    if kind == "date_serial":
        return "date"
    if kind == "integer":
        numeric = [float(value) for value in non_blank]
        if numeric and distinct_ratio >= 0.95 and numeric == sorted(numeric):
            return "integer-counter"
        if numeric and min(numeric) >= 0 and max(numeric) <= 20:
            return "small-integer"
        return "integer"
    if kind == "real":
        numeric = [float(value) for value in non_blank]
        if numeric and min(numeric) >= 0 and max(numeric) <= 1.0:
            return "fraction"
        if any(value < 0 for value in numeric):
            return "signed-measure"
        return "positive-measure"
    if kind == "text":
        text_values = [str(value).strip() for value in non_blank]
        if text_values and all(any(ch.isdigit() for ch in value) for value in text_values[: min(10, len(text_values))]):
            return "id-code"
        if distinct_ratio <= 0.1:
            return "text-low-cardinality"
        if distinct_ratio >= 0.9:
            return "text-high-cardinality"
        return "text"
    return kind


def _build_column_profiles(headers: list[str], rows: list[list[Any]], max_samples: int = 50) -> dict[str, ColumnProfile]:
    profiles: dict[str, ColumnProfile] = {}
    if not headers:
        return profiles
    sample_rows = rows[:max_samples]
    row_count = max(len(sample_rows), 1)
    for index, field in enumerate(headers):
        values = [row[index] if index < len(row) else "" for row in sample_rows]
        non_blank = [value for value in values if value not in ("", None)]
        distinct_values = [str(value) for value in non_blank]
        distinct_count = len(set(distinct_values))
        distinct_ratio = distinct_count / max(len(non_blank), 1)
        blank_ratio = 1 - (len(non_blank) / row_count)
        kind = _infer_value_kind(values)
        pattern = _infer_value_pattern(kind, values, distinct_ratio, blank_ratio)
        avg_text_length = round(
            sum(len(str(value).strip()) for value in non_blank) / max(len(non_blank), 1),
            2,
        )
        frequency_counts = Counter(distinct_values)
        top_frequencies = [
            round(count / max(len(non_blank), 1), 4)
            for count in sorted(frequency_counts.values(), reverse=True)[:5]
        ]
        numeric_min = None
        numeric_max = None
        if kind in {"integer", "real", "date_serial"} and non_blank:
            numeric_values = [float(value) for value in non_blank]
            numeric_min = round(min(numeric_values), 6)
            numeric_max = round(max(numeric_values), 6)
        sample_values = [str(value) for value in non_blank[:12]]
        profiles[field] = ColumnProfile(
            field=field,
            index=index,
            kind=kind,
            pattern=pattern,
            blank_ratio=round(blank_ratio, 4),
            distinct_ratio=round(distinct_ratio, 4),
            distinct_count=distinct_count,
            avg_text_length=avg_text_length,
            top_frequencies=top_frequencies,
            numeric_min=numeric_min,
            numeric_max=numeric_max,
            sample_values=sample_values,
        )
    return profiles


def _read_excel_profiles(path: str | Path, sheet_name: str | None = None) -> dict[str, Any]:
    workbook, sheet = _open_excel_sheet(path, sheet_name)
    headers = [str(value).strip() for value in sheet.row_values(0) if str(value).strip()]
    rows = [sheet.row_values(row_index) for row_index in range(1, min(sheet.nrows, 151))]
    profiles = _build_column_profiles(headers, rows)
    return {
        "path": _normalize_path(path),
        "sheet_name": sheet.name,
        "headers": headers,
        "row_count": max(sheet.nrows - 1, 0),
        "profiles": {field: profile.to_dict() for field, profile in profiles.items()},
    }


def _top_level_datasources(root: etree._Element) -> list[etree._Element]:
    datasources = root.find("datasources")
    if datasources is None:
        return []
    return datasources.findall("datasource")


def _get_datasource_fields(datasource: etree._Element) -> dict[str, str]:
    relation = datasource.find(".//relation")
    fields: dict[str, str] = {}
    if relation is None:
        return fields
    for col in relation.findall("columns/column"):
        raw_name = col.get("name")
        if raw_name:
            fields[raw_name] = f"[{raw_name}]"
    return fields


def _get_datasource_by_name(root: etree._Element, datasource_name: str) -> etree._Element | None:
    for ds in _top_level_datasources(root):
        if ds.get("name") == datasource_name:
            return ds
    return None


def _find_target_datasource(
    root: etree._Element,
    target_source: str | Path,
    workbook_path: str | Path | None = None,
) -> etree._Element | None:
    target_name = Path(target_source).name.casefold()
    normalized_target = _normalize_path(target_source).casefold()
    for datasource in _top_level_datasources(root):
        filename = _find_excel_connection_filename(datasource)
        if not filename:
            continue
        resolved = (
            _resolve_linked_excel_path(workbook_path, filename)
            if workbook_path is not None
            else filename
        ) or filename
        normalized_resolved = resolved.replace("\\", "/")
        if (
            Path(normalized_resolved).name.casefold() == target_name
            or normalized_resolved.casefold() == normalized_target
        ):
            return datasource
    return None


def _collect_scope_worksheets(root: etree._Element, scope: str) -> list[etree._Element]:
    if scope != "workbook":
        raise ValueError(f"Unsupported migration scope: {scope}")
    worksheets = root.find("worksheets")
    if worksheets is None:
        return []
    return worksheets.findall("worksheet")


def _worksheet_datasource_names(worksheet: etree._Element) -> list[str]:
    seen: list[str] = []
    for dep in worksheet.findall(".//datasource-dependencies"):
        datasource_name = dep.get("datasource")
        if datasource_name and datasource_name not in seen:
            seen.append(datasource_name)
    return seen


def _find_source_datasource_name(root: etree._Element, target_datasource_name: str | None, scope: str) -> str:
    usage_count: dict[str, int] = {}
    for worksheet in _collect_scope_worksheets(root, scope):
        for datasource_name in _worksheet_datasource_names(worksheet):
            usage_count[datasource_name] = usage_count.get(datasource_name, 0) + 1

    ranked = sorted(
        (
            (name, count)
            for name, count in usage_count.items()
            if target_datasource_name is None or name != target_datasource_name
        ),
        key=lambda item: (-item[1], item[0]),
    )
    if not ranked:
        raise ValueError("Could not identify a source datasource to migrate from.")
    return ranked[0][0]


def _collect_dashboards_for_worksheets(root: etree._Element, worksheet_names: set[str]) -> list[str]:
    dashboards = root.find("dashboards")
    if dashboards is None:
        return []
    names: list[str] = []
    for dashboard in dashboards.findall("dashboard"):
        for zone in dashboard.findall(".//zone[@name]"):
            if zone.get("name") in worksheet_names:
                names.append(dashboard.get("name", ""))
                break
    return [name for name in names if name]


def inspect_target_schema(target_source: str | Path) -> dict[str, Any]:
    info = _read_excel_profiles(target_source)
    info["target_source"] = _normalize_path(target_source)
    return info


def profile_twb_for_migration(
    file_path: str | Path,
    scope: str = "workbook",
    target_source: str | Path | None = None,
) -> WorkbookMigrationProfile:
    path = Path(file_path)
    root = etree.parse(str(path)).getroot()
    scope_worksheets = _collect_scope_worksheets(root, scope)
    worksheet_names = [worksheet.get("name", "") for worksheet in scope_worksheets]
    dashboards = _collect_dashboards_for_worksheets(root, set(worksheet_names))
    used_datasources = sorted(
        {
            datasource_name
            for worksheet in scope_worksheets
            for datasource_name in _worksheet_datasource_names(worksheet)
        }
    )

    target_datasource_name = None
    if target_source is not None:
        target_ds = _find_target_datasource(root, target_source, workbook_path=path)
        if target_ds is not None:
            target_datasource_name = target_ds.get("name")

    source_datasource_name = _find_source_datasource_name(root, target_datasource_name, scope)
    source_datasource = _get_datasource_by_name(root, source_datasource_name)
    if source_datasource is None:
        raise ValueError(f"Could not locate source datasource '{source_datasource_name}' in workbook.")

    source_fields = list(_get_datasource_fields(source_datasource).keys())
    source_excel_profile = None
    source_excel_filename = _resolve_linked_excel_path(
        path,
        _find_excel_connection_filename(source_datasource),
    )
    if source_excel_filename:
        source_excel_profile = _read_excel_profiles(
            source_excel_filename,
            _find_relation_sheet_name(source_datasource),
        )

    datasources = []
    for datasource in _top_level_datasources(root):
        datasources.append(
            {
                "name": datasource.get("name"),
                "caption": datasource.get("caption"),
                "hasconnection": datasource.get("hasconnection"),
                "field_count": len(_get_datasource_fields(datasource)),
                "used_in_scope": datasource.get("name") in used_datasources,
            }
        )

    return WorkbookMigrationProfile(
        template_file=_normalize_path(path),
        scope=scope,
        datasources=datasources,
        worksheets_in_scope=worksheet_names,
        dashboards_in_scope=dashboards,
        used_datasources=used_datasources,
        source_datasource=source_datasource_name,
        source_datasource_caption=source_datasource.get("caption"),
        source_schema=source_fields,
        source_excel_profile=source_excel_profile,
    )


def _profile_from_dict(field: str, payload: dict[str, Any]) -> ColumnProfile:
    return ColumnProfile(
        field=field,
        index=int(payload["index"]),
        kind=str(payload["kind"]),
        pattern=str(payload["pattern"]),
        blank_ratio=float(payload["blank_ratio"]),
        distinct_ratio=float(payload["distinct_ratio"]),
        distinct_count=int(payload.get("distinct_count", 0)),
        avg_text_length=float(payload.get("avg_text_length", 0.0)),
        top_frequencies=[float(value) for value in payload.get("top_frequencies", [])],
        numeric_min=float(payload["numeric_min"]) if payload.get("numeric_min") is not None else None,
        numeric_max=float(payload["numeric_max"]) if payload.get("numeric_max") is not None else None,
        sample_values=list(payload.get("sample_values", [])),
    )


def _score_field_match(source_field: str, target_field: str, source_profile: ColumnProfile, target_profile: ColumnProfile) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []

    if source_field == target_field:
        score += 0.9
        reasons.append("exact field name match")
    else:
        normalized_source = _normalize_field_name(source_field)
        normalized_target = _normalize_field_name(target_field)
        if normalized_source == normalized_target:
            score += 0.78
            reasons.append("normalized field name match")
        else:
            name_similarity = _sequence_similarity(normalized_source, normalized_target)
            if name_similarity >= 0.7:
                score += 0.34 * name_similarity
                reasons.append(f"name similarity {name_similarity:.2f}")

    sample_score, sample_reasons = _sample_overlap_score(source_profile, target_profile)
    score += sample_score
    reasons.extend(sample_reasons)

    frequency_score, frequency_reasons = _frequency_signature_score(source_profile, target_profile)
    score += frequency_score
    reasons.extend(frequency_reasons)

    if source_profile.kind == target_profile.kind:
        score += 0.22
        reasons.append(f"same kind: {source_profile.kind}")

    if source_profile.pattern == target_profile.pattern:
        score += 0.18
        reasons.append(f"same pattern: {source_profile.pattern}")

    distinct_gap = abs(source_profile.distinct_ratio - target_profile.distinct_ratio)
    if distinct_gap <= 0.2:
        score += 0.12 * (1 - (distinct_gap / 0.2))
        reasons.append("similar distinct ratio")

    if source_profile.distinct_count and target_profile.distinct_count:
        distinct_count_gap = abs(source_profile.distinct_count - target_profile.distinct_count) / max(
            source_profile.distinct_count,
            target_profile.distinct_count,
            1,
        )
        if distinct_count_gap <= 0.35:
            score += 0.14 * (1 - (distinct_count_gap / 0.35))
            reasons.append("similar distinct count")

    blank_gap = abs(source_profile.blank_ratio - target_profile.blank_ratio)
    if blank_gap <= 0.2:
        score += 0.08 * (1 - (blank_gap / 0.2))
        reasons.append("similar blank ratio")

    if source_profile.kind == "text" and target_profile.kind == "text":
        text_length_gap = abs(source_profile.avg_text_length - target_profile.avg_text_length) / max(
            source_profile.avg_text_length,
            target_profile.avg_text_length,
            1.0,
        )
        if text_length_gap <= 0.5:
            score += 0.12 * (1 - (text_length_gap / 0.5))
            reasons.append("similar text length")

    numeric_score, numeric_reasons = _numeric_range_score(source_profile, target_profile)
    score += numeric_score
    reasons.extend(numeric_reasons)

    position_gap = abs(source_profile.index - target_profile.index)
    if position_gap == 0:
        score += 0.12
        reasons.append("same column position")
    elif position_gap == 1:
        score += 0.08
        reasons.append("adjacent column position")

    confidence = round(min(score / 2.45, 1.0), 3)
    return confidence, reasons


def propose_field_mapping(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    use_ai_for_warnings: bool | None = None,
) -> dict[str, Any]:
    profile = profile_twb_for_migration(file_path, scope=scope, target_source=target_source)
    target_schema = inspect_target_schema(target_source)
    target_fields = target_schema["headers"]
    overrides = mapping_overrides or {}
    source_profiles_payload = (profile.source_excel_profile or {}).get("profiles", {})
    target_profiles_payload = target_schema.get("profiles", {})

    source_profiles = {
        field: _profile_from_dict(field, payload)
        for field, payload in source_profiles_payload.items()
        if field in profile.source_schema
    }
    target_profiles = {
        field: _profile_from_dict(field, payload)
        for field, payload in target_profiles_payload.items()
    }

    candidates: list[MappingCandidate] = []
    issues: list[MigrationIssue] = []
    ranked_by_source: dict[str, list[tuple[float, str, list[str]]]] = {}
    for source_field in profile.source_schema:
        if source_field in overrides:
            target_field = overrides[source_field]
            if target_field in target_fields:
                candidates.append(
                    MappingCandidate(
                        source_field=source_field,
                        target_field=target_field,
                        confidence=1.0,
                        reason="override mapping",
                    )
                )
            else:
                issues.append(
                    MigrationIssue(
                        issue_type="unmapped",
                        severity="blocking",
                        message=(
                            f"Override target field '{target_field}' does not exist in target schema "
                            f"for source field '{source_field}'."
                        ),
                        field=source_field,
                    )
                )
            continue

        source_profile = source_profiles.get(source_field)
        ranked: list[tuple[float, str, list[str]]] = []
        if source_profile is not None:
            for target_field in target_fields:
                target_profile = target_profiles.get(target_field)
                if target_profile is None:
                    continue
                confidence, reasons = _score_field_match(
                    source_field,
                    target_field,
                    source_profile,
                    target_profile,
                )
                ranked.append((confidence, target_field, reasons))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        ranked_by_source[source_field] = ranked

    assigned_targets = {candidate.target_field for candidate in candidates}
    unresolved_sources = [
        source_field
        for source_field in profile.source_schema
        if source_field not in overrides
    ]
    unresolved_sources.sort(
        key=lambda source_field: (
            -ranked_by_source.get(source_field, [(0.0, "", [])])[0][0]
            if ranked_by_source.get(source_field)
            else 0.0,
            source_field,
        )
    )

    minimum_confidence = 0.3
    warning_confidence = 0.45

    for source_field in unresolved_sources:
        ranked = [
            item
            for item in ranked_by_source.get(source_field, [])
            if item[1] not in assigned_targets
        ]
        if not ranked or ranked[0][0] < minimum_confidence:
            issues.append(
                MigrationIssue(
                    issue_type="unmapped",
                    severity="blocking",
                    message=f"Could not find a target field match for source field '{source_field}'.",
                    field=source_field,
                )
            )
            continue

        best_confidence, best_target, best_reasons = ranked[0]
        candidates.append(
            MappingCandidate(
                source_field=source_field,
                target_field=best_target,
                confidence=best_confidence,
                reason=", ".join(best_reasons[:4]) or "profile similarity match",
            )
        )
        assigned_targets.add(best_target)
        if best_confidence < warning_confidence:
            issues.append(
                MigrationIssue(
                    issue_type="low-confidence",
                    severity="warning",
                    message=(
                        f"Source field '{source_field}' matched '{best_target}' with low confidence "
                        f"({best_confidence}). Review if the target workbook behaves unexpectedly."
                    ),
                    field=source_field,
                )
            )

    remaining_sources = [
        source_field
        for source_field in profile.source_schema
        if source_field not in {candidate.source_field for candidate in candidates}
        and source_field not in overrides
    ]
    remaining_targets = [target_field for target_field in target_fields if target_field not in assigned_targets]
    if len(remaining_sources) == 1 and len(remaining_targets) == 1:
        candidates.append(
            MappingCandidate(
                source_field=remaining_sources[0],
                target_field=remaining_targets[0],
                confidence=minimum_confidence,
                reason="last remaining target after one-to-one allocation",
            )
        )
        issues = [
            issue
            for issue in issues
            if issue.field != remaining_sources[0] or issue.issue_type != "unmapped"
        ]

    candidates.sort(key=lambda candidate: profile.source_schema.index(candidate.source_field))
    warning_fields = {issue.field for issue in issues if issue.issue_type == "low-confidence" and issue.field}
    warning_candidates = [candidate for candidate in candidates if candidate.source_field in warning_fields]
    ai_review = _review_warning_candidates_with_ai(
        warning_candidates=warning_candidates,
        ranked_by_source=ranked_by_source,
        source_profiles=source_profiles,
        target_profiles=target_profiles,
        assigned_targets={candidate.target_field for candidate in candidates},
        use_ai_for_warnings=use_ai_for_warnings,
    )
    if ai_review.get("status") == "completed":
        candidate_by_source = {candidate.source_field: candidate for candidate in candidates}
        assigned_by_source = {candidate.source_field: candidate.target_field for candidate in candidates}
        target_to_source = {candidate.target_field: candidate.source_field for candidate in candidates}
        reviewed_fields = set(ai_review.get("reviewed_fields", []))
        retained_issues: list[MigrationIssue] = []
        resolved_warning_fields: set[str] = set()
        for suggestion in ai_review.get("applied_suggestions", []):
            source_field = suggestion.get("source_field")
            target_field = suggestion.get("target_field")
            try:
                confidence = float(suggestion.get("confidence", 0.0))
            except (TypeError, ValueError):
                confidence = 0.0
            reason = str(suggestion.get("reason", "")).strip() or "ai warning review"
            candidate = candidate_by_source.get(source_field)
            if candidate is None or source_field not in reviewed_fields:
                continue
            if target_field not in target_fields:
                continue
            assigned_source = target_to_source.get(target_field)
            if assigned_source is not None and assigned_source != source_field:
                continue

            previous_target = assigned_by_source[source_field]
            if previous_target != target_field:
                target_to_source.pop(previous_target, None)
                target_to_source[target_field] = source_field
                assigned_by_source[source_field] = target_field
                candidate.target_field = target_field
            candidate.confidence = max(candidate.confidence, round(confidence, 3))
            candidate.reason = f"{candidate.reason}; ai review: {reason}"
            if confidence >= 0.7:
                resolved_warning_fields.add(source_field)

        for issue in issues:
            if issue.issue_type == "low-confidence" and issue.field in resolved_warning_fields:
                continue
            retained_issues.append(issue)
        issues = retained_issues

    return {
        "template_file": profile.template_file,
        "target_source": target_schema["target_source"],
        "scope": scope,
        "source_datasource": profile.source_datasource,
        "source_schema": profile.source_schema,
        "target_schema": target_fields,
        "source_excel_profile": profile.source_excel_profile,
        "target_excel_profile": {
            "path": target_schema["path"],
            "sheet_name": target_schema["sheet_name"],
            "row_count": target_schema["row_count"],
        },
        "candidate_field_mapping": [asdict(candidate) for candidate in candidates],
        "ai_review": ai_review,
        "issues": [asdict(issue) for issue in issues],
        "blocking_issue_count": sum(1 for issue in issues if issue.severity == "blocking"),
    }


def _calculation_summary(worksheets: list[etree._Element]) -> dict[str, int]:
    total_calcs = 0
    rewrite_candidates = 0
    for worksheet in worksheets:
        for dep in worksheet.findall(".//datasource-dependencies"):
            for col in dep.findall("column"):
                calc = col.find("calculation")
                if calc is None:
                    continue
                total_calcs += 1
                formula = calc.get("formula") or ""
                if "[" in formula and "]" in formula:
                    rewrite_candidates += 1
    return {
        "worksheet_count": len(worksheets),
        "calculation_columns": total_calcs,
        "formulas_requiring_field_rewrite": rewrite_candidates,
    }


def preview_twb_migration(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    use_ai_for_warnings: bool | None = None,
) -> MigrationPreview:
    path = Path(file_path)
    root = etree.parse(str(path)).getroot()
    scope_worksheets = _collect_scope_worksheets(root, scope)
    worksheet_names = [worksheet.get("name", "") for worksheet in scope_worksheets]
    dashboards = _collect_dashboards_for_worksheets(root, set(worksheet_names))
    used_datasources = sorted(
        {
            datasource_name
            for worksheet in scope_worksheets
            for datasource_name in _worksheet_datasource_names(worksheet)
        }
    )

    target_datasource = _find_target_datasource(root, target_source, workbook_path=path)
    target_schema_info = inspect_target_schema(target_source)
    target_datasource_name = target_datasource.get("name", "") if target_datasource is not None else ""
    source_datasource_name = _find_source_datasource_name(root, target_datasource_name or None, scope)
    source_datasource = _get_datasource_by_name(root, source_datasource_name)
    if source_datasource is None:
        raise ValueError(f"Could not locate source datasource '{source_datasource_name}' in workbook.")

    mapping_payload = propose_field_mapping(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        use_ai_for_warnings=use_ai_for_warnings,
    )
    issues = [MigrationIssue(**issue) for issue in mapping_payload["issues"]]
    if target_datasource is None:
        issues.append(
            MigrationIssue(
                issue_type="target-datasource-missing",
                severity="blocking",
                message=(
                    "The target Excel file was scanned successfully, but no matching workbook datasource "
                    "points to it yet. Preview can continue, but apply requires an in-workbook target datasource."
                ),
            )
        )

    capability_report = analyze_workbook(path)
    return MigrationPreview(
        template_file=_normalize_path(path),
        target_source=_normalize_path(target_source),
        source_datasource=source_datasource_name,
        source_datasource_caption=source_datasource.get("caption"),
        target_datasource=target_datasource_name,
        target_datasource_caption=target_datasource.get("caption") if target_datasource is not None else None,
        scope=scope,
        worksheets_in_scope=worksheet_names,
        dashboards_in_scope=dashboards,
        used_datasources=used_datasources,
        source_schema=mapping_payload["source_schema"],
        target_schema=target_schema_info["headers"],
        candidate_field_mapping=[MappingCandidate(**candidate) for candidate in mapping_payload["candidate_field_mapping"]],
        calculation_rewrite_summary=_calculation_summary(scope_worksheets),
        issues=issues,
        ai_review=mapping_payload.get("ai_review", {}),
        removable_datasources=[source_datasource_name],
        capability_summary={
            "fit_level": capability_report.fit_level,
            "summary": capability_report.summary,
        },
    )


def _build_string_replacements(preview: MigrationPreview) -> dict[str, str]:
    if not preview.target_datasource:
        raise ValueError("Cannot build replacements without a target datasource already present in the workbook.")

    replacements = {
        preview.source_datasource: preview.target_datasource,
        f"[{preview.source_datasource}].": f"[{preview.target_datasource}].",
    }
    for candidate in preview.candidate_field_mapping:
        source_local = f"[{candidate.source_field}]"
        target_local = f"[{candidate.target_field}]"
        replacements[source_local] = target_local
        replacements[f":{candidate.source_field}:"] = f":{candidate.target_field}:"
    return replacements


def _replace_in_sections(root: etree._Element, replacements: dict[str, str]) -> None:
    ordered = sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)
    for section_name in ("worksheets", "dashboards", "windows", "actions"):
        section = root.find(section_name)
        if section is None:
            continue
        for element in section.iter():
            for key, value in list(element.attrib.items()):
                updated = value
                for old, new in ordered:
                    if old in updated:
                        updated = updated.replace(old, new)
                if updated != value:
                    element.set(key, updated)
            if element.text:
                updated_text = element.text
                for old, new in ordered:
                    if old in updated_text:
                        updated_text = updated_text.replace(old, new)
                if updated_text != element.text:
                    element.text = updated_text


def _set_datasource_excel_connection_path(
    datasource: etree._Element | None,
    source_path: str | Path,
) -> None:
    if datasource is None:
        return
    connection = datasource.find(".//connection[@class='excel-direct']")
    if connection is not None:
        connection.set("filename", _normalize_path(source_path))


def apply_twb_migration(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    output_path: str | Path | None = None,
    use_ai_for_warnings: bool | None = None,
) -> dict[str, Any]:
    preview = preview_twb_migration(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        use_ai_for_warnings=use_ai_for_warnings,
    )
    if preview.blocking_issue_count:
        raise ValueError(
            f"Cannot apply migration while blocking issues remain ({preview.blocking_issue_count})."
        )

    path = Path(file_path)
    tree = etree.parse(str(path))
    root = tree.getroot()
    replacements = _build_string_replacements(preview)
    _replace_in_sections(root, replacements)
    _set_datasource_excel_connection_path(
        _get_datasource_by_name(root, preview.target_datasource),
        target_source,
    )

    if output_path is None:
        output_path = path.with_name(f"{path.stem} - migrated.twb")
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)

    report_path = output_path.with_name("migration_report.json")
    mapping_path = output_path.with_name("field_mapping.json")

    report_payload = preview.to_dict()
    report_payload["output_summary"] = {
        "migrated_twb": _normalize_path(output_path),
        "report_json": _normalize_path(report_path),
        "mapping_json": _normalize_path(mapping_path),
    }
    report_payload["removable_datasources"] = preview.removable_datasources

    mapping_payload = {
        candidate.source_field: candidate.target_field
        for candidate in preview.candidate_field_mapping
    }
    report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    mapping_path.write_text(json.dumps(mapping_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return report_payload


def migrate_twb_guided(
    file_path: str | Path,
    target_source: str | Path,
    output_path: str | Path | None = None,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    apply_if_no_blockers: bool = True,
    use_ai_for_warnings: bool | None = None,
) -> dict[str, Any]:
    preview = preview_twb_migration(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        use_ai_for_warnings=use_ai_for_warnings,
    )
    payload = preview.to_dict()
    payload["workflow_status"] = "blocked" if preview.blocking_issue_count else "ready"
    payload["next_action"] = (
        "review_mapping_or_fix_blockers"
        if preview.blocking_issue_count
        else "apply_migration"
    )

    if preview.blocking_issue_count or not apply_if_no_blockers:
        return payload

    applied = apply_twb_migration(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        output_path=output_path,
        use_ai_for_warnings=use_ai_for_warnings,
    )
    payload.update(
        {
            "workflow_status": "applied",
            "next_action": "done",
            "output_summary": applied["output_summary"],
            "removable_datasources": applied["removable_datasources"],
        }
    )
    return payload


def profile_twb_for_migration_json(
    file_path: str | Path,
    scope: str = "workbook",
    target_source: str | Path | None = None,
) -> str:
    profile = profile_twb_for_migration(file_path=file_path, scope=scope, target_source=target_source)
    return json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)


def propose_field_mapping_json(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    use_ai_for_warnings: bool | None = None,
) -> str:
    payload = propose_field_mapping(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        use_ai_for_warnings=use_ai_for_warnings,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)


def preview_twb_migration_json(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    use_ai_for_warnings: bool | None = None,
) -> str:
    preview = preview_twb_migration(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        use_ai_for_warnings=use_ai_for_warnings,
    )
    return json.dumps(preview.to_dict(), ensure_ascii=False, indent=2)


def apply_twb_migration_json(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    output_path: str | Path | None = None,
    use_ai_for_warnings: bool | None = None,
) -> str:
    result = apply_twb_migration(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        output_path=output_path,
        use_ai_for_warnings=use_ai_for_warnings,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


def migrate_twb_guided_json(
    file_path: str | Path,
    target_source: str | Path,
    output_path: str | Path | None = None,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    apply_if_no_blockers: bool = True,
    use_ai_for_warnings: bool | None = None,
) -> str:
    payload = migrate_twb_guided(
        file_path=file_path,
        target_source=target_source,
        output_path=output_path,
        scope=scope,
        mapping_overrides=mapping_overrides,
        apply_if_no_blockers=apply_if_no_blockers,
        use_ai_for_warnings=use_ai_for_warnings,
    )
    return json.dumps(payload, ensure_ascii=False, indent=2)
