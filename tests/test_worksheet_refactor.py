from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from cwtwb import TWBEditor
from cwtwb.server import (
    apply_worksheet_refactor,
    clone_worksheet,
    open_workbook,
    preview_worksheet_refactor,
    save_workbook,
)


EXAMPLE_WORKBOOK = Path("examples/migrate_workflow/5 KPI Design Ideas (2).twb")
OUTPUT_DIR = Path(".tmp_test_outputs")


def _worksheet(root: ET.Element, name: str) -> ET.Element:
    worksheet = root.find(f".//worksheet[@name='{name}']")
    assert worksheet is not None
    return worksheet


def _output_path(name: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    return OUTPUT_DIR / name


def test_clone_and_refactor_kpi_worksheet_sdk() -> None:
    editor = TWBEditor.open_existing(EXAMPLE_WORKBOOK)

    clone_message = editor.clone_worksheet("1. KPI", "1. KPI Profit")
    assert "1. KPI Profit" in clone_message

    preview = editor.preview_worksheet_refactor("1. KPI Profit", {"Sales": "Profit"})
    assert preview["worksheet_name"] == "1. KPI Profit"
    assert preview["formulas_updated"]

    result = editor.apply_worksheet_refactor("1. KPI Profit", {"Sales": "Profit"})
    assert result["worksheet_name"] == "1. KPI Profit"

    output = _output_path("kpi_profit_clone.twb")
    editor.save(output)

    root = ET.parse(output).getroot()
    original_ws = _worksheet(root, "1. KPI")
    profit_ws = _worksheet(root, "1. KPI Profit")

    original_xml = ET.tostring(original_ws, encoding="unicode")
    profit_xml = ET.tostring(profit_ws, encoding="unicode")

    assert "Sales" in original_xml
    assert "Profit" in profit_xml

    original_formulas = [
        calc.get("formula", "")
        for calc in original_ws.findall(".//datasource-dependencies/column/calculation")
    ]
    cloned_formulas = [
        calc.get("formula", "")
        for calc in profit_ws.findall(".//datasource-dependencies/column/calculation")
    ]

    assert any("[Sales]" in formula for formula in original_formulas)
    assert any("[Profit]" in formula for formula in cloned_formulas)
    assert not any("[Profit]" in formula for formula in original_formulas)


def test_clone_and_refactor_kpi_worksheet_server_wrappers() -> None:
    open_workbook(str(EXAMPLE_WORKBOOK))

    clone_result = clone_worksheet("1. KPI", "1. KPI Profit MCP")
    assert "1. KPI Profit MCP" in clone_result

    preview_payload = json.loads(
        preview_worksheet_refactor("1. KPI Profit MCP", {"Sales": "Profit"})
    )
    assert preview_payload["worksheet_name"] == "1. KPI Profit MCP"
    assert preview_payload["reference_rewrites"]

    apply_payload = json.loads(
        apply_worksheet_refactor("1. KPI Profit MCP", {"Sales": "Profit"})
    )
    assert apply_payload["worksheet_name"] == "1. KPI Profit MCP"

    output = _output_path("kpi_profit_clone_mcp.twb")
    save_workbook(str(output))

    root = ET.parse(output).getroot()
    profit_ws = _worksheet(root, "1. KPI Profit MCP")
    profit_xml = ET.tostring(profit_ws, encoding="unicode")
    assert "Profit" in profit_xml
