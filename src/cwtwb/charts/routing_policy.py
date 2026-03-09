"""Capability-aware routing policy for chart requests.

This module makes the internal distinction between core primitives, advanced
patterns, and recipe compatibility paths explicit without changing the public
API surface.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..capability_registry import CapabilityLevel, get_capability
from .pattern_mapping import normalize_chart_pattern


@dataclass(frozen=True)
class ChartRouteProfile:
    """Resolved routing profile for a chart request."""

    requested_mark_type: str
    actual_mark_type: str
    support_level: CapabilityLevel | None
    route_family: str
    builder_name: str


def _resolve_support_level(mark_type: str) -> CapabilityLevel | None:
    spec = get_capability("chart", mark_type)
    return None if spec is None else spec.level


def profile_chart_request(mark_type: str) -> ChartRouteProfile:
    """Classify a chart request without changing compatibility behavior."""

    if mark_type == "Pie":
        return ChartRouteProfile(
            requested_mark_type=mark_type,
            actual_mark_type="Pie",
            support_level=_resolve_support_level(mark_type),
            route_family="primitive",
            builder_name="pie",
        )

    if mark_type == "Map":
        return ChartRouteProfile(
            requested_mark_type=mark_type,
            actual_mark_type="Map",
            support_level=_resolve_support_level(mark_type),
            route_family="primitive",
            builder_name="map",
        )

    normalized = normalize_chart_pattern(mark_type)
    support_level = _resolve_support_level(mark_type)

    if support_level == "advanced":
        route_family = "pattern"
    elif support_level == "recipe":
        route_family = "compatibility"
    else:
        route_family = "primitive"

    return ChartRouteProfile(
        requested_mark_type=mark_type,
        actual_mark_type=normalized.actual_mark_type,
        support_level=support_level,
        route_family=route_family,
        builder_name="basic",
    )


def profile_dual_axis_request() -> ChartRouteProfile:
    """Classify the dual-axis path as an advanced composition route."""

    return ChartRouteProfile(
        requested_mark_type="Dual Axis",
        actual_mark_type="Dual Axis",
        support_level=_resolve_support_level("Dual Axis"),
        route_family="composition",
        builder_name="dual_axis",
    )
