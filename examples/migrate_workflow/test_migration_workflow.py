from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from cwtwb import migrate_twb_guided  # noqa: E402


EXAMPLE_DIR = Path(__file__).resolve().parent
TEMPLATE_PATH = EXAMPLE_DIR / "5 KPI Design Ideas (2).twb"
TARGET_SOURCE = EXAMPLE_DIR / "示例 - 超市.xls"
OUTPUT_PATH = EXAMPLE_DIR / "5 KPI Design Ideas (2) - migrated to 示例超市.twb"


def run_example() -> dict:
    result = migrate_twb_guided(
        TEMPLATE_PATH,
        TARGET_SOURCE,
        output_path=OUTPUT_PATH,
    )

    assert result["workflow_status"] == "applied"
    assert result["blocking_issue_count"] == 0

    root = ET.parse(OUTPUT_PATH).getroot()
    dashboard = root.find(".//dashboards/dashboard[@name='KPI Board']")
    assert dashboard is not None

    target_filename = str(TARGET_SOURCE.resolve()).replace("\\", "/")
    filenames = {
        conn.get("filename")
        for conn in root.findall(".//connection[@class='excel-direct']")
        if conn.get("filename")
    }
    assert target_filename in filenames
    return result


if __name__ == "__main__":
    payload = run_example()
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nMigrated workbook: {OUTPUT_PATH}")
