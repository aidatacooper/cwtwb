"""Helpers for reviewing dashboard authoring contracts.

The MCP server does not generate authoring plans from free text. Instead it
provides a stable contract template plus a lightweight review/defaulting pass
that external agents can use before calling the workbook tools.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import CONTRACTS_DIR, iter_profile_files


DEFAULT_CONTRACT_TEMPLATE = CONTRACTS_DIR / "dashboard_authoring_v1.json"
RECOMMENDED_SKILLS = [
    "authoring_workflow",
    "calculation_builder",
    "chart_builder",
    "dashboard_designer",
    "formatting",
]


@dataclass
class ContractReviewResult:
    """Structured result returned by the contract review tool."""

    valid: bool
    summary: str
    missing_required: list[str]
    defaults_applied: dict[str, Any]
    clarification_questions: list[str]
    recommended_skills: list[str]
    execution_outline: list[str]
    normalized_contract: dict[str, Any]
    detected_profile: str | None = None
    parse_error: str | None = None

    def to_json(self) -> str:
        """Render the full review result as formatted JSON."""

        payload = {
            "valid": self.valid,
            "summary": self.summary,
            "missing_required": self.missing_required,
            "defaults_applied": self.defaults_applied,
            "clarification_questions": self.clarification_questions,
            "recommended_skills": self.recommended_skills,
            "execution_outline": self.execution_outline,
            "normalized_contract": self.normalized_contract,
            "detected_profile": self.detected_profile,
        }
        if self.parse_error:
            payload["parse_error"] = self.parse_error
        return json.dumps(payload, indent=2, ensure_ascii=False)


def _read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _load_base_contract_template() -> dict[str, Any]:
    if not DEFAULT_CONTRACT_TEMPLATE.exists():
        raise FileNotFoundError(
            f"Contract template not found: {DEFAULT_CONTRACT_TEMPLATE}"
        )
    return _read_json_file(DEFAULT_CONTRACT_TEMPLATE)


def _iter_profile_payloads() -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for path in iter_profile_files():
        payload = _read_json_file(path)
        payload["_path"] = str(path)
        payloads.append(payload)
    return payloads


def _normalize_token(value: str) -> str:
    return " ".join(value.strip().casefold().replace("_", " ").replace("-", " ").split())


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


def _ensure_dict(parent: dict[str, Any], key: str, defaults_applied: dict[str, Any]) -> dict[str, Any]:
    value = parent.get(key)
    if isinstance(value, dict):
        return value
    parent[key] = {}
    defaults_applied[key] = {}
    return parent[key]


def _set_if_blank(
    parent: dict[str, Any],
    key: str,
    value: Any,
    defaults_applied: dict[str, Any],
    *,
    path: str,
) -> None:
    if _is_blank(parent.get(key)):
        parent[key] = deepcopy(value)
        defaults_applied[path] = deepcopy(value)


def _merge_profile_defaults(
    contract: dict[str, Any],
    profile_defaults: dict[str, Any],
    defaults_applied: dict[str, Any],
    *,
    prefix: str = "",
) -> None:
    for key, value in profile_defaults.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            child = _ensure_dict(contract, key, defaults_applied)
            _merge_profile_defaults(child, value, defaults_applied, prefix=path)
            continue
        _set_if_blank(contract, key, value, defaults_applied, path=path)


def _extract_available_fields(contract: dict[str, Any]) -> list[str]:
    raw_fields = contract.get("available_fields", [])
    if not isinstance(raw_fields, list):
        return []
    return [field for field in raw_fields if isinstance(field, str) and field.strip()]


def _find_matching_profile(contract: dict[str, Any]) -> dict[str, Any] | None:
    explicit_profile = contract.get("dataset_profile")
    dataset_name = contract.get("dataset")
    available_fields = {
        _normalize_token(field)
        for field in _extract_available_fields(contract)
    }

    for profile in _iter_profile_payloads():
        profile_id = str(profile.get("id", "")).strip()
        aliases = [_normalize_token(alias) for alias in profile.get("aliases", []) if isinstance(alias, str)]

        if isinstance(explicit_profile, str) and profile_id and _normalize_token(explicit_profile) == _normalize_token(profile_id):
            return profile

        if isinstance(dataset_name, str) and dataset_name.strip():
            normalized_dataset = _normalize_token(dataset_name)
            if normalized_dataset == _normalize_token(profile_id) or normalized_dataset in aliases:
                return profile

        required_fields = {
            _normalize_token(field)
            for field in profile.get("match", {}).get("fields_all_of", [])
            if isinstance(field, str)
        }
        if required_fields and required_fields.issubset(available_fields):
            return profile

    return None


def _build_execution_outline(contract: dict[str, Any], profile_label: str | None) -> list[str]:
    dashboard_name = contract.get("dashboard", {}).get("name") or "Analytical Dashboard"
    dataset_name = contract.get("dataset") or "the active dataset"
    profile_note = f" using profile '{profile_label}'" if profile_label else ""
    return [
        "Read resource: cwtwb://contracts/dashboard_authoring_v1",
        "Optionally inspect cwtwb://profiles/index and a matching dataset profile",
        "Review the draft contract with review_authoring_contract(contract_json)",
        "Read skill: cwtwb://skills/authoring_workflow",
        "Read phase skills in order: calculation_builder -> chart_builder -> dashboard_designer -> formatting",
        f"Create a workbook for {dataset_name}{profile_note} and register any calculated fields first",
        "Build worksheets from the contract questions and mark types",
        f"Assemble dashboard '{dashboard_name}' and apply actions/captions",
        "Validate the workbook and inspect capability fit before saving",
    ]


def review_authoring_contract_payload(contract_json: str) -> ContractReviewResult:
    """Review a contract JSON string and return a normalized, defaulted result."""

    try:
        parsed = json.loads(contract_json)
    except json.JSONDecodeError as exc:
        return ContractReviewResult(
            valid=False,
            summary="Contract JSON could not be parsed. Fix the JSON syntax before continuing.",
            missing_required=["contract_json"],
            defaults_applied={},
            clarification_questions=[],
            recommended_skills=RECOMMENDED_SKILLS,
            execution_outline=[],
            normalized_contract={},
            parse_error=str(exc),
        )

    if not isinstance(parsed, dict):
        return ContractReviewResult(
            valid=False,
            summary="Contract must be a JSON object at the top level.",
            missing_required=["contract_json"],
            defaults_applied={},
            clarification_questions=[],
            recommended_skills=RECOMMENDED_SKILLS,
            execution_outline=[],
            normalized_contract={},
            parse_error="Top-level JSON value must be an object.",
        )

    contract = deepcopy(_load_base_contract_template())
    defaults_applied: dict[str, Any] = {}

    for key, value in parsed.items():
        contract[key] = value

    _set_if_blank(contract, "dataset", "", defaults_applied, path="dataset")
    _set_if_blank(contract, "dataset_profile", "", defaults_applied, path="dataset_profile")
    _set_if_blank(contract, "available_fields", [], defaults_applied, path="available_fields")
    _set_if_blank(contract, "worksheets", [], defaults_applied, path="worksheets")
    _set_if_blank(contract, "actions", [], defaults_applied, path="actions")

    profile = _find_matching_profile(contract)
    detected_profile = None
    if profile is not None:
        detected_profile = str(profile.get("id", "")).strip() or None
        profile_defaults = profile.get("defaults", {})
        if isinstance(profile_defaults, dict):
            _merge_profile_defaults(contract, profile_defaults, defaults_applied)

    constraints = _ensure_dict(contract, "constraints", defaults_applied)
    _set_if_blank(
        constraints,
        "max_dashboards",
        1,
        defaults_applied,
        path="constraints.max_dashboards",
    )
    _set_if_blank(
        constraints,
        "allowed_support_levels",
        ["core", "advanced"],
        defaults_applied,
        path="constraints.allowed_support_levels",
    )
    _set_if_blank(
        constraints,
        "layout_pattern",
        "executive overview",
        defaults_applied,
        path="constraints.layout_pattern",
    )
    _set_if_blank(constraints, "kpis", [], defaults_applied, path="constraints.kpis")
    _set_if_blank(constraints, "filters", [], defaults_applied, path="constraints.filters")
    _set_if_blank(
        constraints,
        "interaction_pattern",
        "",
        defaults_applied,
        path="constraints.interaction_pattern",
    )

    dashboard = _ensure_dict(contract, "dashboard", defaults_applied)
    _set_if_blank(dashboard, "name", "Analytical Dashboard", defaults_applied, path="dashboard.name")
    _set_if_blank(
        dashboard,
        "layout_pattern",
        contract.get("constraints", {}).get("layout_pattern", "executive overview"),
        defaults_applied,
        path="dashboard.layout_pattern",
    )

    missing_required: list[str] = []
    clarification_questions: list[str] = []

    if _is_blank(contract.get("goal")):
        missing_required.append("goal")
        clarification_questions.append("What is the main business goal of this dashboard?")
    if _is_blank(contract.get("audience")):
        missing_required.append("audience")
        clarification_questions.append("Who is the primary audience for this dashboard?")
    if _is_blank(contract.get("primary_question")):
        missing_required.append("primary_question")
        clarification_questions.append("What is the primary analytical question this dashboard must answer?")
    if contract.get("require_interaction") is None:
        missing_required.append("require_interaction")
        clarification_questions.append("Do you want interactive drill-down or filtering actions in the dashboard?")

    clarification_questions = clarification_questions[:3]
    valid = not clarification_questions

    profile_label = None
    if profile is not None:
        profile_label = str(profile.get("label", "")).strip() or detected_profile

    if valid:
        summary = (
            "Contract is ready for execution. "
            + (
                f"Profile '{profile_label}' was applied to enrich defaults."
                if profile_label
                else "No dataset profile was applied; generic defaults were kept."
            )
        )
    else:
        summary = (
            "Contract needs lightweight clarification before execution. "
            + (
                f"Profile '{profile_label}' supplied dataset-aware defaults."
                if profile_label
                else "Generic defaults were applied because no dataset profile matched yet."
            )
        )

    return ContractReviewResult(
        valid=valid,
        summary=summary,
        missing_required=missing_required,
        defaults_applied=defaults_applied,
        clarification_questions=clarification_questions,
        recommended_skills=RECOMMENDED_SKILLS,
        execution_outline=_build_execution_outline(contract, profile_label),
        normalized_contract=contract,
        detected_profile=detected_profile,
    )
