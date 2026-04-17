from __future__ import annotations

from pathlib import Path

from cwtwb import TWBEditor


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_DIR = ROOT / "examples" / "worksheet_refactor_kpi_profit"
SOURCE = EXAMPLE_DIR / "5 KPI Design Ideas (2).twb"
OUTPUT = ROOT / "examples" / "worksheet_refactor_kpi_profit" / "5 KPI Design Ideas (2) - KPI Profit Worksheet Example.twb"
TARGET_WORKSHEET = "1. KPI Profit"


def main() -> None:
    editor = TWBEditor.open_existing(SOURCE)
    if TARGET_WORKSHEET not in editor.list_worksheets():
        editor.clone_worksheet("1. KPI", TARGET_WORKSHEET)
        editor.apply_worksheet_refactor(TARGET_WORKSHEET, {"Sales": "Profit"})
    editor.set_worksheet_hidden(TARGET_WORKSHEET, hidden=False)
    editor.save(OUTPUT)
    print(f"Saved workbook to {OUTPUT}")


if __name__ == "__main__":
    main()
