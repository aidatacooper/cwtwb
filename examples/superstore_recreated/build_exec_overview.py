"""
Exec Overview Dashboard — Recreation Script

Goal: Replicate the templates/dashboard/Exec Overview.twb dashboard as closely as possible.
Data Source: templates/dashboard/Sample _ Superstore.hyper
Output: examples/superstore_recreated/Exec Overview Recreated.twb

Capability Assessment (compared to original TWB):
  ✅ Fully Supported: KPI text cards (rich-text label_runs), Sparklines (Dual axis Area+Line),
                       Bar charts, Horizontal bars, Maps, Pie charts, Parameter controls,
                       LOD expressions, Worksheet styles, Dashboard layout,
                       CY Sales Labels (column label table), Title (Exec Summary) (dynamic title)
  ⚠️ Simplified: KPI Difference badges (Original GanttBar -> changed to Bar),
                   Year buttons (Original GanttBar+Shape -> changed to ParamCtrl),
                   Conditional indicators (Original Shape mark green dot -> omitted)
  ❌ Not Implemented: Bin, Bitmaps (logo/social icons),
                      Dashboard navigation buttons, Gauge charts

Run:
    cd <project_root>
    python examples/superstore_recreated/build_exec_overview.py
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cwtwb.config import REFERENCES_DIR
from cwtwb.connections import inspect_hyper_schema
from cwtwb.twb_editor import TWBEditor

HYPER_PATH = str(REFERENCES_DIR / "Sample _ Superstore.hyper")
OUTPUT_PATH = str(Path(__file__).resolve().parent / "Exec Overview Recreated.twb")


# ============================================================
# 1. Create Workbook + Connect Hyper (Inspect schema for real table names)
# ============================================================
def create_workbook() -> TWBEditor:
    editor = TWBEditor("")  # Blank template

    # Read Hyper file schema to get actual table and column names
    schema = inspect_hyper_schema(HYPER_PATH)
    tables = []
    for tbl in schema["tables"]:
        tables.append({
            "name": tbl["name"],
            "columns": [c["name"] for c in tbl["columns"]],
        })
        print(f"  Found table: {tbl['name']} ({len(tbl['columns'])} columns)")

    editor.set_hyper_connection(filepath=HYPER_PATH, tables=tables)
    return editor


# ============================================================
# 2. Parameters
# ============================================================
def add_parameters(editor: TWBEditor) -> None:
    editor.add_parameter(
        name="Current Year", datatype="integer", default_value="2023",
        domain_type="list", allowed_values=["2021", "2022", "2023"],
    )
    editor.add_parameter(
        name="Sales Target (PY + X%)", datatype="real", default_value="1.2",
        domain_type="list",
        allowed_values=[
            "1.0", "1.05", "1.1", "1.15", "1.2", "1.25", "1.3",
            "1.35", "1.4", "1.45", "1.5", "1.55", "1.6", "1.65",
            "1.7", "1.75", "1.8", "1.85", "1.9", "1.95",
        ],
    )


# ============================================================
# 3. Calculated Fields
# ============================================================
CALC_FIELDS: list[dict] = [
    # --- Current/Previous Year Measures ---
    {"name": "Current Year Sales",    "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year] THEN [Sales] END",    "datatype": "real", "default_format": 'c"$"#,##0,K;-"$"#,##0,K'},
    {"name": "Previous Year Sales",   "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year]-1 THEN [Sales] END", "datatype": "real"},
    {"name": "Current Year Profit",   "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year] THEN [Profit] END",  "datatype": "real"},
    {"name": "Previous Year Profit",  "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year]-1 THEN [Profit] END","datatype": "real"},
    {"name": "Current Year Quantity", "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year] THEN [Quantity] END","datatype": "integer"},
    {"name": "Previous Year Quantity","formula": "IF YEAR([Order Date]) = [Parameters].[Current Year]-1 THEN [Quantity] END","datatype": "integer"},
    {"name": "Returns count",         "formula": "{ FIXED [Order Date]: COUNT([Order ID]) }",                              "datatype": "integer"},
    {"name": "Current Year Returns",  "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year] THEN [Returns count] END",  "datatype": "integer"},
    {"name": "Previous Year Returns", "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year]-1 THEN [Returns count] END","datatype": "integer"},

    # --- YoY Difference ---
    {"name": "Sales Difference",    "formula": "(SUM([Current Year Sales]) - SUM([Previous Year Sales])) / SUM([Previous Year Sales])",       "datatype": "real"},
    {"name": "Profit Difference",   "formula": "(SUM([Current Year Profit]) - SUM([Previous Year Profit])) / SUM([Previous Year Profit])",    "datatype": "real"},
    {"name": "Quantity Difference",  "formula": "(SUM([Current Year Quantity]) - SUM([Previous Year Quantity])) / SUM([Previous Year Quantity])","datatype": "real"},
    {"name": "Returns Difference",  "formula": "(SUM([Current Year Returns]) - SUM([Previous Year Returns])) / SUM([Previous Year Returns])", "datatype": "real"},

    # --- Color Categorization ---
    {"name": "Sales Color Filter",    "formula": "IF [Sales Difference] > 0 THEN 'GOOD' ELSE 'BAD' END",     "datatype": "string", "role": "measure"},
    {"name": "Profit Color Filter",   "formula": "IF [Profit Difference] > 0 THEN 'GOOD' ELSE 'BAD' END",    "datatype": "string", "role": "measure"},
    {"name": "Quantity Color Filter",  "formula": "IF [Quantity Difference] > 0 THEN 'GOOD' ELSE 'BAD' END", "datatype": "string", "role": "measure"},
    {"name": "Returns Color Filter",  "formula": "IF [Returns Difference] < 0 THEN 'GOOD' ELSE 'BAD' END",   "datatype": "string", "role": "measure"},

    # --- Year Helpers ---
    {"name": "Year Filter",        "formula": "YEAR([Order Date]) = [Parameters].[Current Year]", "datatype": "boolean", "role": "dimension"},
    {"name": "Current Year Value", "formula": "[Parameters].[Current Year]",                       "datatype": "integer", "default_format": "0"},

    # --- Target Related ---
    {"name": "Sales Target",          "formula": "[Previous Year Sales]*[Parameters].[Sales Target (PY + X%)]", "datatype": "real"},
    {"name": "Difference from Target", "formula": "(SUM([Current Year Sales]) - SUM([Sales Target]))",           "datatype": "real", "role": "measure", "field_type": "ordinal", "default_format": '*+"£"#,##0,.0K;-"£"#,##0,.0K'},
    {"name": "Target Reached",        "formula": "IF SUM([Current Year Sales]) >= SUM([Sales Target]) THEN '⬤' ELSE ' ' END", "datatype": "string", "role": "measure"},

    # --- LOD: Ratio Calculation (for Sub-Categories) ---
    {"name": "CY Sales Total",          "formula": "{FIXED: SUM([Current Year Sales])}",                       "datatype": "real"},
    {"name": "CY Total Sales Subcat",   "formula": "{ FIXED [Sub-Category]: SUM([Current Year Sales]) }",     "datatype": "real"},
    {"name": "Pct of Total Sales CY",   "formula": "SUM([CY Total Sales Subcat]) / SUM([CY Sales Total])",    "datatype": "real"},

    # --- Helpers ---
    {"name": "Other % of total", "formula": "1-[Pct of Total Sales CY]", "datatype": "real"},
    {"name": "dummy", "formula": "'dummy'", "datatype": "string", "role": "dimension"},
    {"name": "Rank CY", "formula": "RANK_DENSE(sum([Current Year Sales]),'desc')", "datatype": "integer", "field_type": "ordinal", "table_calc": "Rows"},

    # --- MIN(1) dummy measure for KPI Difference badges ---
    {"name": "KPI Bar Sales",    "formula": "MIN(1)", "datatype": "integer"},
    {"name": "KPI Bar Profit",   "formula": "MIN(1)", "datatype": "integer"},
    {"name": "KPI Bar Returns",  "formula": "MIN(1)", "datatype": "integer"},
    {"name": "KPI Bar Quantity", "formula": "MIN(1)", "datatype": "integer"},
]


def add_calculated_fields(editor: TWBEditor) -> None:
    for f in CALC_FIELDS:
        editor.add_calculated_field(
            f["name"], f["formula"], f["datatype"],
            role=f.get("role"), field_type=f.get("field_type"),
            table_calc=f.get("table_calc"),
            default_format=f.get("default_format", ""),
        )
        print(f"  + {f['name']}")


# ============================================================
# 4. Create Worksheets + Chart Configurations
# ============================================================
def create_worksheets(editor: TWBEditor) -> None:
    yf = [{"field": "Year Filter", "values": ["true"]}]

    # ----- KPI Text Cards (rich-text: label name + value) -----
    for name, measure, label_name in [
        ("Sales KPI",    "Current Year Sales",    "Sales"),
        ("Profit KPI",   "Current Year Profit",   "Profit"),
        ("Returns KPI",  "Current Year Returns",  "Returns"),
        ("Quantity KPI", "Current Year Quantity", "Quantity"),
    ]:
        editor.add_worksheet(name)
        editor.configure_chart(
            name, mark_type="Text",
            label=f"SUM({measure})",
            filters=yf,
            label_runs=[
                {"text": label_name, "fontname": "Tableau Regular", "fontsize": 10, "fontalignment": "2"},
                {"text": "\n"},
                {"field": f"SUM({measure})", "fontname": "Tableau Bold", "fontsize": 12,
                 "fontcolor": "#555555", "bold": True, "fontalignment": "2"},
            ],
        )

    # ----- KPI Difference Badges (Bar - simplified from GanttBar) -----
    for name, diff, color, kpi_bar in [
        ("Sales KPI Difference",    "Sales Difference",    "Sales Color Filter",   "KPI Bar Sales"),
        ("Profit KPI Difference",   "Profit Difference",   "Profit Color Filter",  "KPI Bar Profit"),
        ("Returns KPI Difference",  "Returns Difference",  "Returns Color Filter", "KPI Bar Returns"),
        ("Quantity KPI Difference",  "Quantity Difference", "Quantity Color Filter","KPI Bar Quantity"),
    ]:
        editor.add_worksheet(name)
        editor.configure_chart(
            name, mark_type="Bar",
            columns=[kpi_bar],
            color=color,
            label=diff,
            axis_fixed_range={"min": 0, "max": 1},
            customized_label=f"<{diff}> vs PY",
            color_map={"BAD": "#e15759", "GOOD": "#03a44e"},
            text_format={diff: "p0.00%"},
            mark_sizing_off=True,
        )

    # ----- KPI Sparklines (Dual Axis: Area + Line) -----
    for name, prev, curr in [
        ("Sales KPI Graph",    "Previous Year Sales",    "Current Year Sales"),
        ("Profit KPI Graph",   "Previous Year Profit",   "Current Year Profit"),
        ("Returns KPI Graph",  "Previous Year Returns",  "Current Year Returns"),
        ("Quantity KPI Graph", "Previous Year Quantity",  "Current Year Quantity"),
    ]:
        editor.add_worksheet(name)
        editor.configure_dual_axis(
            name,
            mark_type_1="Area", mark_type_2="Line",
            columns=["MONTH(Order Date)"],
            rows=[f"SUM({prev})", f"SUM({curr})"],
            hide_axes=True, hide_zeroline=True, show_labels=False,
        )

    # ----- Monthly Sales vs Targets (Bar + Gantt) -----
    editor.add_worksheet("CY Sales")
    editor.configure_dual_axis(
        "CY Sales",
        mark_type_1="Bar", mark_type_2="GanttBar",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Current Year Sales)", "SUM(Sales Target)"],
        mark_color_1="#adb1c5",
        mark_color_2="#4e79a7",
        show_labels=False,
        synchronized=True,
        filters=yf,
    )

    # ----- CY Sales Labels (column-header label table for CY Sales chart) -----
    # Shows MONTH(Order Date) + Target Reached + Difference from Target as column headers
    # Matches original XML: cols shelf = (MONTH / (Target Reached / Diff from Target))
    editor.add_worksheet("CY Sales Labels")
    editor.configure_chart(
        "CY Sales Labels",
        mark_type="Text",
        columns=["MONTH(Order Date)", "Target Reached", "Difference from Target"],
        label="MONTH(Order Date)",
        filters=yf,
    )

    # ----- Title (Exec Summary) — dynamic title worksheet -----
    # Shows "EXECUTIVE SALES OVERVIEW | <year>" with rich text formatting
    editor.add_worksheet("Title (Exec Summary)")
    editor.configure_chart(
        "Title (Exec Summary)",
        mark_type="Text",
        label="SUM(Current Year Value)",
        label_runs=[
            {"text": "EXECUTIVE SALES OVERVIEW ", "fontname": "Tableau Medium", "fontsize": 22,
             "fontalignment": None},
            {"text": "|", "fontname": "Tableau Medium", "fontsize": 22,
             "bold": True, "fontcolor": "#5a6dff", "fontalignment": None},
            {"field": "SUM(Current Year Value)", "fontname": "Tableau Medium", "fontsize": 22,
             "prefix": " ", "fontalignment": None},
        ],
    )

    # ----- Top 5 Manufacturers (Horizontal Bar) -----
    editor.add_worksheet("Sales by Top Manufacturers")
    editor.configure_dual_axis(
        "Sales by Top Manufacturers",
        mark_type_1="Bar", mark_type_2="GanttBar",
        columns=["SUM(Current Year Sales)", "SUM(Sales Target)"],
        rows=["Product Name", "Difference from Target", "Target Reached"],
        dual_axis_shelf="columns",
        mark_color_1="#adb1c5",
        show_labels=False,
        sort_descending="SUM(Current Year Sales)",
        synchronized=True,
        filters=yf + [{"column": "Product Name", "top": 5, "by": "SUM(Current Year Sales)"}],
    )

    # ----- Sales by Location (Map — multi-layer) -----
    editor.add_worksheet("Sales by Location")
    editor.configure_chart(
        "Sales by Location", mark_type="Map",
        geographic_field="State/Province",
        map_fields=["Country/Region"],
        filters=yf,
        map_layers=[
            # Layer 0 (id=1): Circle marker layer — size=CY Sales
            {"mark_type": "Automatic", "size": "SUM(Current Year Sales)"},
            # Layer 1 (id=0): Multipolygon base map — color + size + tooltip + geometry
            {
                "mark_type": "Multipolygon",
                "color": "Target Reached",
                "size": "SUM(Current Year Sales)",
                "tooltip": ["SUM(Current Year Sales)", "SUM(Sales Target)"],
                "mark_sizing_off": True,
                "mark_size_value": "1.7471270561218262",
            },
            # Layer 2 (id=2): Gray circle overlay — mark_color=#adb1c5
            {
                "mark_type": "Automatic",
                "size": "SUM(Current Year Sales)",
                "mark_color": "#adb1c5",
                "mark_sizing_off": True,
                "mark_size_value": "1.7471270561218262",
                "has_stroke": True,
                "stroke_color": "#000000",
            },
        ],
    )

    # ----- Top 5 Locations (Pie with Rank CY label) -----
    editor.add_worksheet("Top 5 Locations")
    editor.configure_chart(
        "Top 5 Locations", mark_type="Pie",
        rows=["State/Province"],
        label="Rank CY",
        sort_descending="SUM(Current Year Sales)",
        filters=yf + [{"column": "State/Province", "top": 5, "by": "SUM(Current Year Sales)"}],
    )

    # ----- Top 5 Locations text (Text with rich-text label: state + CY sales) -----
    editor.add_worksheet("Top 5 Locations text")
    editor.configure_chart(
        "Top 5 Locations text", mark_type="Text",
        rows=["State/Province"],
        label="SUM(Current Year Sales)",
        label_extra=["State/Province"],
        sort_descending="SUM(Current Year Sales)",
        filters=yf + [{"column": "State/Province", "top": 5, "by": "SUM(Current Year Sales)"}],
        label_runs=[
            {"field": "State/Province", "fontname": "Tableau Regular", "fontcolor": "#333333"},
            {"text": "\n"},
            {"field": "SUM(Current Year Sales)", "fontname": "Tableau Bold", "fontsize": 12, "fontcolor": "#666666"},
            {"text": "\n"},
        ],
    )

    # ----- Top 5 Sub-Categories (Horizontal Bar + Gantt + Pie KPI) -----
    editor.add_worksheet("Sales by Sub-Category")
    editor.configure_dual_axis(
        "Sales by Sub-Category",
        mark_type_1="Bar", mark_type_2="GanttBar",
        rows=["Sub-Category", "Difference from Target", "Target Reached"],
        columns=["SUM(Current Year Sales)", "SUM(Sales Target)"],
        dual_axis_shelf="cols",
        mark_color_1="#adb1c5",
        mark_color_2="#4e79a7",
        show_labels=False,
        sort_descending="SUM(Current Year Sales)",
        synchronized=True,
        filters=yf + [{"column": "Sub-Category", "top": 5, "by": "SUM(Current Year Sales)"}],
        extra_axes=[
            {
                "measure": "KPI Bar Sales",
                "mark_type": "Pie",
                "color": ":Measure Names",
                "measure_values": ["Pct of Total Sales CY", "Other % of total"],
                "color_map": {"Pct of Total Sales CY": "#5a6dff", "Other % of total": "#d2d3df"},
            },
            {
                "measure": "KPI Bar Sales",
                "mark_type": "Automatic",
                "mark_sizing_off": True,
                "label": "Pct of Total Sales CY",
                "mark_color": "#ffffff",
                "size_value": "0.60370165109634399",
            },
        ],
    )



# ============================================================
# 5. Apply Worksheet Styles (Using new configure_worksheet_style API)
# ============================================================
KPI_WORKSHEETS = [
    "Sales KPI", "Sales KPI Difference", "Sales KPI Graph",
    "Profit KPI", "Profit KPI Difference", "Profit KPI Graph",
    "Returns KPI", "Returns KPI Difference", "Returns KPI Graph",
    "Quantity KPI", "Quantity KPI Difference", "Quantity KPI Graph",
]

ALL_WORKSHEETS = KPI_WORKSHEETS + [
    "CY Sales", "CY Sales Labels",
    "Title (Exec Summary)",
    "Sales by Top Manufacturers",
    "Sales by Location", "Top 5 Locations", "Top 5 Locations text",
    "Sales by Sub-Category",
]


def apply_styles(editor: TWBEditor) -> None:
    # ------------------------------------------------------------------
    # Disable tooltip on ALL worksheets (tooltip-mode='none')
    # ------------------------------------------------------------------
    for ws in ALL_WORKSHEETS:
        editor.configure_worksheet_style(ws, disable_tooltip=True)

    # ------------------------------------------------------------------
    # KPI Text Cards (Sales KPI, Profit KPI, Returns KPI, Quantity KPI)
    # ------------------------------------------------------------------
    for ws in ["Sales KPI", "Profit KPI", "Returns KPI", "Quantity KPI"]:
        editor.configure_worksheet_style(
            ws,
            background_color="#00000000",
            hide_axes=True, hide_gridlines=True, hide_zeroline=True,
            hide_borders=True, hide_band_color=True,
            pane_cell_style={"text-align": "center", "vertical-align": "center"},
        )
        print(f"  styled (KPI card): {ws}")

    # ------------------------------------------------------------------
    # KPI Sparklines
    # ------------------------------------------------------------------
    for ws in ["Sales KPI Graph", "Profit KPI Graph", "Returns KPI Graph", "Quantity KPI Graph"]:
        editor.configure_worksheet_style(
            ws,
            background_color="#00000000",
            hide_axes=True, hide_gridlines=True, hide_zeroline=True,
            hide_borders=True, hide_band_color=True,
            hide_col_field_labels=True,
            hide_droplines=True, hide_reflines=True, hide_table_dividers=True,
            axis_style={"tick-color": "#00000000"},
            cell_formats=[{"field": "MONTH(Order Date)", "text-format": "iLLLL"}],
            label_formats=[
                {"field": "MONTH(Order Date)", "display": "true",
                 "text-format": "iLLLLL", "font-weight": "bold",
                 "font-family": "Tableau Medium", "font-size": "8",
                 "color": "#bec4f4"},
            ],
        )
        print(f"  styled (sparkline): {ws}")

    # ------------------------------------------------------------------
    # KPI Difference Badges
    # ------------------------------------------------------------------
    for ws, kpi_bar in [
        ("Sales KPI Difference",    "KPI Bar Sales"),
        ("Profit KPI Difference",   "KPI Bar Profit"),
        ("Returns KPI Difference",  "KPI Bar Returns"),
        ("Quantity KPI Difference", "KPI Bar Quantity"),
    ]:
        editor.configure_worksheet_style(
            ws,
            background_color="#00000000",
            hide_axes=True, hide_gridlines=True, hide_zeroline=True,
            hide_borders=True, hide_band_color=True,
            hide_droplines=True, hide_reflines=True,
            pane_datalabel_style={
                "color-mode": "match", "font-size": "18",
                "font-weight": "normal", "font-family": "Tableau Medium",
            },
            pane_cell_style={"vertical-align": "center", "text-align": "right"},
            axis_style={
                "tick-color": "#00000000",
                "stroke-size": "0", "line-visibility": "off",
                "per_field": [
                    {"field": f"MIN({kpi_bar})", "attr": "display",
                     "value": "false", "scope": "cols", "class": "0"},
                ],
            },
        )
        print(f"  styled (KPI diff): {ws}")

    # ------------------------------------------------------------------
    # CY Sales: axis date format, label number format, hide axis, reflines
    # ------------------------------------------------------------------
    editor.configure_worksheet_style(
        "CY Sales",
        background_color="#00000000",
        hide_borders=True, hide_band_color=True,
        hide_droplines=True, hide_reflines=True,
        hide_zeroline=True, hide_gridlines=True,
        hide_table_dividers=True, hide_col_field_labels=True,
        label_formats=[
            # Date axis labels — hide display but keep format for overlay
            {"field": "MONTH(Order Date)", "display": "false"},
            {"field": "MONTH(Order Date)", "text-format": "iLLL",
             "font-size": "10", "font-family": "Tableau Medium",
             "font-weight": "normal", "color": "#333333"},
            # CY Sales measure label
            {"field": "SUM(Current Year Sales)",
             "text-format": 'c"$"#,##0,K;-"$"#,##0,K',
             "font-weight": "bold", "color": "#333333"},
        ],
        axis_style={
            "tick-color": "#00000000",
            "per_field": [
                # Show CY Sales axis (left)
                {"field": "SUM(Current Year Sales)", "attr": "display",
                 "value": "true", "scope": "rows", "class": "0"},
                {"field": "SUM(Current Year Sales)", "attr": "title",
                 "value": "", "scope": "rows", "class": "0"},
                # Height of date axis
                {"field": "MONTH(Order Date)", "attr": "height", "value": "35"},
                # Hide Sales Target axis (right)
                {"field": "SUM(Sales Target)", "attr": "title",
                 "value": "", "scope": "rows", "class": "0"},
                {"field": "SUM(Sales Target)", "attr": "display",
                 "value": "false", "scope": "rows", "class": "0"},
            ],
        },
    )
    print("  styled (chart): CY Sales")

    # ------------------------------------------------------------------
    # CY Sales Labels: transparent, label rotation, per-field formats
    # ------------------------------------------------------------------
    editor.configure_worksheet_style(
        "CY Sales Labels",
        background_color="#00000000",
        hide_axes=True, hide_gridlines=True, hide_zeroline=True,
        hide_borders=True, hide_band_color=True,
        hide_col_field_labels=True, hide_droplines=True, hide_reflines=True,
        hide_table_dividers=True,
        # Per-field table-level cell format (date header font)
        cell_formats=[
            {"field": "MONTH(Order Date)", "font-family": "Tableau Semibold",
             "color": "#666666", "text-format": "iLLLLL"},
        ],
        # Per-field label formats
        label_formats=[
            {"field": "MONTH(Order Date)", "display": "false"},
            {"field": "MONTH(Order Date)", "text-format": "iLLLLL"},
            # Target Reached column: centered, mint green
            {"field": "Target Reached", "text-align": "center",
             "color": "#b2e1c1", "font-weight": "normal", "font-size": "10"},
            # Difference from Target: rotated -90 degrees
            {"field": "Difference from Target", "text-orientation": "-90",
             "font-size": "8", "color": "#adb1c5",
             "font-family": "Tableau Semibold", "font-weight": "bold"},
        ],
        # Pane cell: centered + rotated (applies to the data cells)
        pane_cell_style={"text-align": "center", "text-orientation": "-90"},
        pane_trendline_hidden=True,
        # Per-field header heights (column width in cross-tab)
        header_formats=[
            {"field": "Target Reached", "height": "28"},
            {"field": "Difference from Target", "height": "80"},
        ],
    )
    print("  styled (labels): CY Sales Labels")

    # ------------------------------------------------------------------
    # Title (Exec Summary): transparent, left-aligned cell
    # ------------------------------------------------------------------
    editor.configure_worksheet_style(
        "Title (Exec Summary)",
        background_color="#00000000",
        hide_axes=True, hide_gridlines=True, hide_zeroline=True,
        hide_borders=True, hide_band_color=True,
        pane_cell_style={"vertical-align": "bottom", "text-align": "left"},
    )
    print("  styled (title): Title (Exec Summary)")

    # ------------------------------------------------------------------
    # Sales by Sub-Category: hide gridlines/borders + number formats
    # ------------------------------------------------------------------
    editor.configure_worksheet_style(
        "Sales by Sub-Category",
        hide_gridlines=True, hide_borders=True, hide_band_color=True,
        hide_droplines=True, hide_reflines=True, hide_zeroline=True,
        hide_table_dividers=True,
        hide_col_field_labels=True, hide_row_field_labels=True,
        label_formats=[
            {"field": "SUM(Current Year Sales)",
             "text-format": 'c"$"#,##0,K;-"$"#,##0,K',
             "font-size": "10", "font-family": "Tableau Medium",
             "color": "#555555"},
            {"field": "Difference from Target",
             "text-format": '*+"£"#,##0,.0K;-"£"#,##0,.0K',
             "font-size": "8", "color": "#adb1c5",
             "font-family": "Tableau Semibold"},
            {"field": "Pct of Total Sales CY",
             "text-format": "p0%",
             "font-size": "8", "font-family": "Tableau Medium",
             "color": "#555555"},
            {"field": "Target Reached", "color": "#8cd17d"},
        ],
        axis_style={
            "tick-color": "#00000000",
            "per_field": [
                {"field": "SUM(Current Year Sales)", "attr": "display",
                 "value": "false", "scope": "cols", "class": "0"},
                {"field": "SUM(Current Year Sales)", "attr": "title",
                 "value": "", "scope": "cols", "class": "0"},
                {"field": "SUM(Sales Target)", "attr": "title",
                 "value": "", "scope": "cols", "class": "0"},
                {"field": "SUM(Sales Target)", "attr": "display",
                 "value": "false", "scope": "cols", "class": "0"},
                {"field": "KPI Bar Sales", "attr": "display",
                 "value": "false", "scope": "cols", "class": "1"},
            ],
        },
    )
    print("  styled (chart): Sales by Sub-Category")

    # ------------------------------------------------------------------
    # Sales by Top Manufacturers: label formats, axis style
    # ------------------------------------------------------------------
    editor.configure_worksheet_style(
        "Sales by Top Manufacturers",
        background_color="#00000000",
        hide_borders=True, hide_band_color=True,
        hide_droplines=True, hide_reflines=True,
        hide_zeroline=True, hide_gridlines=True, hide_table_dividers=True,
        hide_col_field_labels=True, hide_row_field_labels=True,
        label_formats=[
            # CY Sales number format
            {"field": "SUM(Current Year Sales)",
             "text-format": 'c"$"#,##0,K;-"$"#,##0,K',
             "font-family": "Tableau Medium", "color": "#555555",
             "font-size": "10", "font-weight": "normal"},
            # Target Reached: centered, mint green
            {"field": "Target Reached", "text-align": "center",
             "color": "#b2e1c1", "font-size": "10"},
            # Difference from Target
            {"field": "Difference from Target",
             "text-format": '*+"£"#,##0,.0K;-"£"#,##0,.0K',
             "font-size": "8", "color": "#adb1c5",
             "font-family": "Tableau Semibold", "font-weight": "bold"},
            # Product Name color
            {"field": "Product Name", "font-size": "10", "color": "#333333",
             "font-family": "Tableau Medium", "font-weight": "normal"},
        ],
        axis_style={
            "tick-color": "#00000000",
            "per_field": [
                {"field": "SUM(Current Year Sales)", "attr": "display",
                 "value": "false", "scope": "cols", "class": "0"},
                {"field": "SUM(Current Year Sales)", "attr": "title",
                 "value": "", "scope": "cols", "class": "0"},
                {"field": "SUM(Sales Target)", "attr": "title",
                 "value": "", "scope": "cols", "class": "0"},
                {"field": "SUM(Sales Target)", "attr": "display",
                 "value": "false", "scope": "cols", "class": "0"},
            ],
        },
    )
    print("  styled (chart): Sales by Top Manufacturers")

    # ------------------------------------------------------------------
    # Sales by Location: transparent
    # ------------------------------------------------------------------
    editor.configure_worksheet_style(
        "Sales by Location",
        background_color="#00000000",
        hide_axes=True, hide_gridlines=True, hide_zeroline=True,
        hide_borders=True, hide_band_color=True,
        hide_droplines=True, hide_reflines=True, hide_table_dividers=True,
        axis_style={"tick-color": "#00000000"},
    )
    print("  styled (map): Sales by Location")

    # ------------------------------------------------------------------
    # Top 5 Locations (Pie): mark color + datalabel style
    # ------------------------------------------------------------------
    editor.configure_worksheet_style(
        "Top 5 Locations",
        background_color="#00000000",
        hide_axes=True, hide_gridlines=True, hide_zeroline=True,
        hide_borders=True, hide_band_color=True,
        hide_droplines=True, hide_reflines=True, hide_table_dividers=True,
        hide_col_field_labels=True,
        hide_row_label="State/Province",
        # Axis tick transparent
        axis_style={"tick-color": "#00000000"},
        # Hide State/Province label in table label style
        label_formats=[
            {"field": "State/Province", "display": "false"},
        ],
        pane_mark_style={
            "mark-color": "#5a6dff",
            "has-stroke": "true",
            "stroke-color": "#757fc5",
            "mark-transparency": "29",
            "size": "1.0214917659759521",
        },
        pane_datalabel_style={
            "color-mode": "user", "font-family": "Tableau Bold",
            "color": "#757fc5", "font-size": "12",
        },
        pane_trendline_hidden=True,
    )
    print("  styled (pie): Top 5 Locations")

    # ------------------------------------------------------------------
    # Top 5 Locations text
    # ------------------------------------------------------------------
    editor.configure_worksheet_style(
        "Top 5 Locations text",
        background_color="#00000000",
        hide_axes=True, hide_gridlines=True, hide_zeroline=True,
        hide_borders=True, hide_band_color=True,
        hide_droplines=True, hide_reflines=True, hide_table_dividers=True,
        axis_style={"tick-color": "#00000000"},
        hide_row_label="State/Province",
    )
    print("  styled (text): Top 5 Locations text")


# ============================================================
# 6. Dashboard Layout
# ============================================================
# Color constants
SIDEBAR_BG = "#e7e8f7"      # Lavender gray sidebar
KPI_BG     = "#ffffff"      # KPI card background (white, aligns with ref 1220)
CARD_BG    = "#ffffff"       # White card
BORDER     = "#898989"       # Border color (aligns with ref 1220)

DASHBOARD_LAYOUT: dict = {
    "type": "container", "direction": "horizontal",
    "children": [
        # ===== Left Sidebar =====
        {"type": "container", "direction": "vertical", "fixed_size": 148,
         "style": {"background-color": SIDEBAR_BG},
         "children": [
             {"type": "empty", "fixed_size": 20},
             {"type": "text", "text": "Overview", "font_size": "11", "bold": True,
              "font_color": "#3c4062", "fixed_size": 30,
              "style": {"background-color": SIDEBAR_BG}},
             {"type": "text", "text": "Order Details", "font_size": "11",
              "font_color": "#6b6f8d", "fixed_size": 30,
              "style": {"background-color": SIDEBAR_BG}},
             {"type": "empty", "fixed_size": 15},
             {"type": "text", "text": "Controls", "font_size": "11", "bold": True,
              "font_color": "#3c4062", "fixed_size": 25,
              "style": {"background-color": SIDEBAR_BG}},
             {"type": "text", "text": "Select Year", "font_size": "9",
              "font_color": "#6b6f8d", "fixed_size": 20,
              "style": {"background-color": SIDEBAR_BG}},
             {"type": "paramctrl", "parameter": "Current Year", "fixed_size": 40,
              "style": {"background-color": SIDEBAR_BG}},
             {"type": "empty", "fixed_size": 15},
             {"type": "text", "text": "Set Sales Target\n(PY + X%)", "font_size": "9",
              "font_color": "#6b6f8d", "fixed_size": 35,
              "style": {"background-color": SIDEBAR_BG}},
             {"type": "paramctrl", "parameter": "Sales Target (PY + X%)", "fixed_size": 40,
              "style": {"background-color": SIDEBAR_BG}},
             {"type": "empty", "fixed_size": 15},
             # ❌ Not Implemented: Green dot legend "Sales Target has been reached"
             # ❌ Not Implemented: Twitter/LinkedIn icons (bitmap zones)
             {"type": "text", "text": "Sales Target\nhas been reached.", "font_size": "8",
              "font_color": "#6b6f8d", "fixed_size": 40,
              "style": {"background-color": SIDEBAR_BG}},
             # Bottom credit takes remaining space
             {"type": "text", "text": "Created by:\nSerena Purslow", "font_size": "8",
              "font_color": "#8b8faa",
              "style": {"background-color": SIDEBAR_BG}},
         ]},

        # ===== Main Content Area =====
        {"type": "container", "direction": "vertical",
         "children": [
             # --- Title Bar — dynamic Title (Exec Summary) worksheet ---
             {"type": "worksheet", "name": "Title (Exec Summary)",
              "fixed_size": 60,
              "style": {"background-color": CARD_BG}, "fit": "entire"},

             # --- KPI Cards Section (4 groups: Value+Diff | Sparkline) ---
             {"type": "container", "direction": "horizontal", "fixed_size": 110,
              "style": {"background-color": KPI_BG},
              "children": [
                  # Sales KPI
                  {"type": "container", "direction": "horizontal", "children": [
                      {"type": "container", "direction": "vertical", "fixed_size": 100, "children": [
                          {"type": "worksheet", "name": "Sales KPI", "fixed_size": 55,
                           "style": {"background-color": KPI_BG}, "fit": "entire"},
                          {"type": "worksheet", "name": "Sales KPI Difference",
                           "style": {"background-color": KPI_BG}, "fit": "entire"},
                      ]},
                      {"type": "worksheet", "name": "Sales KPI Graph",
                       "style": {"background-color": KPI_BG}, "fit": "entire"},
                  ]},
                  # Profit KPI
                  {"type": "container", "direction": "horizontal", "children": [
                      {"type": "container", "direction": "vertical", "fixed_size": 100, "children": [
                          {"type": "worksheet", "name": "Profit KPI", "fixed_size": 55,
                           "style": {"background-color": KPI_BG}, "fit": "entire"},
                          {"type": "worksheet", "name": "Profit KPI Difference",
                           "style": {"background-color": KPI_BG}, "fit": "entire"},
                      ]},
                      {"type": "worksheet", "name": "Profit KPI Graph",
                       "style": {"background-color": KPI_BG}, "fit": "entire"},
                  ]},
                  # Returns KPI
                  {"type": "container", "direction": "horizontal", "children": [
                      {"type": "container", "direction": "vertical", "fixed_size": 100, "children": [
                          {"type": "worksheet", "name": "Returns KPI", "fixed_size": 55,
                           "style": {"background-color": KPI_BG}, "fit": "entire"},
                          {"type": "worksheet", "name": "Returns KPI Difference",
                           "style": {"background-color": KPI_BG}, "fit": "entire"},
                      ]},
                      {"type": "worksheet", "name": "Returns KPI Graph",
                       "style": {"background-color": KPI_BG}, "fit": "entire"},
                  ]},
                  # Quantity KPI
                  {"type": "container", "direction": "horizontal", "children": [
                      {"type": "container", "direction": "vertical", "fixed_size": 100, "children": [
                          {"type": "worksheet", "name": "Quantity KPI", "fixed_size": 55,
                           "style": {"background-color": KPI_BG}, "fit": "entire"},
                          {"type": "worksheet", "name": "Quantity KPI Difference",
                           "style": {"background-color": KPI_BG}, "fit": "entire"},
                      ]},
                      {"type": "worksheet", "name": "Quantity KPI Graph",
                       "style": {"background-color": KPI_BG}, "fit": "entire"},
                  ]},
              ]},

             # --- Middle Section: Sales vs Targets + Top 5 Manufacturers ---
             {"type": "container", "direction": "horizontal",
              "children": [
              {"type": "container", "direction": "vertical", "weight": 55, "children": [
                      {"type": "text", "text": "2023 | Sales vs Targets",
                       "font_size": "12", "bold": True, "font_color": "#2c2f4a",
                       "fixed_size": 30,
                       "style": {"background-color": CARD_BG}},
                      # CY Sales + CY Sales Labels stacked vertically
                      {"type": "container", "direction": "vertical", "children": [
                          {"type": "worksheet", "name": "CY Sales",
                           "style": {"background-color": CARD_BG}, "fit": "entire"},
                          # Empty spacer (52px) offsets y-axis area so labels align with bars
                          {"type": "container", "direction": "horizontal", "fixed_size": 60, "children": [
                              {"type": "empty", "fixed_size": 52},
                              {"type": "worksheet", "name": "CY Sales Labels",
                               "style": {"background-color": CARD_BG}, "fit": "entire"},
                          ]},
                      ]},
                  ],
                  "style": {"border-color": BORDER, "border-style": "solid",
                            "border-width": "1", "margin": "4"}},
                  {"type": "container", "direction": "vertical", "weight": 45,
                   "style": {"border-color": BORDER,
                             "border-style": "solid", "border-width": "1",
                             "margin": "4"},
                   "children": [
                      {"type": "text", "text": "Top 5 Manufacturers | Sales vs Targets",
                       "font_size": "12", "bold": True, "font_color": "#2c2f4a",
                       "fixed_size": 30},
                      {"type": "worksheet", "name": "Sales by Top Manufacturers", "fit": "entire"},
                   ]},
              ]},

             # --- Bottom Section: Map + Top 5 Sub-Categories ---
             {"type": "container", "direction": "horizontal",
              "children": [
                  # Left container: Sales by Location (including text descriptions)
                  {"type": "container", "direction": "vertical", "weight": 33, "children": [
                      {"type": "text", "text": "Sales by Location | Top 5 States",
                       "font_size": "12", "bold": True, "font_color": "#2c2f4a",
                       "fixed_size": 30,
                       "style": {"background-color": CARD_BG}},
                      {"type": "container", "direction": "horizontal", "children": [
                          {"type": "worksheet", "name": "Sales by Location",
                           "style": {"background-color": CARD_BG}, "fit": "entire"},
                           {"type": "container", "direction": "horizontal", "fixed_size": 150, "children": [
                               {"type": "worksheet", "name": "Top 5 Locations",
                                "style": {"background-color": CARD_BG}, "fit": "entire"},
                               {"type": "worksheet", "name": "Top 5 Locations text",
                                "style": {"background-color": CARD_BG}, "fit": "entire"},
                           ]},
                      ]},
                  ],
                  "style": {"border-color": BORDER, "border-style": "solid",
                            "border-width": "1", "margin": "4"}},
                  {"type": "container", "direction": "vertical", "weight": 55,
                   "style": {"border-color": BORDER,
                             "border-style": "solid", "border-width": "1",
                             "margin": "4"},
                   "children": [
                      {"type": "text", "text": "Top 5 Sub-Categories | Sales vs Targets",
                       "font_size": "12", "bold": True, "font_color": "#2c2f4a",
                       "fixed_size": 30},
                      {"type": "worksheet", "name": "Sales by Sub-Category", "fit": "entire", "show_title": False},
                  ]},
              ]},
         ]},
    ],
}


def create_dashboard(editor: TWBEditor) -> None:
    editor.add_dashboard(
        dashboard_name="Exec Overview",
        width=1200, height=1000,
        layout=DASHBOARD_LAYOUT,
        worksheet_names=ALL_WORKSHEETS,
    )

    # Highlight actions: Map -> Other charts
    editor.add_dashboard_action(
        dashboard_name="Exec Overview",
        action_type="highlight",
        source_sheet="Sales by Location",
        target_sheet="Sales by Sub-Category",
        fields=["State/Province"],
    )
    editor.add_dashboard_action(
        dashboard_name="Exec Overview",
        action_type="highlight",
        source_sheet="Sales by Location",
        target_sheet="Sales by Top Manufacturers",
        fields=["State/Province"],
    )


# ============================================================
# 7. Main
# ============================================================
def main() -> None:
    print("=== Building Exec Overview Dashboard ===\n")

    print("1. Creating workbook + Hyper connection...")
    editor = create_workbook()

    print("2. Adding parameters...")
    add_parameters(editor)

    print("3. Adding calculated fields...")
    add_calculated_fields(editor)

    print("4. Creating worksheets and charts...")
    create_worksheets(editor)

    print("5. Applying worksheet styles...")
    apply_styles(editor)

    print("6. Creating dashboard...")
    create_dashboard(editor)

    print(f"7. Saving to {OUTPUT_PATH}...")
    editor.save(OUTPUT_PATH, validate=False)

    print(f"\nDone! Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
