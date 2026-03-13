"""
Exec Overview Dashboard — 复刻脚本

目标: 尽可能复刻 templates/dashboard/Exec Overview.twb 仪表板
数据源: templates/dashboard/Sample _ Superstore.hyper
输出: examples/superstore_recreated/Exec Overview Recreated.twb

能力评估 (对照原始 TWB):
  ✅ 完全支持: KPI 文本卡片, 迷你折线图(双轴Area), 柱形图, 水平条形图,
               地图, 饼图, 参数控制, LOD表达式, 工作表样式, 仪表板布局
  ⚠️ 简化实现: KPI 差异徽章(原 GanttBar → 改用 Bar),
               年份按钮(原 GanttBar+Shape → 改用 ParamCtrl),
               条件指标(原 Shape mark 绿点 → 省略)
  ❌ 无法实现: Table Calculation(RANK_DENSE), Bin, 位图(logo/社交图标),
              仪表板导航按钮, 圆环仪表盘(gauge)

运行:
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
# 1. 创建工作簿 + 连接 Hyper (读取 schema 获取真实表名)
# ============================================================
def create_workbook() -> TWBEditor:
    editor = TWBEditor("")  # 空模板

    # 读取 Hyper 文件 schema 获取实际表名和列名
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
# 2. 参数
# ============================================================
def add_parameters(editor: TWBEditor) -> None:
    editor.add_parameter(
        name="Current Year", datatype="integer", default_value="2021",
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
# 3. 计算字段
# ============================================================
CALC_FIELDS: list[dict] = [
    # --- 当前年 / 上年 度量 ---
    {"name": "Current Year Sales",    "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year] THEN [Sales] END",    "datatype": "real"},
    {"name": "Previous Year Sales",   "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year]-1 THEN [Sales] END", "datatype": "real"},
    {"name": "Current Year Profit",   "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year] THEN [Profit] END",  "datatype": "real"},
    {"name": "Previous Year Profit",  "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year]-1 THEN [Profit] END","datatype": "real"},
    {"name": "Current Year Quantity", "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year] THEN [Quantity] END","datatype": "integer"},
    {"name": "Previous Year Quantity","formula": "IF YEAR([Order Date]) = [Parameters].[Current Year]-1 THEN [Quantity] END","datatype": "integer"},
    {"name": "Returns count",         "formula": "{ FIXED [Order Date]: COUNT([Order ID]) }",                              "datatype": "integer"},
    {"name": "Current Year Returns",  "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year] THEN [Returns count] END",  "datatype": "integer"},
    {"name": "Previous Year Returns", "formula": "IF YEAR([Order Date]) = [Parameters].[Current Year]-1 THEN [Returns count] END","datatype": "integer"},

    # --- YoY 差异 ---
    {"name": "Sales Difference",    "formula": "(SUM([Current Year Sales]) - SUM([Previous Year Sales])) / SUM([Previous Year Sales])",       "datatype": "real"},
    {"name": "Profit Difference",   "formula": "(SUM([Current Year Profit]) - SUM([Previous Year Profit])) / SUM([Previous Year Profit])",    "datatype": "real"},
    {"name": "Quantity Difference",  "formula": "(SUM([Current Year Quantity]) - SUM([Previous Year Quantity])) / SUM([Previous Year Quantity])","datatype": "real"},
    {"name": "Returns Difference",  "formula": "(SUM([Current Year Returns]) - SUM([Previous Year Returns])) / SUM([Previous Year Returns])", "datatype": "real"},

    # --- 颜色分类 ---
    {"name": "Sales Color Filter",    "formula": "IF [Sales Difference] > 0 THEN 'GOOD' ELSE 'BAD' END",     "datatype": "string", "role": "measure"},
    {"name": "Profit Color Filter",   "formula": "IF [Profit Difference] > 0 THEN 'GOOD' ELSE 'BAD' END",    "datatype": "string", "role": "measure"},
    {"name": "Quantity Color Filter",  "formula": "IF [Quantity Difference] > 0 THEN 'GOOD' ELSE 'BAD' END", "datatype": "string", "role": "measure"},
    {"name": "Returns Color Filter",  "formula": "IF [Returns Difference] < 0 THEN 'GOOD' ELSE 'BAD' END",   "datatype": "string", "role": "measure"},

    # --- 年份辅助 ---
    {"name": "Year Filter",        "formula": "YEAR([Order Date]) = [Parameters].[Current Year]", "datatype": "boolean", "role": "dimension"},
    {"name": "Current Year Value", "formula": "[Parameters].[Current Year]",                       "datatype": "integer"},

    # --- 目标相关 ---
    {"name": "Sales Target",          "formula": "[Previous Year Sales]*[Parameters].[Sales Target (PY + X%)]", "datatype": "real"},
    {"name": "Difference from Target", "formula": "(SUM([Current Year Sales]) - SUM([Sales Target]))",           "datatype": "real", "role": "measure", "field_type": "ordinal"},
    {"name": "Target Reached",        "formula": "IF SUM([Current Year Sales]) >= SUM([Sales Target]) THEN '⬤' ELSE ' ' END", "datatype": "string", "role": "measure"},

    # --- LOD: 占比计算 (用于 Sub-Categories) ---
    {"name": "CY Sales Total",          "formula": "{FIXED: SUM([Current Year Sales])}",                       "datatype": "real"},
    {"name": "CY Total Sales Subcat",   "formula": "{ FIXED [Sub-Category]: SUM([Current Year Sales]) }",     "datatype": "real"},
    {"name": "Pct of Total Sales CY",   "formula": "SUM([CY Total Sales Subcat]) / SUM([CY Sales Total])",    "datatype": "real"},

    # --- 辅助 ---
    {"name": "Other % of total", "formula": "1-[Pct of Total Sales CY]", "datatype": "real"},
    {"name": "dummy", "formula": "'dummy'", "datatype": "string", "role": "dimension"},
    {"name": "Rank CY", "formula": "RANK_DENSE(sum([Current Year Sales]),'desc')", "datatype": "integer", "field_type": "ordinal", "table_calc": "Rows"},

    # --- KPI Difference 用 MIN(1) dummy 度量 ---
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
        )
        print(f"  + {f['name']}")


# ============================================================
# 4. 创建工作表 + 图表配置
# ============================================================
def create_worksheets(editor: TWBEditor) -> None:
    yf = [{"field": "Year Filter", "values": ["true"]}]

    # ----- KPI 数值卡片 (Text) -----
    for name, measure in [
        ("Sales KPI",    "Current Year Sales"),
        ("Profit KPI",   "Current Year Profit"),
        ("Returns KPI",  "Current Year Returns"),
        ("Quantity KPI", "Current Year Quantity"),
    ]:
        editor.add_worksheet(name)
        editor.configure_chart(name, mark_type="Text", label=f"SUM({measure})", filters=yf)

    # ----- KPI 差异徽章 (Bar — 原版用 GanttBar, 此处简化) -----
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

    # ----- KPI 迷你图 (Dual Axis: Area + Area) -----
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

    # ----- 月度 Sales vs Targets (Bar + Gantt) -----
    editor.add_worksheet("CY Sales")
    editor.configure_dual_axis(
        "CY Sales",
        mark_type_1="Bar", mark_type_2="GanttBar",
        columns=["MONTH(Order Date)"],
        rows=["SUM(Current Year Sales)", "SUM(Sales Target)"],
        color_1="Target Reached",
        show_labels=False,
        synchronized=True,
        filters=yf,
    )

    # ----- Top 5 Manufacturers (Horizontal Bar) -----
    editor.add_worksheet("Sales by Top Manufacturers")
    editor.configure_dual_axis(
        "Sales by Top Manufacturers",
        mark_type_1="Bar", mark_type_2="GanttBar",
        columns=["SUM(Current Year Sales)", "SUM(Sales Target)"],
        rows=["Product Name", "Difference from Target", "Target Reached"],
        dual_axis_shelf="columns",
        color_1="Target Reached",
        sort_descending="SUM(Current Year Sales)",
        show_labels=False,
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
            # Layer 0 (id=1): 圆形标记层 — size=CY Sales
            {"mark_type": "Automatic", "size": "SUM(Current Year Sales)"},
            # Layer 1 (id=0): Multipolygon 底图 — color + size + tooltip + geometry
            {
                "mark_type": "Multipolygon",
                "color": "Target Reached",
                "size": "SUM(Current Year Sales)",
                "tooltip": ["SUM(Current Year Sales)", "SUM(Sales Target)"],
                "mark_sizing_off": True,
                "mark_size_value": "1.7471270561218262",
            },
            # Layer 2 (id=2): 灰色圆形叠加 — mark_color=#adb1c5
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

    # ----- Top 5 Locations text (Text with multi-field label) -----
    editor.add_worksheet("Top 5 Locations text")
    editor.configure_chart(
        "Top 5 Locations text", mark_type="Text",
        rows=["State/Province"],
        label="SUM(Current Year Sales)",
        label_extra=["State/Province"],
        customized_label="<SUM(Current Year Sales)>\n<State/Province>",
        sort_descending="SUM(Current Year Sales)",
        filters=yf + [{"column": "State/Province", "top": 5, "by": "SUM(Current Year Sales)"}],
    )

    # ----- Top 5 Sub-Categories (Horizontal Bar + Gantt + Pie KPI) -----
    editor.add_worksheet("Sales by Sub-Category")
    editor.configure_dual_axis(
        "Sales by Sub-Category",
        mark_type_1="Bar", mark_type_2="GanttBar",
        rows=["Sub-Category", "Difference from Target"],
        columns=["SUM(Current Year Sales)", "SUM(Sales Target)"],
        dual_axis_shelf="cols",
        color_1="Target Reached",
        label_1="Difference from Target",
        sort_descending="SUM(Current Year Sales)",
        synchronized=True,
        show_labels=False,
        filters=yf + [{"column": "Sub-Category", "top": 5, "by": "SUM(Current Year Sales)"}],
        extra_axes=[
            {
                "measure": "KPI Bar Sales",
                "mark_type": "Pie",
                "color": ":Measure Names",
                "measure_values": ["Pct of Total Sales CY", "Other % of total"],
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
# 5. 应用工作表样式 (利用新 configure_worksheet_style API)
# ============================================================
KPI_WORKSHEETS = [
    "Sales KPI", "Sales KPI Difference", "Sales KPI Graph",
    "Profit KPI", "Profit KPI Difference", "Profit KPI Graph",
    "Returns KPI", "Returns KPI Difference", "Returns KPI Graph",
    "Quantity KPI", "Quantity KPI Difference", "Quantity KPI Graph",
]

ALL_WORKSHEETS = KPI_WORKSHEETS + [
    "CY Sales", "Sales by Top Manufacturers",
    "Sales by Location", "Top 5 Locations", "Top 5 Locations text",
    "Sales by Sub-Category",
]


def apply_styles(editor: TWBEditor) -> None:
    # KPI 卡片: 全部隐藏, 透明背景
    for ws in KPI_WORKSHEETS:
        editor.configure_worksheet_style(
            ws,
            background_color="#00000000",
            hide_axes=True,
            hide_gridlines=True,
            hide_zeroline=True,
            hide_borders=True,
            hide_band_color=True,
        )
        print(f"  styled (KPI): {ws}")

    # 主图表: 隐藏网格线和边框, 保留坐标轴
    for ws in ["CY Sales", "Sales by Top Manufacturers", "Sales by Sub-Category"]:
        editor.configure_worksheet_style(
            ws,
            hide_gridlines=True,
            hide_borders=True,
            hide_band_color=True,
        )
        print(f"  styled (chart): {ws}")

    # 地图和文本: 全透明
    editor.configure_worksheet_style(
        "Sales by Location",
        background_color="#00000000",
        hide_axes=True,
        hide_gridlines=True,
        hide_zeroline=True,
        hide_borders=True,
        hide_band_color=True,
    )
    for ws in ["Top 5 Locations", "Top 5 Locations text"]:
        editor.configure_worksheet_style(
            ws,
            background_color="#00000000",
            hide_axes=True,
            hide_gridlines=True,
            hide_zeroline=True,
            hide_borders=True,
            hide_band_color=True,
            hide_row_label="State/Province",
        )
        print(f"  styled (clean): {ws}")


# ============================================================
# 6. 仪表板布局
# ============================================================
# 配色常量
SIDEBAR_BG = "#e7e8f7"      # 淡紫灰侧边栏
KPI_BG     = "#ffffff"      # KPI 卡片背景 (白色, 对齐参考 1220)
CARD_BG    = "#ffffff"       # 白色卡片
BORDER     = "#898989"       # 边框色 (对齐参考 1220)

DASHBOARD_LAYOUT: dict = {
    "type": "container", "direction": "horizontal",
    "children": [
        # ===== 左侧边栏 =====
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
             # ❌ 无法实现: 绿点图例 "Sales Target has been reached"
             # ❌ 无法实现: Twitter/LinkedIn 图标 (bitmap zones)
             {"type": "text", "text": "Sales Target\nhas been reached.", "font_size": "8",
              "font_color": "#6b6f8d", "fixed_size": 40,
              "style": {"background-color": SIDEBAR_BG}},
             # 底部 credit 占剩余空间
             {"type": "text", "text": "Created by:\nSerena Purslow", "font_size": "8",
              "font_color": "#8b8faa",
              "style": {"background-color": SIDEBAR_BG}},
         ]},

        # ===== 主内容区 =====
        {"type": "container", "direction": "vertical",
         "children": [
             # --- 标题栏 ---
             {"type": "text", "text": "EXECUTIVE SALES OVERVIEW | 2021",
              "font_size": "20", "bold": True, "font_color": "#2c2f4a",
              "fixed_size": 60,
              "style": {"background-color": CARD_BG}},

             # --- KPI 卡片行 (4组: 值+差异 | 迷你图) ---
             {"type": "container", "direction": "horizontal", "fixed_size": 110,
              "style": {"background-color": KPI_BG},
              "children": [
                  # Sales KPI
                  {"type": "container", "direction": "horizontal", "children": [
                      {"type": "container", "direction": "vertical", "children": [
                          {"type": "worksheet", "name": "Sales KPI", "fixed_size": 55,
                           "style": {"background-color": KPI_BG}},
                          {"type": "worksheet", "name": "Sales KPI Difference",
                           "style": {"background-color": KPI_BG}},
                      ]},
                      {"type": "worksheet", "name": "Sales KPI Graph",
                       "style": {"background-color": KPI_BG}},
                  ]},
                  # Profit KPI
                  {"type": "container", "direction": "horizontal", "children": [
                      {"type": "container", "direction": "vertical", "children": [
                          {"type": "worksheet", "name": "Profit KPI", "fixed_size": 55,
                           "style": {"background-color": KPI_BG}},
                          {"type": "worksheet", "name": "Profit KPI Difference",
                           "style": {"background-color": KPI_BG}},
                      ]},
                      {"type": "worksheet", "name": "Profit KPI Graph",
                       "style": {"background-color": KPI_BG}},
                  ]},
                  # Returns KPI
                  {"type": "container", "direction": "horizontal", "children": [
                      {"type": "container", "direction": "vertical", "children": [
                          {"type": "worksheet", "name": "Returns KPI", "fixed_size": 55,
                           "style": {"background-color": KPI_BG}},
                          {"type": "worksheet", "name": "Returns KPI Difference",
                           "style": {"background-color": KPI_BG}},
                      ]},
                      {"type": "worksheet", "name": "Returns KPI Graph",
                       "style": {"background-color": KPI_BG}},
                  ]},
                  # Quantity KPI
                  {"type": "container", "direction": "horizontal", "children": [
                      {"type": "container", "direction": "vertical", "children": [
                          {"type": "worksheet", "name": "Quantity KPI", "fixed_size": 55,
                           "style": {"background-color": KPI_BG}},
                          {"type": "worksheet", "name": "Quantity KPI Difference",
                           "style": {"background-color": KPI_BG}},
                      ]},
                      {"type": "worksheet", "name": "Quantity KPI Graph",
                       "style": {"background-color": KPI_BG}},
                  ]},
              ]},

             # --- 中间行: Sales vs Targets + Top 5 Manufacturers ---
             {"type": "container", "direction": "horizontal",
              "children": [
              {"type": "container", "direction": "vertical", "weight": 55, "children": [
                      {"type": "text", "text": "2021 | Sales vs Targets",
                       "font_size": "12", "bold": True, "font_color": "#2c2f4a",
                       "fixed_size": 30,
                       "style": {"background-color": CARD_BG}},
                      {"type": "worksheet", "name": "CY Sales",
                       "style": {"background-color": CARD_BG}},
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
                      {"type": "worksheet", "name": "Sales by Top Manufacturers"},
                  ]},
              ]},

             # --- 底部行: Map + Top 5 Sub-Categories ---
             {"type": "container", "direction": "horizontal",
              "children": [
                  {"type": "container", "direction": "vertical", "weight": 55, "children": [
                      {"type": "text", "text": "Sales by Location | Top 5 States",
                       "font_size": "12", "bold": True, "font_color": "#2c2f4a",
                       "fixed_size": 30,
                       "style": {"background-color": CARD_BG}},
                      {"type": "container", "direction": "horizontal", "children": [
                          {"type": "worksheet", "name": "Sales by Location", "weight": 3,
                           "style": {"background-color": CARD_BG}},
                          {"type": "container", "direction": "vertical", "weight": 1, "children": [
                              {"type": "worksheet", "name": "Top 5 Locations",
                               "style": {"background-color": CARD_BG}},
                              {"type": "worksheet", "name": "Top 5 Locations text",
                               "style": {"background-color": CARD_BG}},
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
                      {"type": "text", "text": "Top 5 Sub-Categories | Sales vs Targets",
                       "font_size": "12", "bold": True, "font_color": "#2c2f4a",
                       "fixed_size": 30},
                      {"type": "worksheet", "name": "Sales by Sub-Category"},
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

    # 高亮交互: 地图 → 其他图表
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
# Main
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
