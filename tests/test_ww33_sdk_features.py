"""Unit tests for WW33 refactored SDK features."""
from pathlib import Path
from cwtwb import TableColumn, TWBEditor


def test_add_shared_filter(tmp_path: Path) -> None:
    template = Path("src/cwtwb/references/empty_template.twb")
    editor = TWBEditor(template, clear_existing_content=True)

    editor.add_shared_filter("Region", values=["East"])
    editor.add_shared_filter("Sub-Category", all_members=True)
    editor.add_shared_filter("Order Date", year=2018)

    shared_views = editor.root.find("shared-views")
    assert shared_views is not None
    view = shared_views.find("shared-view")
    assert view is not None
    filters = view.findall("filter")
    assert len(filters) == 3


def test_set_datasource_color_palette(tmp_path: Path) -> None:
    template = Path("src/cwtwb/references/empty_template.twb")
    editor = TWBEditor(template, clear_existing_content=True)

    editor.set_datasource_color_palette(
        "Measure Names",
        color_map={'"[ds].[inst_1]"': "#5c6068", '"[ds].[inst_2]"': "#ffffff"},
        is_measure_names=True,
    )
    style = editor._datasource.find("style")
    assert style is not None
    rule = style.find("style-rule[@element='mark']")
    assert rule is not None
    enc = rule.find("encoding[@attr='color']")
    assert enc is not None
    assert enc.get("field") == "[:Measure Names]"


def test_set_worksheet_rich_title(tmp_path: Path) -> None:
    template = Path("src/cwtwb/references/empty_template.twb")
    editor = TWBEditor(template, clear_existing_content=True)
    editor.add_worksheet("TitleWS")

    editor.set_worksheet_rich_title(
        "TitleWS",
        runs=[
            {"text": "Sales Overview", "bold": True, "fontsize": 14},
            {"text": " - Subtitle", "fontsize": 10},
        ],
    )

    ws = editor._find_worksheet("TitleWS")
    formatted = ws.find(".//formatted-text")
    assert formatted is not None
    runs = formatted.findall("run")
    assert len(runs) == 2
    assert runs[0].get("bold") == "true"


def test_configure_multi_column_table(tmp_path: Path) -> None:
    template = Path("src/cwtwb/references/empty_template.twb")
    editor = TWBEditor(template, clear_existing_content=True)
    editor.add_worksheet("TableWS")

    editor.add_calculated_field("LABEL:Subcat BOLD", "IF TRUE THEN [Sub-Category] END")
    editor.add_calculated_field("LABEL:Subcat Normal", "IF FALSE THEN [Sub-Category] END")
    editor.add_calculated_field("MIN(1) Subcat", "MIN(1)")
    editor.add_calculated_field("MIN(0) Subcat", "MIN(0)")
    editor.add_calculated_field("LABEL:Sales BOLD", "SUM([Sales])")
    editor.add_calculated_field("LABEL:Sales Normal", "SUM([Sales])")
    editor.add_calculated_field("MIN(1) A", "MIN(1)")
    editor.add_calculated_field("MIN(0) Sales", "MIN(0)")

    cols = [
        TableColumn(
            header="Sub-Category",
            bold_field="LABEL:Subcat BOLD",
            normal_field="LABEL:Subcat Normal",
            axis_field="MIN(1) Subcat",
            spacer_field="MIN(0) Subcat",
        ),
        TableColumn(
            header="Sales",
            bold_field="LABEL:Sales BOLD",
            normal_field="LABEL:Sales Normal",
            axis_field="MIN(1) A",
            spacer_field="MIN(0) Sales",
        ),
    ]

    editor.configure_multi_column_table(
        "TableWS",
        row_field="Sub-Category",
        columns=cols,
    )

    ws = editor._find_worksheet("TableWS")
    table = ws.find("table")
    assert table is not None
    panes = table.findall(".//pane")
    assert len(panes) == 5
