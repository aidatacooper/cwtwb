"""Workbook migration helpers for reusing TWB templates with a new datasource."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree
import xlrd

from .twb_analyzer import analyze_workbook


DEFAULT_BILINGUAL_FIELD_MAPPING: dict[str, str] = {
    "Row ID": "行 ID",
    "Order ID": "订单 ID",
    "Order Date": "订单日期",
    "Ship Date": "发货日期",
    "Ship Mode": "装运模式",
    "Customer ID": "客户 ID",
    "Customer Name": "客户名称",
    "Segment": "细分",
    "Country/Region": "国家/地区",
    "City": "城市",
    "State/Province": "省/自治区",
    "Postal Code": "邮政编码",
    "Region": "区域",
    "Product ID": "产品 ID",
    "Category": "类别",
    "Sub-Category": "子类别",
    "Product Name": "产品名称",
    "Sales": "销售额",
    "Quantity": "数量",
    "Discount": "折扣",
    "Profit": "利润",
}


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
    candidate_field_mapping: list[MappingCandidate]
    calculation_rewrite_summary: dict[str, int]
    issues: list[MigrationIssue] = field(default_factory=list)
    removable_datasources: list[str] = field(default_factory=list)
    capability_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def blocking_issue_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "blocking")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blocking_issue_count"] = self.blocking_issue_count
        return payload


def _normalize_path(path: str | Path) -> str:
    return str(Path(path).resolve()).replace("\\", "/")


def _read_excel_headers(path: str | Path) -> dict[str, Any]:
    workbook = xlrd.open_workbook(_normalize_path(path))
    sheet = workbook.sheet_by_index(0)
    headers = [str(value).strip() for value in sheet.row_values(0) if str(value).strip()]
    return {
        "sheet_name": sheet.name,
        "headers": headers,
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


def _find_target_datasource(root: etree._Element, target_source: str | Path) -> etree._Element | None:
    target_name = Path(target_source).name.casefold()
    normalized_target = _normalize_path(target_source).casefold()
    for datasource in _top_level_datasources(root):
        for conn in datasource.findall(".//connection[@class='excel-direct']"):
            filename = (conn.get("filename") or "").replace("\\", "/")
            if Path(filename).name.casefold() == target_name or filename.casefold() == normalized_target:
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


def _find_source_datasource_name(root: etree._Element, target_datasource_name: str, scope: str) -> str:
    usage_count: dict[str, int] = {}
    for worksheet in _collect_scope_worksheets(root, scope):
        for datasource_name in _worksheet_datasource_names(worksheet):
            usage_count[datasource_name] = usage_count.get(datasource_name, 0) + 1

    ranked = sorted(
        ((name, count) for name, count in usage_count.items() if name != target_datasource_name),
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
    info = _read_excel_headers(target_source)
    info["target_source"] = _normalize_path(target_source)
    return info


def _build_candidate_mapping(
    source_fields: dict[str, str],
    target_fields: dict[str, str],
    mapping_overrides: dict[str, str] | None = None,
) -> tuple[list[MappingCandidate], list[MigrationIssue]]:
    overrides = mapping_overrides or {}
    issues: list[MigrationIssue] = []
    candidates: list[MappingCandidate] = []
    for source_field, default_target in DEFAULT_BILINGUAL_FIELD_MAPPING.items():
        if source_field not in source_fields:
            continue
        target_field = overrides.get(source_field, default_target)
        if target_field not in target_fields:
            issues.append(
                MigrationIssue(
                    issue_type="unmapped",
                    severity="blocking",
                    message=f"Target datasource is missing mapped field '{target_field}' for source field '{source_field}'.",
                    field=source_field,
                )
            )
            continue
        reason = "override mapping" if source_field in overrides else "built-in bilingual alias"
        candidates.append(
            MappingCandidate(
                source_field=source_field,
                target_field=target_field,
                confidence=1.0,
                reason=reason,
            )
        )
    return candidates, issues


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
) -> MigrationPreview:
    path = Path(file_path)
    root = etree.parse(str(path)).getroot()

    target_datasource = _find_target_datasource(root, target_source)
    if target_datasource is None:
        raise ValueError(f"Could not find a workbook datasource for target source: {target_source}")

    target_fields = _get_datasource_fields(target_datasource)
    scope_worksheets = _collect_scope_worksheets(root, scope)
    worksheet_names = [worksheet.get("name", "") for worksheet in scope_worksheets]
    source_datasource_name = _find_source_datasource_name(root, target_datasource.get("name", ""), scope)
    source_datasource = _get_datasource_by_name(root, source_datasource_name)
    if source_datasource is None:
        raise ValueError(f"Could not locate source datasource '{source_datasource_name}' in workbook.")

    source_fields = _get_datasource_fields(source_datasource)
    candidates, issues = _build_candidate_mapping(source_fields, target_fields, mapping_overrides)
    dashboards = _collect_dashboards_for_worksheets(root, set(worksheet_names))
    used_datasources = sorted(
        {
            datasource_name
            for worksheet in scope_worksheets
            for datasource_name in _worksheet_datasource_names(worksheet)
        }
    )

    capability_report = analyze_workbook(path)
    preview = MigrationPreview(
        template_file=_normalize_path(path),
        target_source=_normalize_path(target_source),
        source_datasource=source_datasource_name,
        source_datasource_caption=source_datasource.get("caption"),
        target_datasource=target_datasource.get("name", ""),
        target_datasource_caption=target_datasource.get("caption"),
        scope=scope,
        worksheets_in_scope=worksheet_names,
        dashboards_in_scope=dashboards,
        used_datasources=used_datasources,
        candidate_field_mapping=candidates,
        calculation_rewrite_summary=_calculation_summary(scope_worksheets),
        issues=issues,
        removable_datasources=[source_datasource_name],
        capability_summary={
            "fit_level": capability_report.fit_level,
            "summary": capability_report.summary,
        },
    )
    return preview


def _build_string_replacements(
    preview: MigrationPreview,
    target_field_locals: dict[str, str],
) -> dict[str, str]:
    replacements = {
        preview.source_datasource: preview.target_datasource,
        f"[{preview.source_datasource}].": f"[{preview.target_datasource}].",
    }
    for candidate in preview.candidate_field_mapping:
        source_local = f"[{candidate.source_field}]"
        target_local = target_field_locals[candidate.target_field]
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


def apply_twb_migration(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    preview = preview_twb_migration(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
    )
    if preview.blocking_issue_count:
        raise ValueError(
            f"Cannot apply migration while blocking issues remain ({preview.blocking_issue_count})."
        )

    path = Path(file_path)
    tree = etree.parse(str(path))
    root = tree.getroot()
    target_datasource = _get_datasource_by_name(root, preview.target_datasource)
    if target_datasource is None:
        raise ValueError(f"Target datasource '{preview.target_datasource}' not found during apply.")

    target_field_locals = _get_datasource_fields(target_datasource)
    replacements = _build_string_replacements(preview, target_field_locals)
    _replace_in_sections(root, replacements)

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


def preview_twb_migration_json(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
) -> str:
    preview = preview_twb_migration(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
    )
    return json.dumps(preview.to_dict(), ensure_ascii=False, indent=2)


def apply_twb_migration_json(
    file_path: str | Path,
    target_source: str | Path,
    scope: str = "workbook",
    mapping_overrides: dict[str, str] | None = None,
    output_path: str | Path | None = None,
) -> str:
    result = apply_twb_migration(
        file_path=file_path,
        target_source=target_source,
        scope=scope,
        mapping_overrides=mapping_overrides,
        output_path=output_path,
    )
    return json.dumps(result, ensure_ascii=False, indent=2)
