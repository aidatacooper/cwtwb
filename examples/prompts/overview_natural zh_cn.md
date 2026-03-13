---
step: 10
level: "⭐⭐⭐ Advanced"
demonstrates: "参数 + LOD 计算字段 + 地图 + 面积图 + 筛选侧边栏 + 仪表板交互动作 — 纯中文自然语言提示词"
description: 纯自然语言演示提示词 — 完全还原 overview_full correct.twb
---

# 帮我做一个 Superstore 盈利概览仪表板

用 Superstore 模板创建工作簿，保存到 `output/overview_natural.twb`。

## 分析场景

我想从地域、产品线、客户群体三个维度看我们门店的盈利状况，同时能做 What-If 假设分析。

## 三个假设分析参数

给我三个滑块：目标利润 Target Profit（默认 10000，范围 -30000 到 100000，步长 10000）、流失率 Churn Rate（默认 0.168，范围 0 到 1，步长 0.05）、新业务增长 New Business Growth（默认 0.599，范围 0 到 1，步长 0.05）。

## 六个分析指标

请帮我生成以下指标：**Profit Ratio**、**Profit per Customer** 和 **Profit per Order**。另外创建一个 **Order Profitable?** 状态，判断利润是否超过目标利润。最后，按照 `(1 - 流失率) * (1 + 增长)` 的逻辑计算 **Sales & Units estimate**（Units 需要四舍五入取整）。

## 四张图表

## 四张图表

首先，制作一个 **Total Sales** KPI 条，集中展示从销售额到订单利润在内的 7 个核心指标。

接着，创建一个 **SaleMap** 地图来展现地域表现。按州显示盈利状态（颜色区分），并用气泡大小代表销售规模，在提示信息中显示利润。

最后，添加 **SalesbyProduct** 和 **SalesbySegment** 两个趋势图。它们应该展示按月统计的销售面积图，并分别按产品类别和客户细分进行分面排列。同样用颜色区分盈亏，并在提示信息中包含利润详情。

## 仪表板 Overview（936×650）

整体分成上下两部分：顶部放 Total Sales KPI 条，大概占 15% 高度；下方分左右两栏。

左侧栏大约占 18% 宽度，从上到下依次放：Order Date 日期范围筛选器、Region 下拉筛选器（dropdown 模式）、State/Province 多选下拉筛选器（checkdropdown 模式）、Profit Ratio 数值范围筛选器，以及 Order Profitable? 的颜色图例。这些筛选器和图例都挂在 SaleMap 工作表上。

右侧主区域占剩余的 82% 宽度，上半部分放 SaleMap 地图（约占 55% 高度），下半部分左右各放一张面积图：左边 SalesbySegment，右边 SalesbyProduct，各占 50% 宽度。

先用 generate_layout_json 工具生成布局 JSON 文件，再把文件路径传给 add_dashboard。

## 两个交互动作

在地图上点击某个州时，过滤 SalesbyProduct 工作表（按 State/Province 字段）；同时高亮 SalesbySegment 工作表（也按 State/Province 字段）。
