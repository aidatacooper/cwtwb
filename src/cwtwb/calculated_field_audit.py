"""Audit and explicitly repair calculated-field metadata semantics."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import asdict, dataclass
from typing import Literal

from lxml import etree

STRING_LIKE_DATATYPES = frozenset({"string", "boolean", "nominal"})
STRING_MEASURE_CODE = "CF_STRING_MEASURE"


@dataclass(frozen=True)
class CalculatedFieldIssue:
    """One evidence-backed calculated-field metadata inconsistency."""

    code: str
    datasource_name: str
    field_name: str
    internal_name: str
    datatype: str
    role: str
    field_type: str
    severity: Literal["error", "warning"]
    reason: str
    proposed_changes: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CalculatedFieldChange:
    """Before/after metadata for one applied or proposed repair."""

    datasource_name: str
    field_name: str
    internal_name: str
    before: dict[str, str]
    after: dict[str, str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class CalculatedFieldRepairResult:
    """Structured result for a dry-run or applied semantic repair."""

    dry_run: bool
    mutated: bool
    issues: tuple[CalculatedFieldIssue, ...]
    changes: tuple[CalculatedFieldChange, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "dry_run": self.dry_run,
            "mutated": self.mutated,
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
            "changes": [change.to_dict() for change in self.changes],
        }


def _datasource_label(datasource: etree._Element) -> str:
    return datasource.get("caption") or datasource.get("name") or "(unnamed datasource)"


def audit_calculated_fields(root: etree._Element) -> list[CalculatedFieldIssue]:
    """Find known datatype/role contradictions without mutating the workbook."""

    issues: list[CalculatedFieldIssue] = []
    for datasource in root.findall("./datasources/datasource"):
        datasource_name = _datasource_label(datasource)
        for column in datasource.findall("./column"):
            if column.find("calculation") is None:
                continue
            datatype = (column.get("datatype") or "").lower()
            role = (column.get("role") or "").lower()
            field_type = (column.get("type") or "").lower()
            if datatype not in STRING_LIKE_DATATYPES or role != "measure":
                continue
            issues.append(
                CalculatedFieldIssue(
                    code=STRING_MEASURE_CODE,
                    datasource_name=datasource_name,
                    field_name=column.get("caption") or column.get("name", "").strip("[]"),
                    internal_name=column.get("name", ""),
                    datatype=datatype,
                    role=role,
                    field_type=field_type,
                    severity="error",
                    reason=(
                        "String-like calculated fields cannot be meaningfully aggregated as "
                        "measures and may appear broken in Tableau."
                    ),
                    proposed_changes={"role": "dimension", "type": "nominal"},
                )
            )
    return issues


def repair_calculated_field_issues(
    root: etree._Element,
    *,
    issue_codes: Collection[str] | None = None,
    field_names: Collection[str] | None = None,
    datasource_names: Collection[str] | None = None,
    dry_run: bool = True,
) -> CalculatedFieldRepairResult:
    """Repair selected known issues, defaulting to a non-mutating dry-run."""

    allowed_codes = set(issue_codes or {STRING_MEASURE_CODE})
    allowed_fields = set(field_names or ())
    allowed_datasources = set(datasource_names or ())
    selected = [
        issue
        for issue in audit_calculated_fields(root)
        if issue.code in allowed_codes
        and (not allowed_fields or issue.field_name in allowed_fields or issue.internal_name in allowed_fields)
        and (not allowed_datasources or issue.datasource_name in allowed_datasources)
    ]
    selected_keys = {
        (issue.datasource_name, issue.internal_name, issue.code)
        for issue in selected
    }
    changes: list[CalculatedFieldChange] = []
    for datasource in root.findall("./datasources/datasource"):
        datasource_name = _datasource_label(datasource)
        for column in datasource.findall("./column"):
            key = (datasource_name, column.get("name", ""), STRING_MEASURE_CODE)
            if key not in selected_keys:
                continue
            before = {
                "role": column.get("role", ""),
                "type": column.get("type", ""),
            }
            after = {"role": "dimension", "type": "nominal"}
            changes.append(
                CalculatedFieldChange(
                    datasource_name=datasource_name,
                    field_name=column.get("caption") or column.get("name", "").strip("[]"),
                    internal_name=column.get("name", ""),
                    before=before,
                    after=after,
                )
            )
            if not dry_run:
                column.set("role", after["role"])
                column.set("type", after["type"])

    return CalculatedFieldRepairResult(
        dry_run=dry_run,
        mutated=bool(changes) and not dry_run,
        issues=tuple(selected),
        changes=tuple(changes),
    )
