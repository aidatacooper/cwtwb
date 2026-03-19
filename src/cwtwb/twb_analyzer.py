"""Read-only capability analysis for existing Tableau workbooks.

The analyzer parses a TWB file and maps detected XML features to cwtwb's
capability registry (core/advanced/recipe/unsupported). It is used by MCP
tools to judge template fit, surface migration risks, and explain why a
workbook is or is not a good support target.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from lxml import etree

from .capability_registry import CapabilityKind, CapabilityLevel, get_capability


TemplateFit = Literal["core-fit", "advanced-fit", "recipe-heavy", "unsupported-fit"]


@dataclass
class DetectedCapability:
    """A capability observed in a TWB file."""

    kind: str
    raw_name: str
    canonical: str | None
    level: CapabilityLevel | None
    source: str
    occurrences: int = 1
    xpath_hints: tuple[str, ...] = ()


@dataclass
class AnalysisReport:
    """Aggregated TWB capability analysis output."""

    file_path: str
    detected: list[DetectedCapability] = field(default_factory=list)
    unknown: list[DetectedCapability] = field(default_factory=list)

    @property
    def summary(self) -> dict[str, int]:
        """Return aggregated counts by support level plus unknown capabilities."""
        counts = {"core": 0, "advanced": 0, "recipe": 0, "unsupported": 0, "unknown": 0}
        for item in self.detected:
            if item.level is not None:
                counts[item.level] += 1
        counts["unknown"] = len(self.unknown)
        return counts

    @property
    def fit_level(self) -> TemplateFit:
        """Classify template fit quality from detected capability tiers."""
        summary = self.summary
        if summary["recipe"] > 0:
            return "recipe-heavy"
        if summary["advanced"] > 0:
            return "advanced-fit"
        if summary["unsupported"] > 0 or summary["unknown"] > 0:
            return "unsupported-fit"
        return "core-fit"

    @property
    def non_core_detected(self) -> list[DetectedCapability]:
        """Return detected capabilities outside the core support tier."""
        return [item for item in self.detected if item.level in {"advanced", "recipe", "unsupported"}]

    @property
    def gap_items(self) -> list[DetectedCapability]:
        """Return all capabilities that require migration/design attention."""
        return self.non_core_detected + self.unknown

    def _format_items(self, level: str) -> list[str]:
        """Format one support-level block for text rendering."""
        items = [item for item in self.detected if item.level == level]
        if not items:
            return []
        lines = [f"[{level}]"]
        for item in items:
            lines.append(
                f"- {item.kind}: {item.canonical} "
                f"(source={item.source}, count={item.occurrences})"
            )
        return lines

    def to_text(self) -> str:
        """Render the report as concise text for MCP responses."""

        lines = [f"TWB analysis: {self.file_path}", ""]
        summary = self.summary
        lines.append(f"Template fit: {self.fit_level}")
        lines.append(
            "Summary: "
            f"core={summary['core']}, "
            f"advanced={summary['advanced']}, "
            f"recipe={summary['recipe']}, "
            f"unsupported={summary['unsupported']}, "
            f"unknown={summary['unknown']}"
        )
        for level in ("core", "advanced", "recipe", "unsupported"):
            block = self._format_items(level)
            if block:
                lines.append("")
                lines.extend(block)
        if self.unknown:
            lines.append("")
            lines.append("[unknown]")
            for item in self.unknown:
                lines.append(
                    f"- {item.kind}: {item.raw_name} "
                    f"(source={item.source}, count={item.occurrences})"
                )
        return "\n".join(lines)

    def to_gap_text(self) -> str:
        """Render a decision-oriented gap summary for template triage."""

        summary = self.summary
        lines = [f"Capability gap: {self.file_path}", ""]
        lines.append(f"Template fit: {self.fit_level}")
        lines.append(
            "Decision summary: "
            f"core={summary['core']}, "
            f"advanced={summary['advanced']}, "
            f"recipe={summary['recipe']}, "
            f"unsupported={summary['unsupported']}, "
            f"unknown={summary['unknown']}"
        )

        if not self.gap_items:
            lines.append("All detected capabilities are core. This template fits the stable surface area.")
            return "\n".join(lines)

        advanced = [item for item in self.detected if item.level == "advanced"]
        recipe = [item for item in self.detected if item.level == "recipe"]
        unsupported = [item for item in self.detected if item.level == "unsupported"]

        if advanced:
            lines.append("")
            lines.append("[advanced]")
            for item in advanced:
                lines.append(f"- {item.kind}: {item.canonical}")

        if recipe:
            lines.append("")
            lines.append("[recipe-only]")
            for item in recipe:
                lines.append(f"- {item.kind}: {item.canonical}")

        if unsupported:
            lines.append("")
            lines.append("[unsupported]")
            for item in unsupported:
                lines.append(f"- {item.kind}: {item.canonical}")

        if self.unknown:
            lines.append("")
            lines.append("[unknown]")
            for item in self.unknown:
                lines.append(f"- {item.kind}: {item.raw_name}")

        lines.append("")
        lines.append("Recommendation:")
        if unsupported or self.unknown:
            lines.append("- Do not treat this template as a direct support target. Keep unsupported or unknown parts outside the core API.")
        if recipe:
            lines.append("- Treat recipe-only items as examples or helper scripts, not first-class SDK promises.")
        if advanced:
            lines.append("- Keep advanced items behind explicit APIs or documentation, not the default happy path.")
        return "\n".join(lines)


class TWBAnalyzer:
    """Inspect a TWB file and map observed features onto cwtwb capabilities."""

    def analyze(self, file_path: str | Path) -> AnalysisReport:
        """Run all detectors and return a normalized analysis report."""
        path = Path(file_path)
        tree = etree.parse(str(path))
        root = tree.getroot()

        detected: dict[tuple[str, str, str], DetectedCapability] = {}
        unknown: dict[tuple[str, str, str], DetectedCapability] = {}

        self._detect_charts(root, detected, unknown)
        self._detect_encodings(root, detected, unknown)
        self._detect_dashboard_zones(root, detected, unknown)
        self._detect_actions(root, detected, unknown)
        self._detect_connections(root, detected, unknown)
        self._detect_unsupported_features(root, detected, unknown)

        return AnalysisReport(
            file_path=str(path),
            detected=sorted(
                detected.values(),
                key=lambda item: (item.level or "zzz", item.kind, item.canonical or item.raw_name),
            ),
            unknown=sorted(
                unknown.values(),
                key=lambda item: (item.kind, item.raw_name),
            ),
        )

    def _record_detection(
        self,
        bucket: dict[tuple[str, str, str], DetectedCapability],
        *,
        kind: str,
        raw_name: str,
        canonical: str | None,
        level: CapabilityLevel | None,
        source: str,
        xpath_hint: str,
    ) -> None:
        """Upsert a detected capability and accumulate occurrence metadata."""
        key = (kind, canonical or raw_name, source)
        current = bucket.get(key)
        if current is None:
            bucket[key] = DetectedCapability(
                kind=kind,
                raw_name=raw_name,
                canonical=canonical,
                level=level,
                source=source,
                xpath_hints=(xpath_hint,),
            )
            return

        hints = current.xpath_hints
        if xpath_hint and xpath_hint not in hints:
            hints = hints + (xpath_hint,)
        current.occurrences += 1
        current.xpath_hints = hints

    def _resolve_and_record(
        self,
        bucket: dict[tuple[str, str, str], DetectedCapability],
        unknown: dict[tuple[str, str, str], DetectedCapability],
        *,
        kind: CapabilityKind,
        raw_name: str,
        source: str,
        xpath_hint: str,
    ) -> None:
        """Resolve capability metadata from registry and record into target buckets."""
        spec = get_capability(kind, raw_name)
        if spec is None:
            self._record_detection(
                unknown,
                kind=kind,
                raw_name=raw_name,
                canonical=None,
                level=None,
                source=source,
                xpath_hint=xpath_hint,
            )
            return

        self._record_detection(
            bucket,
            kind=kind,
            raw_name=raw_name,
            canonical=spec.canonical,
            level=spec.level,
            source=source,
            xpath_hint=xpath_hint,
        )

    def _detect_charts(
        self,
        root: etree._Element,
        detected: dict[tuple[str, str, str], DetectedCapability],
        unknown: dict[tuple[str, str, str], DetectedCapability],
    ) -> None:
        """Detect chart marks/patterns from worksheet pane and naming hints."""
        for worksheet in root.findall(".//worksheet"):
            worksheet_name = worksheet.get("name", "<unnamed>")
            xpath_hint = f".//worksheet[@name='{worksheet_name}']"
            table = worksheet.find("table")
            if table is None:
                continue

            for mark in table.findall(".//pane/mark"):
                raw_class = mark.get("class", "")
                if not raw_class or raw_class == "Automatic":
                    continue
                self._resolve_and_record(
                    detected,
                    unknown,
                    kind="chart",
                    raw_name=raw_class,
                    source="pane-mark",
                    xpath_hint=xpath_hint,
                )

            panes = table.find("panes")
            if panes is not None and len(panes.findall("pane")) > 1:
                self._resolve_and_record(
                    detected,
                    unknown,
                    kind="chart",
                    raw_name="Dual Axis",
                    source="multi-pane",
                    xpath_hint=xpath_hint,
                )

            self._resolve_chart_name_patterns(worksheet_name, xpath_hint, detected, unknown)

    def _resolve_chart_name_patterns(
        self,
        worksheet_name: str,
        xpath_hint: str,
        detected: dict[tuple[str, str, str], DetectedCapability],
        unknown: dict[tuple[str, str, str], DetectedCapability],
    ) -> None:
        """Detect recipe-like chart patterns inferred from worksheet names."""
        for name in (
            "Donut Chart",
            "Lollipop Chart",
            "Bullet Chart",
            "Bump Chart",
            "Butterfly Chart",
            "Calendar Chart",
            "Scatterplot",
            "Heatmap",
            "Tree Map",
            "Bubble Chart",
        ):
            if worksheet_name.casefold() == name.casefold():
                self._resolve_and_record(
                    detected,
                    unknown,
                    kind="chart",
                    raw_name=name,
                    source="worksheet-name",
                    xpath_hint=xpath_hint,
                )

    def _detect_encodings(
        self,
        root: etree._Element,
        detected: dict[tuple[str, str, str], DetectedCapability],
        unknown: dict[tuple[str, str, str], DetectedCapability],
    ) -> None:
        """Detect encoding channels declared under worksheet panes."""
        for encoding in root.findall(".//encodings/*"):
            raw_name = etree.QName(encoding).localname
            self._resolve_and_record(
                detected,
                unknown,
                kind="encoding",
                raw_name=raw_name,
                source="encodings",
                xpath_hint=f".//encodings/{raw_name}",
            )

    def _detect_dashboard_zones(
        self,
        root: etree._Element,
        detected: dict[tuple[str, str, str], DetectedCapability],
        unknown: dict[tuple[str, str, str], DetectedCapability],
    ) -> None:
        """Detect dashboard zone/control types used in the workbook."""
        for zone in root.findall(".//dashboard//zone"):
            raw_name = zone.get("type-v2") or "worksheet"
            self._resolve_and_record(
                detected,
                unknown,
                kind="dashboard_zone",
                raw_name=raw_name,
                source="dashboard-zone",
                xpath_hint=".//dashboard//zone",
            )

    def _detect_actions(
        self,
        root: etree._Element,
        detected: dict[tuple[str, str, str], DetectedCapability],
        unknown: dict[tuple[str, str, str], DetectedCapability],
    ) -> None:
        """Detect interaction action commands declared in workbook XML."""
        for command in root.findall(".//action/command"):
            raw_name = command.get("command", "")
            if not raw_name:
                continue
            self._resolve_and_record(
                detected,
                unknown,
                kind="action",
                raw_name=raw_name,
                source="action-command",
                xpath_hint=".//action/command",
            )

        for action in root.xpath(".//action[link and not(command)]"):
            self._resolve_and_record(
                detected,
                unknown,
                kind="action",
                raw_name="url-action",
                source="action-link",
                xpath_hint=".//action[link and not(command)]",
            )

        for nav_action in root.xpath(".//nav-action"):
            self._resolve_and_record(
                detected,
                unknown,
                kind="action",
                raw_name="nav-action",
                source="nav-action",
                xpath_hint=".//nav-action",
            )

    def _detect_connections(
        self,
        root: etree._Element,
        detected: dict[tuple[str, str, str], DetectedCapability],
        unknown: dict[tuple[str, str, str], DetectedCapability],
    ) -> None:
        """Detect connection classes across all datasource connection nodes."""
        for connection in root.findall(".//connection"):
            raw_name = connection.get("class", "")
            if not raw_name:
                continue
            self._resolve_and_record(
                detected,
                unknown,
                kind="connection",
                raw_name=raw_name,
                source="connection-class",
                xpath_hint=".//connection",
            )

    def _detect_unsupported_features(
        self,
        root: etree._Element,
        detected: dict[tuple[str, str, str], DetectedCapability],
        unknown: dict[tuple[str, str, str], DetectedCapability],
    ) -> None:
        """Detect known unsupported feature markers for migration triage."""
        if root.find(".//reference-line") is not None:
            self._resolve_and_record(
                detected,
                unknown,
                kind="feature",
                raw_name="reference-line",
                source="xml-feature",
                xpath_hint=".//reference-line",
            )
        if root.find(".//trend-line") is not None:
            self._resolve_and_record(
                detected,
                unknown,
                kind="feature",
                raw_name="trend-line",
                source="xml-feature",
                xpath_hint=".//trend-line",
            )
        if root.find(".//bin") is not None:
            self._resolve_and_record(
                detected,
                unknown,
                kind="feature",
                raw_name="bin",
                source="xml-feature",
                xpath_hint=".//bin",
            )
        if root.find(".//group[@type='set']") is not None:
            self._resolve_and_record(
                detected,
                unknown,
                kind="feature",
                raw_name="set",
                source="xml-feature",
                xpath_hint=".//group[@type='set']",
            )

        for element in root.iter():
            if etree.QName(element).localname.startswith("table-calc"):
                self._resolve_and_record(
                    detected,
                    unknown,
                    kind="feature",
                    raw_name="table-calculation",
                    source="xml-feature",
                    xpath_hint=".//table-calc-*",
                )
                break


def analyze_workbook(file_path: str | Path) -> AnalysisReport:
    """Convenience wrapper for one-off TWB analysis."""

    return TWBAnalyzer().analyze(file_path)
