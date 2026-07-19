from __future__ import annotations

import sys
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cwtwb import TWBEditor  # noqa: E402
from cwtwb.server import (  # noqa: E402
    add_calculated_field,
    add_dashboard,
    add_dashboard_action,
    add_parameter,
    add_worksheet,
    configure_chart,
    create_workbook,
    list_dashboards,
    list_worksheets,
    open_workbook,
    save_workbook,
)


def _build_seed_workbook(tmp_path: Path) -> Path:
    template = Path("src/cwtwb/references/empty_template.twb")
    output = tmp_path / "seed_existing_workbook.twb"

    create_workbook(str(template), "Seed Existing Workbook")
    add_parameter(
        name="Target Profit",
        datatype="real",
        default_value="1000",
        domain_type="range",
        min_value="0",
        max_value="5000",
        granularity="100",
    )
    add_calculated_field(
        "Profit Gap",
        "SUM([Profit (Orders)]) - [Target Profit]",
        "real",
    )

    add_worksheet("Sales by Category")
    configure_chart(
        worksheet_name="Sales by Category",
        mark_type="Bar",
        rows=["Category"],
        columns=["SUM(Sales)"],
    )

    add_worksheet("Sales by Segment")
    configure_chart(
        worksheet_name="Sales by Segment",
        mark_type="Pie",
        color="Segment",
        wedge_size="SUM(Sales)",
    )

    add_dashboard(
        dashboard_name="Overview",
        worksheet_names=["Sales by Category", "Sales by Segment"],
        layout="horizontal",
    )
    add_dashboard_action(
        dashboard_name="Overview",
        action_type="filter",
        source_sheet="Sales by Category",
        target_sheet="Sales by Segment",
        fields=["Category"],
    )
    save_workbook(str(output))
    return output


def _inject_thumbnails(source_path: Path, output_path: Path) -> None:
    shutil.copyfile(source_path, output_path)
    tree = ET.parse(output_path)
    root = tree.getroot()
    thumbnails = ET.Element("thumbnails")
    ET.SubElement(thumbnails, "thumbnail")
    root.append(thumbnails)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def test_open_workbook_lists_existing_objects(tmp_path: Path) -> None:
    seed = _build_seed_workbook(tmp_path)

    result = open_workbook(str(seed))
    assert f"Workbook opened: {seed}" in result

    worksheets_output = list_worksheets()
    dashboards_output = list_dashboards()
    assert "Sales by Category" in worksheets_output
    assert "Sales by Segment" in worksheets_output
    assert "Overview: Sales by Category, Sales by Segment" in dashboards_output

    editor = TWBEditor.open_existing(seed)
    assert editor.list_worksheets() == ["Sales by Category", "Sales by Segment"]
    assert editor.list_dashboards() == [
        {
            "name": "Overview",
            "worksheets": ["Sales by Category", "Sales by Segment"],
        }
    ]


def test_open_workbook_reconfigures_existing_worksheet(tmp_path: Path) -> None:
    seed = _build_seed_workbook(tmp_path)
    output = tmp_path / "edited_existing_workbook.twb"

    open_workbook(str(seed))
    configure_chart(
        worksheet_name="Sales by Category",
        mark_type="Line",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Sales)"],
    )
    save_workbook(str(output))

    root = ET.parse(output).getroot()
    worksheet = root.find(".//worksheet[@name='Sales by Category']")
    assert worksheet is not None
    mark = worksheet.find(".//pane/mark")
    assert mark is not None
    assert mark.get("class") == "Line"

    rows = worksheet.find("./table/rows")
    cols = worksheet.find("./table/cols")
    assert rows is not None and (rows.text or "").strip()
    assert cols is not None and (cols.text or "").strip()

    dashboard = root.find(".//dashboards/dashboard[@name='Overview']")
    assert dashboard is not None
    assert dashboard.findall(".//zone[@name='Sales by Category']")
    assert root.find(".//actions/action") is not None


def test_open_existing_restores_parameters_for_new_calculations(tmp_path: Path) -> None:
    seed = _build_seed_workbook(tmp_path)
    output = tmp_path / "parameter_reopen.twb"

    editor = TWBEditor.open_existing(seed)
    assert "Target Profit" in editor._parameters

    editor.add_calculated_field(
        "Target Delta",
        "SUM([Profit (Orders)]) - [Target Profit]",
        "real",
    )
    editor.save(output)

    root = ET.parse(output).getroot()
    calc = root.find(".//datasource/column[@caption='Target Delta']")
    assert calc is not None
    formula = calc.find("calculation")
    assert formula is not None
    assert "[Parameters].[Parameter 1]" in formula.get("formula", "")


def test_open_existing_continues_dashboard_zone_ids(tmp_path: Path) -> None:
    seed = _build_seed_workbook(tmp_path)

    editor = TWBEditor.open_existing(seed)
    old_ids = {
        int(zone.get("id"))
        for zone in editor.root.findall(".//dashboard//zone[@id]")
        if zone.get("id")
    }

    editor.add_dashboard(
        "Second Overview",
        worksheet_names=["Sales by Category", "Sales by Segment"],
        layout="vertical",
    )

    new_ids = [
        int(zone.get("id"))
        for zone in editor.root.findall(".//dashboard//zone[@id]")
        if zone.get("id")
    ]
    assert old_ids
    assert len(new_ids) == len(set(new_ids))
    assert max(new_ids) > max(old_ids)


def test_open_existing_strips_top_level_thumbnails(tmp_path: Path) -> None:
    seed = _build_seed_workbook(tmp_path)
    with_thumbnails = tmp_path / "seed_with_thumbnails.twb"
    output = tmp_path / "thumbnails_removed.twb"

    _inject_thumbnails(seed, with_thumbnails)
    editor = TWBEditor.open_existing(with_thumbnails)
    assert editor.root.find("thumbnails") is None

    editor.save(output)
    root = ET.parse(output).getroot()
    assert root.find("thumbnails") is None
