"""Explainable dashboard Gallery recommendations and layout materialization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml

from .config import GALLERY_DIR
from .dashboards import normalize_dashboard_layout, write_dashboard_layout_file

DashboardIntent = Literal[
    "overview",
    "comparison",
    "trend",
    "geographic",
    "detail",
    "filter-heavy",
]


@dataclass(frozen=True)
class DashboardRequirements:
    """Explicit features used to rank Gallery templates."""

    kpi_count: int = 0
    chart_count: int = 0
    filter_count: int = 0
    chart_types: tuple[str, ...] = ()
    has_temporal_data: bool = False
    has_geographic_data: bool = False
    primary_intent: DashboardIntent | None = None


@dataclass(frozen=True)
class GalleryTemplateSummary:
    name: str
    title: str
    description: str
    intents: tuple[str, ...]
    slots: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class GalleryRecommendation:
    template: str
    title: str
    score: int
    matched: tuple[str, ...]
    penalties: tuple[str, ...]
    hard_failures: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _validate_template(payload: dict[str, Any], path: Path) -> dict[str, Any]:
    required = {"schema_version", "name", "title", "description", "slots", "layout"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"Gallery template {path.name} is missing: {', '.join(missing)}")
    if payload["schema_version"] != 1:
        raise ValueError(f"Unsupported Gallery schema in {path.name}: {payload['schema_version']}")
    if not isinstance(payload["slots"], dict) or not isinstance(payload["layout"], dict):
        raise TypeError(f"Gallery template {path.name} has invalid slots or layout.")
    return payload


@lru_cache(maxsize=1)
def _load_templates() -> tuple[dict[str, Any], ...]:
    templates: list[dict[str, Any]] = []
    if not GALLERY_DIR.is_dir():
        raise FileNotFoundError(f"Packaged Gallery directory not found: {GALLERY_DIR}")
    for path in sorted(GALLERY_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as handle:
            payload = yaml.safe_load(handle)
        if not isinstance(payload, dict):
            raise TypeError(f"Gallery template {path.name} must contain an object.")
        templates.append(_validate_template(payload, path))
    if not templates:
        raise FileNotFoundError(f"No Gallery templates found in: {GALLERY_DIR}")
    names = [template["name"] for template in templates]
    if len(names) != len(set(names)):
        raise ValueError("Gallery template names must be unique.")
    return tuple(templates)


def list_gallery_templates() -> list[GalleryTemplateSummary]:
    """List packaged templates without applying or generating a dashboard."""

    return [
        GalleryTemplateSummary(
            name=template["name"],
            title=template["title"],
            description=template["description"],
            intents=tuple(template.get("intents", ())),
            slots=template["slots"],
        )
        for template in _load_templates()
    ]


def _range_score(
    label: str,
    value: int,
    preferred: list[int] | tuple[int, int] | None,
    matched: list[str],
    penalties: list[str],
) -> int:
    # Zero is the public API's "unspecified" default. Do not interpret an
    # omitted count as an explicit request for zero zones.
    if value == 0:
        return 0
    if not preferred or len(preferred) != 2:
        return 0
    low, high = int(preferred[0]), int(preferred[1])
    if low <= value <= high:
        matched.append(f"requested {value} {label} fits preferred range {low}-{high}")
        return 10
    distance = low - value if value < low else value - high
    penalties.append(f"requested {value} {label}; preferred range is {low}-{high}")
    return -min(15, 5 * distance)


def _score_template(
    template: dict[str, Any],
    requirements: DashboardRequirements,
) -> GalleryRecommendation | None:
    matched: list[str] = []
    penalties: list[str] = []
    hard_failures: list[str] = []
    required = template.get("requirements", {}) or {}
    if required.get("temporal") and not requirements.has_temporal_data:
        hard_failures.append("requires temporal data")
    if required.get("geographic") and not requirements.has_geographic_data:
        hard_failures.append("requires geographic data")
    if hard_failures:
        return None

    score = 0
    intents = set(template.get("intents", ()))
    if requirements.primary_intent:
        if requirements.primary_intent in intents:
            score += 40
            matched.append(f"primary intent is {requirements.primary_intent}")
        else:
            score -= 10
            penalties.append(
                f"primary intent {requirements.primary_intent} is not a native template intent"
            )

    preferences = template.get("preferences", {}) or {}
    if requirements.has_temporal_data and preferences.get("temporal"):
        score += 20
        matched.append("temporal data matches the template")
    if requirements.has_geographic_data and preferences.get("geographic"):
        score += 20
        matched.append("geographic data matches the template")
    score += _range_score(
        "KPIs", requirements.kpi_count, preferences.get("kpi_count"), matched, penalties
    )
    score += _range_score(
        "charts", requirements.chart_count, preferences.get("chart_count"), matched, penalties
    )
    score += _range_score(
        "filters", requirements.filter_count, preferences.get("filter_count"), matched, penalties
    )

    weights = {str(k).casefold(): int(v) for k, v in (preferences.get("chart_types") or {}).items()}
    chart_matches = [chart for chart in requirements.chart_types if chart.casefold() in weights]
    if chart_matches:
        chart_score = min(20, sum(weights[chart.casefold()] for chart in chart_matches))
        score += chart_score
        matched.append("preferred chart types: " + ", ".join(chart_matches))

    score += int(template.get("base_score", 0))
    return GalleryRecommendation(
        template=template["name"],
        title=template["title"],
        score=max(0, score),
        matched=tuple(matched),
        penalties=tuple(penalties),
        hard_failures=tuple(hard_failures),
    )


def recommend_gallery_templates(
    requirements: DashboardRequirements,
    *,
    limit: int = 3,
) -> list[GalleryRecommendation]:
    """Rank compatible Gallery templates with deterministic explanations."""

    if limit < 1:
        raise ValueError("limit must be at least 1")
    ranked: list[tuple[int, GalleryRecommendation]] = []
    for template in _load_templates():
        recommendation = _score_template(template, requirements)
        if recommendation is not None:
            ranked.append((int(template.get("priority", 100)), recommendation))
    ranked.sort(key=lambda item: (-item[1].score, item[0], item[1].template))
    return [recommendation for _, recommendation in ranked[:limit]]


def _worksheet_values(value: str | list[str] | tuple[str, ...], slot_name: str) -> list[str]:
    values = [value] if isinstance(value, str) else list(value)
    cleaned = [str(item).strip() for item in values if str(item).strip()]
    if not cleaned:
        raise ValueError(f"Gallery slot '{slot_name}' requires at least one worksheet name.")
    return cleaned


def _expand_slot(
    node: dict[str, Any],
    slot_specs: dict[str, dict[str, Any]],
    worksheet_slots: Mapping[str, str | list[str] | tuple[str, ...]],
) -> dict[str, Any]:
    slot_name = str(node.get("slot", ""))
    if slot_name not in slot_specs:
        raise ValueError(f"Layout references undefined Gallery slot '{slot_name}'.")
    if slot_name not in worksheet_slots:
        raise ValueError(f"Missing worksheet binding for Gallery slot '{slot_name}'.")
    spec = slot_specs[slot_name]
    values = _worksheet_values(worksheet_slots[slot_name], slot_name)
    minimum = int(spec.get("min", 1))
    maximum = int(spec.get("max", minimum))
    if not minimum <= len(values) <= maximum:
        raise ValueError(
            f"Gallery slot '{slot_name}' accepts {minimum}-{maximum} worksheet(s); "
            f"received {len(values)}."
        )
    mode = spec.get("mode", "single")
    worksheet_nodes = [{"type": "worksheet", "name": name} for name in values]
    sizing = {key: node[key] for key in ("fixed_size", "weight") if key in node}
    if mode == "single":
        result = worksheet_nodes[0]
        result.update(sizing)
        return result
    if mode == "grid-2x2":
        rows = [
            {
                "type": "container",
                "direction": "horizontal",
                "children": worksheet_nodes[index:index + 2],
            }
            for index in range(0, len(worksheet_nodes), 2)
        ]
        result = {"type": "container", "direction": "vertical", "children": rows}
        result.update(sizing)
        return result
    if mode not in {"horizontal", "vertical"}:
        raise ValueError(f"Unsupported Gallery slot mode '{mode}' for '{slot_name}'.")
    result = {"type": "container", "direction": mode, "children": worksheet_nodes}
    result.update(sizing)
    return result


def _materialize_node(
    node: dict[str, Any],
    slot_specs: dict[str, dict[str, Any]],
    worksheet_slots: Mapping[str, str | list[str] | tuple[str, ...]],
) -> dict[str, Any]:
    if node.get("type") == "slot":
        return _expand_slot(node, slot_specs, worksheet_slots)
    result = dict(node)
    if "children" in result:
        result["children"] = [
            _materialize_node(child, slot_specs, worksheet_slots)
            for child in result["children"]
        ]
    return result


def materialize_gallery_layout(
    template_name: str,
    *,
    worksheet_slots: Mapping[str, str | list[str] | tuple[str, ...]],
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Bind exact worksheet names to a Gallery template's canonical layout."""

    template = next(
        (item for item in _load_templates() if item["name"] == template_name),
        None,
    )
    if template is None:
        available = ", ".join(item["name"] for item in _load_templates())
        raise ValueError(f"Unknown Gallery template '{template_name}'. Available: {available}")
    slot_specs = template["slots"]
    unknown_slots = sorted(set(worksheet_slots) - set(slot_specs))
    if unknown_slots:
        raise ValueError("Unknown Gallery worksheet slots: " + ", ".join(unknown_slots))
    layout = normalize_dashboard_layout(
        _materialize_node(template["layout"], slot_specs, worksheet_slots)
    )
    result: dict[str, Any] = {
        "template": template_name,
        "layout_schema": layout,
        "worksheet_slots": {key: value for key, value in worksheet_slots.items()},
    }
    if output_path is not None:
        path = write_dashboard_layout_file(output_path, layout)
        result["output_path"] = str(path.absolute())
    return result
