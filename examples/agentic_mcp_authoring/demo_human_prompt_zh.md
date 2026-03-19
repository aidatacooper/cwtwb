# 面向人类的自然 Demo Prompt（中文）

我想做一个给销售管理层看的执行摘要仪表板。

我最关心的是：
- 哪些 Region 和 State 在驱动 Sales 和 Profit
- 当前筛选条件下，月度 Sales 趋势如何变化
- 当前选择后，Sub-Category 的销售分布如何

我希望结果：
- 只有 1 个 dashboard
- 主图能够驱动辅助图
- 有一个内部跳转动作
- 有一个外部链接动作
- 关键图表带一两句简短说明，让结果更像 AI authoring

我知道这批数据里至少有这些字段：
- Order Date
- Region
- State/Province
- Category
- Sub-Category
- Sales
- Profit
- Quantity

请你使用 `cwtwb` MCP server 帮我完成这件事。
如果 server 提供了 authoring workflow 相关的 prompt、resource、tool，请优先使用它们来规范化需求、补充必要默认值、然后生成 workbook。

最后请把 workbook 保存到：

```text
output/agentic_mcp_client_demo.twb
```

并告诉我：
- 你识别到了什么 dataset profile
- 你最终整理出的 contract 是什么
- 你调用了哪些关键 MCP prompts / resources / tools
- validate 和 analyze 的结果如何
