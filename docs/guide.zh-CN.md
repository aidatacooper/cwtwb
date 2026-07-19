# cwtwb 指南

本页收集不适合放进 README 的详细文档。

## Python API

### 作为 Python Library 使用

使用 `TWBEditor(...)` 从模板开始并重建 workbook 内容。需要保留现有 worksheets 和 dashboards，并在原地重新配置某个 sheet 时，使用 `TWBEditor.open_existing(...)`。

```python
from cwtwb.twb_editor import TWBEditor

editor = TWBEditor("")  # "" uses the built-in Superstore template
editor.clear_worksheets()
editor.add_calculated_field("Profit Ratio", "SUM([Profit])/SUM([Sales])")

editor.add_worksheet("Sales by Category")
editor.configure_chart(
    worksheet_name="Sales by Category",
    mark_type="Bar",
    rows=["Category"],
    columns=["SUM(Sales)"],
)

editor.add_worksheet("Segment Pie")
editor.configure_chart(
    worksheet_name="Segment Pie",
    mark_type="Pie",
    color="Segment",
    wedge_size="SUM(Sales)",
)

editor.add_dashboard(
    dashboard_name="Overview",
    worksheet_names=["Sales by Category", "Segment Pie"],
    layout="horizontal",
)

editor.save("output/my_workbook.twb")
```

### 克隆并重构现有 Worksheet

当你想复制一个现有可视化模块，并只把克隆出来的 worksheet 重新绑定到另一个核心指标时，使用 worksheet clone/refactor。典型场景是把 Sales KPI worksheet 变成独立的 Profit KPI worksheet，同时保留原始 sheet。

```python
from cwtwb.twb_editor import TWBEditor

editor = TWBEditor.open_existing("examples/worksheet_refactor_kpi_profit/5 KPI Design Ideas (2).twb")

editor.clone_worksheet("1. KPI", "1. KPI Profit")
editor.apply_worksheet_refactor("1. KPI Profit", {"Sales": "Profit"})
editor.set_worksheet_hidden("1. KPI Profit", hidden=False)

editor.save("output/kpi_profit_clone.twb")
```

可用 helper：

- `clone_worksheet(source_worksheet, target_worksheet)`
- `preview_worksheet_refactor(worksheet_name, replacements)`
- `apply_worksheet_refactor(worksheet_name, replacements)`
- `set_worksheet_hidden(worksheet_name, hidden=True)`

`apply_worksheet_refactor(...)` 还会对通用 Tableau `Calculation_*` 字段执行 worksheet-local identity normalization。这样 clone-and-replace 工作流后的 pill label 更稳定，并会返回 `post_process` 证据，包括重命名的 calculation identities 和 worksheet-local rewrite maps。

### 云端验证

保存 workbook 后，优先使用 `validate_workbook_api` 做 Tableau Cloud/Server REST API 验证而不发布。只有明确需要发布/可打开性证据、`.twbx` 包验证、workbook ID 或截图时，才使用 `upload_workbook`。

**设置：**

```bash
pip install "cwtwb[validate]"
cp .env.example .env  # Fill in your Tableau Cloud PAT credentials
```

凭据也可以通过 `env_path`、`TABLEAU_ENV_FILE` 或 workbook 同目录 `.env` 在运行时选择。显式 `env_path` 优先级最高，适合一次性验证调用；MCP 用户无需为了切换凭据而编辑 server 配置或重启。

**Python API：**

```python
from cwtwb.validate import TableauUploader

uploader = TableauUploader(env_path="project/.env")

# REST API semantic validation without publishing
result = uploader.validate("output/my_workbook.twb", validation_level="semantic")
print(result.success, result.valid)

# Publish only when you need openability evidence, TWBX validation, or screenshots
result = uploader.upload("output/my_workbook.twb", data_path="data.xlsx")
print(result.success, result.workbook_url)

# Optional: screenshot for human review
if result.success:
    screenshot = uploader.screenshot(result.workbook_id, output_dir="output/validation")
    print(screenshot.path)
```

**MCP Tools：**

```text
validate_workbook_api(twb_path="output/my.twb", validation_level="semantic")
validate_workbook_api(twb_path="output/my.twb", env_path="project/.env")
upload_workbook(twb_path="output/my.twb", data_path="data.xlsx")
screenshot_workbook(workbook_id="xxx", output_dir="output/validation", env_path="project/.env")
```

### 处理打包工作簿（.twbx）

`.twbx` 是 ZIP archive，会把 workbook XML 和数据 extract（`.hyper`）、图片资源一起打包。cwtwb 可以透明读写它们：

```python
from cwtwb.twb_editor import TWBEditor

# Open a packaged workbook — extracts and images are preserved automatically
editor = TWBEditor.open_existing("templates/dashboard/MyDashboard.twbx")

# Make changes as usual
editor.add_calculated_field("Profit Ratio", "SUM([Profit])/SUM([Sales])")

# Save as .twbx — re-bundles the updated .twb with the original extracts/images
editor.save("output/MyDashboard_v2.twbx")

# Or extract just the XML when the packaged format isn't needed
editor.save("output/MyDashboard_v2.twb")
```

普通 `.twb` 也可以保存为 `.twbx`：

```python
editor = TWBEditor("templates/twb/superstore.twb")
# ...
editor.save("output/superstore.twbx")  # produces a single-entry ZIP with the .twb inside
```

## MCP 参考

### 稳定的 Agent 契约

cwtwb MCP server 设计为通过已连接 MCP 客户端直接调用工具。Agent 不应该尝试通过临时 shell 命令调用 cwtwb，例如：

```bash
mcp list-tools cwtwb
mcp call cwtwb create_workbook '{"name": "Example"}'
gh api /orgs/.../mcp/servers/cwtwb/tools
```

这些命令不是 cwtwb 的一部分，大多数用户机器也没有安装 `mcp` CLI。如果客户端看不到 `create_workbook`、`list_fields`、`add_worksheet` 或 `save_workbook`，正确处理方式是重新连接/重启 MCP 客户端并检查 server config，而不是发明 shell 命令。

推荐排查顺序：

1. 确认 server 能启动：`uvx cwtwb` 或 `uvx --from cwtwb cwtwb-mcp`
2. 确认 MCP 客户端配置指向同一个命令
3. 完全重启客户端，让它重新加载工具表面
4. 通过客户端自己的 MCP UI 或工具接口查看可用 tools/resources
5. 阅读 `cwtwb://tool-surface` 和 `cwtwb://skills/index`

`uv cache clean` 只会清理包缓存；如果旧 wheel 被复用，它可能有帮助，但不会修复 Claude/Cursor/VSCode 里过期的 MCP 工具注册表。

### 字段表达式输入

Chart 和 dashboard 的字段输入应使用面向用户的字段名或 Tableau 表达式，而不是从其他 workbook XML 里复制出来的内部引用。请使用 `Sales`、`SUM(Sales)`、`Category` 或 `MONTH(Order Date)`。

不要传入 `[sum:Sales:qk]`、`[avg:Calculation_ABC:qk]`、`[none:Category:nk]`、`[mn:Order Date:ok]`、`[sum:Sales:qk:1]`，也不要传入 `[federated.xxx].[sum:Profit:qk]` 这类带 datasource 前缀的变体。它们是 `.twb` 内部生成的 column-instance token；cwtwb 会拒绝这些值，避免 Agent 使用参考 workbook 时把内部字段二次包装或注册成伪原始字段。

### MCP Resources

| Resource | 用途 |
|---|---|
| `cwtwb://tool-surface` | 稳定工具调用顺序、保存语义和客户端使用规则 |
| `cwtwb://skills/index` | 列出阶段化 cwtwb authoring skills |
| `cwtwb://skills/data_quality` | 在 authoring 前进行本地 schema 检查和字段适配评估 |
| `cwtwb://skills/governance` | 本地命名和元数据规范 |
| `cwtwb://skills/synthetic_data` | 安全示例数据策略和连接指导 |
| `cwtwb://skills/design_advisor` | 面向受众的 dashboard 设计规格指导 |
| `cwtwb://skills/metric_blueprint` | 面向决策的指标契约指导 |
| `cwtwb://skills/calculation_builder` | Tableau 计算语法和 calculated field 指导 |
| `cwtwb://skills/chart_builder` | 图表选择和 encoding 指导 |
| `cwtwb://skills/dashboard_designer` | Dashboard layout 和组合指导 |
| `cwtwb://skills/formatting` | Formatting 和 styling 指导 |
| `cwtwb://skills/validation` | 验证工作流指导 |
| `cwtwb://skills/quality_review` | 基于证据的设计和可维护性评审指导 |
| `cwtwb://skills/documentation` | Workbook 交接和指标文档指导 |
| `file://docs/tableau_all_functions.json` | Tableau calculation function reference |
| `cwtwb://profiles/index` | Dataset profile index，当 profiles 已配置时可用 |

兼容别名：

```text
cwtwb://docs/manual-editing
cwtwb://docs/tool-surface
```

这些别名用于避免不够规范的客户端因为 `Unknown resource` 停止。新文档和 prompts 应使用上面的 canonical resources。

### MCP Tools

| Tool | 说明 |
|---|---|
| `create_workbook` | 加载 `.twb` 或 `.twbx` 模板，并初始化 rebuild-from-template workspace |
| `open_workbook` | 打开现有 `.twb` 或 `.twbx`，保留 worksheets 和 dashboards 供编辑 |
| `list_fields` | 列出可用 dimensions 和 measures |
| `list_worksheets` | 列出 active workbook 的 worksheet 名称 |
| `list_dashboards` | 列出 dashboards 及其 worksheet zones |
| `add_parameter` | 添加 what-if analysis 参数 |
| `add_calculated_field` | 添加 Tableau formula calculated field |
| `remove_calculated_field` | 删除已添加 calculated field |
| `clone_worksheet` | 克隆现有 worksheet 及其 worksheet window |
| `preview_worksheet_refactor` | mutation 前预览 worksheet-scoped field rewrites |
| `apply_worksheet_refactor` | 应用 worksheet-scoped field rewrites，并保留原 worksheet |
| `add_worksheet` | 添加空白 worksheet |
| `configure_chart` | 配置 chart type 和 field mappings |
| `configure_worksheet_style` | 应用 worksheet 级样式 |
| `configure_dual_axis` | 配置 dual-axis chart |
| `configure_chart_recipe` | 配置 `lollipop`、`donut`、`butterfly`、`calendar` 等 recipe chart |
| `add_dashboard` | 创建组合 worksheets 的 dashboard |
| `add_dashboard_action` | 添加 filter、highlight、URL 或 go-to-sheet action |
| `set_worksheet_caption` | 设置或清除 worksheet caption |
| `set_worksheet_hidden` | 通过 worksheet window metadata 隐藏或显示 worksheet |
| `generate_layout_json` | 生成并验证 dashboard flexbox layout JSON |
| `list_capabilities` | 展示 cwtwb 声明的支持边界 |
| `describe_capability` | 说明某 chart/feature 属于 core、advanced、recipe 还是 unsupported |
| `analyze_twb` | 按 capability catalog 分析 `.twb` 文件 |
| `diff_template_gap` | 总结 template 的 non-core gap |
| `validate_workbook` | 使用官方 Tableau TWB XSD schema 验证 workbook |
| `validate_workbook_api` | 通过 Tableau Cloud/Server REST API 验证 `.twb`，不发布 |
| `set_excel_connection` | 将 datasource 配置为本地 Excel workbook |
| `set_mysql_connection` | 将 datasource 配置为本地 MySQL 连接 |
| `set_tableauserver_connection` | 配置 Tableau Server 连接 |
| `set_hyper_connection` | 将 datasource 配置为本地 Hyper extract |
| `save_workbook` | 保存为 `.twb` 或 `.twbx` |
| `upload_workbook` | 发布 `.twb`/`.twbx` 到 Tableau Cloud，用于 openability evidence、`.twbx` validation 或 screenshots |
| `screenshot_workbook` | 对 `upload_workbook` 发布的 workbook 截图 |

Agent 需要特别注意的保存语义：

- `save_workbook(output_path=...)` 是默认 MCP 工具中唯一会把 active in-memory workbook 写到磁盘的工具。
- `validate_workbook()` 只验证 active workbook 或已有文件，不保存、不导出。
- `validate_workbook_api()` 通过 Tableau Cloud/Server REST API 做语法或语义验证，不发布。默认 `.twb` 云端验证优先使用它。
- `upload_workbook()` 会发布 workbook；只在需要发布/可打开性证据、`.twbx` 验证或截图时使用。
- `analyze_twb(file_path=...)` 需要已有 `.twb` 或 `.twbx` 路径。新生成 workbook 要先 `save_workbook`，再分析保存后的文件。
- Migration tools 用于把现有 workbook 指向新 datasource，不是保存 active workbook 的替代品。

### MCP Prompts

默认 MCP entrypoint 当前不注册 prompts。这是有意设计：默认 server 专注于通过 workbook engineering surface 做直接工具调用。

## Capability Model

### Core primitives

这些是项目应该持续承诺的稳定基础能力：

- **Bar**
- **Line**
- **Area**
- **Pie**
- **Map**
- **Text** / KPI cards
- Parameters and calculated fields
- Basic dashboard composition

### Advanced patterns

这些能力已支持，但属于更高层组合或交互特性，而不是默认基础表面：

- **Scatterplot**
- **Heatmap**
- **Tree Map**
- **Bubble Chart**
- **Dual Axis**：`mark_color_1/2`、`color_map_1`、`reverse_axis_1`、`hide_zeroline`、`synchronized`
- **Table Calculations**：通过 `add_calculated_field(table_calc="Rows")` 支持 `RANK_DENSE`、`RUNNING_SUM`、`WINDOW_SUM`
- **KPI Difference badges**：`MIN(1)` dummy axis + `axis_fixed_range` + `color_map` + `customized_label`
- **Donut (via extra_axes)**：使用 `configure_dual_axis(extra_axes=[...])` 构建多 pane Pie + white circle
- **Rich-text labels**：`configure_chart(label_runs=[...])`
- **Advanced worksheet styling**：pane/cell/datalabel/mark styles、per-field label/cell/header formats、axis tick control、tooltip disabling 等
- Dashboard zone primitives：**Text**、**Empty**、**Filter**、**ParamCtrl**、**Color Legend**
- Dashboard actions、worksheet captions、declarative JSON layout workflows

### Recipes and showcase patterns

这些模式当前可以生成，但应视为 recipe 或 example，而不是一等 API 承诺：

- **Donut**
- **Lollipop**
- **Bullet**
- **Bump**
- **Butterfly**
- **Calendar**

Recipe charts 通过统一的 `configure_chart_recipe` 工具暴露，避免公开 MCP surface 为每个 showcase 图表不断增加新工具。

### Capability-first workflow

当不确定某个能力是否属于稳定 SDK surface：

1. 使用 `list_capabilities` 查看声明边界
2. 使用 `describe_capability` 检查具体 chart、encoding 或 feature
3. 在追逐 showcase template 前使用 `analyze_twb` 或 `diff_template_gap`

这能让新功能工作与真实产品边界保持一致，而不是被某个样例 workbook 牵着走。

## Validation and Layouts

### 内置验证

#### 结构验证

`save()` 在发布最终文件前自动验证 TWB XML：

- 缺少 `<workbook>` 或 `<datasources>` 等 fatal errors 会抛出 `TWBValidationError`
- 缺少 `<view>` 或 `<panes>` 等 warnings 会记录但不阻止保存
- workbook 会先写到同目录临时文件，再从磁盘解析回来
- 已保存 `.twb` 或 `.twbx` 会在 vendored schema 可用时使用 Tableau TWB XSD 检查
- `.twb` 输出在配置 `.env` 凭据且服务器支持时也会运行 Tableau Cloud/Server REST API 语义验证
- 严格 XSD errors 会 fail-closed，已知 Tableau 兼容 warnings 不阻止保存
- 最终输出路径只有在临时文件验证通过后才会替换
- 可用 `editor.save("output.twb", validate=False)` 或 `editor.save("output.twbx", validate=False)` 关闭验证

#### XSD schema 验证

`TWBEditor.validate_schema()` 使用官方 Tableau TWB XSD schema 验证 workbook，并支持 2026.1/2026.2 版本感知。源码 checkout 使用 `vendor/tableau-document-schemas/`；安装包（包括 `uvx cwtwb`）使用 `cwtwb/vendor/` 下的 packaged copy。

```python
result = editor.validate_schema()
print(result.to_text())
# PASS  Workbook is valid against Tableau TWB XSD schema
# — or —
# FAIL  Schema validation failed (2 error(s)):
#   * Element 'workbook': Missing child element(s)...

result.valid
result.errors
result.schema_available
```

同样检查也可通过 MCP 工具使用：

```text
validate_workbook()
validate_workbook(file_path="out.twb")
```

### Dashboard Layouts

| Layout | 说明 |
|---|---|
| `vertical` | worksheets 从上到下排列 |
| `horizontal` | worksheets 横向并排 |
| `grid-2x2` | 最多四个 worksheet 的 2x2 网格 |
| `dict` or `.json` path | 更复杂 dashboard 的声明式自定义 layout |

嵌套 dashboard 使用规范 layout tree：

```json
{
  "type": "container",
  "direction": "horizontal",
  "children": [
    {"type": "worksheet", "name": "Sidebar", "fixed_size": 160},
    {
      "type": "container",
      "direction": "vertical",
      "children": [
        {"type": "worksheet", "name": "Header", "fixed_size": 80},
        {"type": "worksheet", "name": "Main Chart", "weight": 1}
      ]
    }
  ]
}
```

为了兼容旧 MCP prompts 和生成的 JSON 文件，`add_dashboard` 也接受 legacy container aliases，并递归标准化：`{"type": "horizontal", "children": [...]}` 和 `{"type": "vertical", "children": [...]}`。未知 layout node type 会抛出明确错误。

### Hyper-backed Example

`examples/hyper_and_new_charts.py` 使用包内置 `Sample - EU Superstore.hyper` extract，并通过 Tableau Hyper API 解析物理 `Orders_*` table 后切换 workbook 连接。无需 clone 仓库，安装 `pip install "cwtwb[examples]"` 后即可运行。

## Workbook Migration

cwtwb 包含迁移子系统，可把现有 `.twb` 切换到新 datasource，例如把基于一个 Excel 的 workbook 指向 schema 不同的新 Excel，或在同一数据集的不同语言版本间迁移。

### 工作方式

迁移是多步工作流，每一步都有 MCP tool 和 Python function：

```text
1. inspect_target_schema      → 扫描目标 Excel 并列出列
2. profile_twb_for_migration → 盘点 workbook 使用的字段
3. propose_field_mapping     → 模糊匹配源字段到目标列
4. preview_twb_migration     → dry-run：展示变更、blockers、warnings
5. apply_twb_migration       → 写出迁移后的 .twb + JSON reports
```

`migrate_twb_guided` 仍作为 Python convenience wrapper 可用，会顺序运行步骤 2-5，并在只剩低置信度匹配时自动暂停，返回 `warning_review_bundle` 供人工确认。

### Python Example

```python
from cwtwb.migration import migrate_twb_guided_json
import json

result = migrate_twb_guided_json(
    file_path="templates/SalesDashboard.twb",
    target_source="data/new_data_source.xlsx",
    output_path="output/SalesDashboard_migrated.twb",
)
bundle = json.loads(result)

if bundle["status"] == "warning_review_required":
    print(bundle["warning_review_bundle"])
    result = migrate_twb_guided_json(
        file_path="templates/SalesDashboard.twb",
        target_source="data/new_data_source.xlsx",
        output_path="output/SalesDashboard_migrated.twb",
        mapping_overrides={"Old Field Name": "New Column Name"},
    )
```

### MCP Tool Example

```text
inspect_target_schema(target_source="data/new_data_source.xlsx")

profile_twb_for_migration(
    file_path="templates/SalesDashboard.twb",
    target_source="data/new_data_source.xlsx"
)

propose_field_mapping(
    file_path="templates/SalesDashboard.twb",
    target_source="data/new_data_source.xlsx"
)

preview_twb_migration(
    file_path="templates/SalesDashboard.twb",
    target_source="data/new_data_source.xlsx"
)

apply_twb_migration(
    file_path="templates/SalesDashboard.twb",
    target_source="data/new_data_source.xlsx",
    output_path="output/SalesDashboard_migrated.twb"
)
```

### 输出文件

| File | Contents |
|---|---|
| `<output>.twb` | 字段引用已重写的迁移后 workbook |
| `migration_report.json` | 每个字段的状态：mapped / warning / blocked |
| `field_mapping.json` | 用于审计的最终 source-to-target field mapping |

### Scope 参数

`scope="workbook"` 会迁移所有 worksheets。传入 worksheet 名称可以限制到单个 sheet。

### 自包含示例

`examples/migrate_workflow/` 包含 template `.twb`、原始 Superstore Excel、中文 locale Superstore Excel 和可运行脚本：

```bash
python examples/migrate_workflow/test_migration_workflow.py
```

## Development

### Project Structure

```text
cwtwb/
|-- src/cwtwb/
|   |-- __init__.py
|   |-- capability_registry.py
|   |-- config.py
|   |-- charts/
|   |-- connections.py
|   |-- dashboard_actions.py
|   |-- dashboard_dependencies.py
|   |-- dashboard_layouts.py
|   |-- dashboards.py
|   |-- field_registry.py
|   |-- layout.py
|   |-- layout_model.py
|   |-- layout_rendering.py
|   |-- mcp/
|   |-- parameters.py
|   |-- skills/
|   |-- twb_analyzer.py
|   |-- twb_editor.py
|   |-- validate/
|   |-- validator.py
|   `-- server.py
|-- tests/
|-- examples/
|-- docs/
|-- pyproject.toml
`-- README.md
```

### 本地开发

```bash
pip install -e .
pytest --basetemp=output/pytest_tmp
python examples/scripts/demo_all_supported_charts.py
python examples/scripts/demo_hyper_and_new_charts.py
python examples/migrate_workflow/test_migration_workflow.py
cwtwb
```
