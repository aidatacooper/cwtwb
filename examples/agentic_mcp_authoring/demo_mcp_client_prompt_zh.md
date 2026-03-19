# MCP Client Demo Prompt（中文）

请使用当前连接的 `cwtwb` MCP server，完整演示一条 **Agentic BI authoring** 工作流：

目标：
- 从人类业务需求出发
- 先规范化为 contract
- 再通过 review / elicitation / execution plan 明确执行步骤
- 最终生成一个 `.twb` 仪表板

请严格按下面流程执行，不要跳步：

## 1. 从人类需求开始

人类需求如下：

```text
为销售管理层创建一个执行摘要仪表板。

目标：
1. 看清哪些 Region / State 在驱动 Sales 和 Profit
2. 看到在当前筛选条件下的月度 Sales 趋势
3. 看到当前选择后的 Sub-Category 销售分布

要求：
- 只做 1 个 dashboard
- 主图要驱动辅助图
- 需要至少 1 个内部跳转动作
- 需要至少 1 个外部 URL 动作
- 关键 worksheet 需要简短 caption，让结果看起来像 AI authoring，而不是纯 XML 拼接
```

已知字段如下，请把它们传给 prompt / contract：

```text
Order Date
Region
State/Province
Category
Sub-Category
Sales
Profit
Quantity
```

## 2. 先走 MCP prompt / resource / review 流程

请按这个顺序：

1. 调用 MCP prompt `dashboard_brief_to_contract`
2. 读取 resource `cwtwb://contracts/dashboard_authoring_v1`
3. 读取 resource `cwtwb://profiles/index`
4. 如果发现合适的 dataset profile，再读取对应 profile
5. 调用 tool `review_authoring_contract`
6. 调用 MCP prompt `light_elicitation`
7. 调用 MCP prompt `authoring_execution_plan`

执行要求：
- 先展示规范化后的 contract
- 如果 `review_authoring_contract` 返回 `clarification_questions`，只问这些问题，不要继续生成 workbook
- 如果 contract 已经足够完整，则继续执行，不要额外发散

## 3. 再进入 authoring 执行阶段

如果 contract 已有效，请继续：

1. 读取 `cwtwb://skills/authoring_workflow`
2. 读取 `cwtwb://skills/chart_builder`
3. 读取 `cwtwb://skills/dashboard_designer`
4. 创建 workbook
5. 添加 calculated field：

```text
Profit Ratio = SUM([Profit]) / SUM([Sales])
```

6. 创建这些 worksheet：
- `Sales Map`
- `Sales Trend`
- `Sub-Category Breakdown`

7. 配置图表建议：
- `Sales Map`：Map，按 `State/Province` 做地理编码，颜色用 `SUM(Profit)`，大小用 `SUM(Sales)`
- `Sales Trend`：Line，按 `MONTH(Order Date)` 展示 `SUM(Sales)`，可用 `Region` 上色
- `Sub-Category Breakdown`：Bar，按 `Sub-Category` 展示 `SUM(Sales)`，可用 `SUM(Profit)` 着色，并按 `SUM(Sales)` 降序

8. 创建 dashboard：
- 名称：`Executive Overview`

9. 添加 action：
- `filter`：`Sales Map` -> `Sub-Category Breakdown`，字段 `State/Province`
- `go-to-sheet`：`Sales Map` -> `Sales Trend`，caption 用 `Open Monthly Trend`
- `url`：来源 `Sub-Category Breakdown`，URL 用 `https://example.com/product-detail`，caption 用 `Open Product Detail`

10. 给 worksheet 添加 caption：
- `Sales Map`：`Geographic view of sales and profit, intended to drive the rest of the dashboard.`
- `Sales Trend`：`Monthly sales trend after the current dashboard context is applied.`
- `Sub-Category Breakdown`：`Sub-category comparison after the current selection.`

## 4. 保存、验证、分析

请把输出 workbook 保存到：

```text
output/agentic_mcp_client_demo.twb
```

然后继续：

1. 调用 `validate_workbook`
2. 调用 `analyze_twb`

## 5. 最终输出格式

最后请给我一份简洁总结，包含：

1. 识别到的 dataset profile
2. 最终 contract 的关键字段
3. 实际调用过的 prompts / resources / tools 概览
4. 生成的 workbook 路径
5. validate 结果
6. analyze 结果中最关键的 capability 摘要

额外要求：
- 不要跳过 contract review
- 不要直接开始创建 workbook
- 不要省略 prompts 的使用
- 优先体现 “人类需求 -> 规范化 -> 生成 dashboard twb” 这条主线
