from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cwtwb.migration import apply_twb_migration, preview_twb_migration  # noqa: E402
from cwtwb.server import apply_twb_migration as apply_twb_migration_tool  # noqa: E402
from cwtwb.server import preview_twb_migration as preview_twb_migration_tool  # noqa: E402


TEMPLATE_PATH = Path("templates/migrate/5 KPI Design Ideas (2).twb")
TARGET_SOURCE = Path("templates/migrate/示例 - 超市.xls")
EXPECTED_WORKSHEETS = [
    "1. KPI",
    "2.1 KPI",
    "2.2 MoM Rounded Button",
    "2.3 KPI Line",
    "3.1 KPI Banner",
    "3.2 KPI Line",
    "3.3 KPI Metic",
    "4.1 KPI",
    "4.2 Line",
    "5.1 KPI",
    "5.2 Line",
    "Sheet 1",
    "Validation",
]


def test_preview_twb_migration_reports_expected_scope() -> None:
    preview = preview_twb_migration(TEMPLATE_PATH, TARGET_SOURCE)

    assert preview.source_datasource == "Sample - Superstore (copy)"
    assert preview.target_datasource.startswith("federated.")
    assert preview.worksheets_in_scope == EXPECTED_WORKSHEETS
    assert preview.dashboards_in_scope == ["KPI Board"]
    assert len(preview.candidate_field_mapping) == 21
    assert preview.blocking_issue_count == 0
    assert preview.removable_datasources == ["Sample - Superstore (copy)"]


def test_preview_tool_returns_json_payload() -> None:
    payload = json.loads(preview_twb_migration_tool(str(TEMPLATE_PATH), str(TARGET_SOURCE)))

    assert payload["source_datasource"] == "Sample - Superstore (copy)"
    assert payload["blocking_issue_count"] == 0
    assert len(payload["candidate_field_mapping"]) == 21


def test_apply_twb_migration_writes_expected_files(tmp_path: Path) -> None:
    output_path = tmp_path / "5 KPI Design Ideas (2) - migrated to 示例超市.twb"

    result = apply_twb_migration(
        TEMPLATE_PATH,
        TARGET_SOURCE,
        output_path=output_path,
    )

    assert output_path.exists()
    assert (tmp_path / "migration_report.json").exists()
    assert (tmp_path / "field_mapping.json").exists()
    assert result["output_summary"]["migrated_twb"].endswith("5 KPI Design Ideas (2) - migrated to 示例超市.twb")

    root = ET.parse(output_path).getroot()
    dashboard = root.find(".//dashboards/dashboard[@name='KPI Board']")
    assert dashboard is not None

    zone_names = [zone.get("name") for zone in dashboard.findall(".//zone[@name]")]
    assert zone_names == [
        "1. KPI",
        "2.1 KPI",
        "2.2 MoM Rounded Button",
        "2.3 KPI Line",
        "3.3 KPI Metic",
        "3.1 KPI Banner",
        "3.2 KPI Line",
        "4.1 KPI",
        "4.2 Line",
        "5.1 KPI",
        "5.2 Line",
    ]

    dep_names = {
        dep.get("datasource")
        for dep in root.findall(".//worksheet//datasource-dependencies")
    }
    assert dep_names == {"federated.0ur6qhz0zzw4sa17r5sbi1fpalil"}

    datasources = root.find("datasources")
    assert datasources is not None
    top_level_names = [ds.get("name") for ds in datasources.findall("datasource")]
    assert "Sample - Superstore (copy)" in top_level_names
    assert "federated.0ur6qhz0zzw4sa17r5sbi1fpalil" in top_level_names


def test_apply_tool_returns_json_payload(tmp_path: Path) -> None:
    output_path = tmp_path / "tool-migrated.twb"

    payload = json.loads(
        apply_twb_migration_tool(
            str(TEMPLATE_PATH),
            str(TARGET_SOURCE),
            str(output_path),
        )
    )

    assert payload["output_summary"]["migrated_twb"].endswith("tool-migrated.twb")
    assert payload["removable_datasources"] == ["Sample - Superstore (copy)"]
