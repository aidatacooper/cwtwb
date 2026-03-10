from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cwtwb.migration import (  # noqa: E402
    apply_twb_migration,
    migrate_twb_guided,
    preview_twb_migration,
    profile_twb_for_migration,
    propose_field_mapping,
)
from cwtwb.server import (  # noqa: E402
    apply_twb_migration as apply_twb_migration_tool,
    migrate_twb_guided as migrate_twb_guided_tool,
    preview_twb_migration as preview_twb_migration_tool,
    profile_twb_for_migration as profile_twb_for_migration_tool,
    propose_field_mapping as propose_field_mapping_tool,
)


MIGRATE_DIR = Path("templates/migrate")
TEMPLATE_PATH = MIGRATE_DIR / "5 KPI Design Ideas (2).twb"
TARGET_SOURCE = next(path for path in MIGRATE_DIR.glob("*.xls") if "Superstore" not in path.name)
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


def test_profile_twb_for_migration_reports_used_source() -> None:
    profile = profile_twb_for_migration(TEMPLATE_PATH, target_source=TARGET_SOURCE)

    assert profile.source_datasource == "Sample - Superstore (copy)"
    assert profile.worksheets_in_scope == EXPECTED_WORKSHEETS
    assert profile.dashboards_in_scope == ["KPI Board"]
    assert profile.used_datasources == ["Sample - Superstore (copy)"]
    assert "Sales" in profile.source_schema


def test_propose_field_mapping_auto_scans_source_and_target() -> None:
    proposal = propose_field_mapping(TEMPLATE_PATH, TARGET_SOURCE)

    assert proposal["source_datasource"] == "Sample - Superstore (copy)"
    assert len(proposal["candidate_field_mapping"]) == 21
    assert proposal["blocking_issue_count"] == 0
    mapped = {item["source_field"]: item["target_field"] for item in proposal["candidate_field_mapping"]}
    assert mapped["Sales"] == "销售额"
    assert mapped["Country/Region"] == "国家/地区"


def test_preview_twb_migration_reports_expected_scope() -> None:
    preview = preview_twb_migration(TEMPLATE_PATH, TARGET_SOURCE)

    assert preview.source_datasource == "Sample - Superstore (copy)"
    assert preview.target_datasource.startswith("federated.")
    assert preview.worksheets_in_scope == EXPECTED_WORKSHEETS
    assert preview.dashboards_in_scope == ["KPI Board"]
    assert len(preview.candidate_field_mapping) == 21
    assert preview.blocking_issue_count == 0
    assert preview.removable_datasources == ["Sample - Superstore (copy)"]


def test_mcp_tools_return_json_payloads() -> None:
    profile_payload = json.loads(
        profile_twb_for_migration_tool(str(TEMPLATE_PATH), target_source=str(TARGET_SOURCE))
    )
    mapping_payload = json.loads(propose_field_mapping_tool(str(TEMPLATE_PATH), str(TARGET_SOURCE)))
    preview_payload = json.loads(preview_twb_migration_tool(str(TEMPLATE_PATH), str(TARGET_SOURCE)))

    assert profile_payload["source_datasource"] == "Sample - Superstore (copy)"
    assert mapping_payload["blocking_issue_count"] == 0
    assert len(mapping_payload["candidate_field_mapping"]) == 21
    assert preview_payload["blocking_issue_count"] == 0


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


def test_apply_twb_migration_retargets_excel_connection_path(tmp_path: Path) -> None:
    output_path = tmp_path / "retargeted.twb"

    apply_twb_migration(
        TEMPLATE_PATH,
        TARGET_SOURCE,
        output_path=output_path,
    )

    root = ET.parse(output_path).getroot()
    filenames = {
        conn.get("filename")
        for conn in root.findall(".//connection[@class='excel-direct']")
        if conn.get("filename")
    }

    assert any(str(TARGET_SOURCE.resolve()).replace("\\", "/") == filename for filename in filenames)


def test_migrate_twb_guided_runs_end_to_end(tmp_path: Path) -> None:
    output_path = tmp_path / "guided.twb"

    payload = migrate_twb_guided(
        TEMPLATE_PATH,
        TARGET_SOURCE,
        output_path=output_path,
    )

    assert payload["workflow_status"] == "applied"
    assert payload["next_action"] == "done"
    assert output_path.exists()


def test_migrate_twb_guided_tool_returns_json_payload(tmp_path: Path) -> None:
    output_path = tmp_path / "guided-tool.twb"

    payload = json.loads(
        migrate_twb_guided_tool(
            str(TEMPLATE_PATH),
            str(TARGET_SOURCE),
            str(output_path),
        )
    )

    assert payload["workflow_status"] == "applied"
    assert payload["output_summary"]["migrated_twb"].endswith("guided-tool.twb")
