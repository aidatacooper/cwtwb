# Exec Overview Dashboard 复刻报告

> 目标: 用 cwtwb SDK (Python API) 完全复现 `templates/dashboard/Exec Overview.twb`
> 输出: `examples/superstore_recreated/Exec Overview Recreated.twb`

---

## 1. 当前能力总览

### 已实现 (SDK Python API)

| 功能 | API | 状态 |
|------|-----|------|
| 创建空工作簿 | `TWBEditor("")` | OK |
| Hyper 数据连接 | `set_hyper_connection()` | **有 bug** (见下) |
| 参数 (list domain) | `add_parameter()` | OK |
| 计算字段 (含 LOD) | `add_calculated_field()` | OK |
| 基础图表 (Bar/Text/Map/Area/Line) | `configure_chart()` | OK |
| 双轴图 | `configure_dual_axis()` | OK |
| 工作表样式 | `configure_worksheet_style()` | OK |
| 仪表板布局 (嵌套容器) | `add_dashboard()` + layout dict | OK |
| 仪表板交互 (highlight) | `add_dashboard_action()` | OK |

### 未实现 / 无法实现

| 功能 | 原因 |
|------|------|
| Table Calculation (RANK_DENSE) | SDK 不支持 |
| Bin (分箱) | SDK 不支持 |
| 位图 (logo / 社交图标) | SDK 不支持 image zone |
| 仪表板导航按钮 | SDK 不支持 |
| 圆环仪表盘 (gauge) | SDK 不支持 |
| Donut recipe (`configure_chart_recipe`) | **仅 MCP 工具层**, 不在 TWBEditor 类上 |
| GanttBar mark | SDK `configure_chart` 未暴露此 mark type |
| Shape mark (条件指标绿点) | SDK 不支持 shape encoding |

---

## 2. Bug 跟踪

### Bug #4: Top N 过滤器不生效 ✅ 已修复

**现象**: `Sales by Top Manufacturers` 和 `Top 5 Locations` 两个工作表设置了 Top 5 筛选，但在 Tableau 中实际显示全部数据，过滤器不起作用

**根因**: **SDK** — `builder_base.py` 的 `_add_filters` 方法在生成 Top N `<groupfilter>` 时有三处缺陷：

1. **`expression` 格式错误**: 中间 `<groupfilter>` 的 `expression` 属性使用完整列实例引用 `[federated...][sum:...:qk]`，Tableau 要求公式语法 `SUM([Calculation_...])`
2. **缺少 `<slices>` 元素**: Tableau 需要 `<view>` 下存在 `<slices><column>...</column></slices>` 才能正确识别 Top N 过滤的维度域
3. **缺少 `ui-manual-selection` 属性**: 最内层 `<groupfilter>` 缺少 `ns0:ui-manual-selection="true"`、`ns0:ui-manual-selection-all-when-empty="true"`、`ns0:ui-manual-selection-is-empty="true"` 三个属性

**修复**: `src/cwtwb/charts/builder_base.py`
- `expression` 改为 `f"{by_ci.derivation.upper()}({by_ci.column_local_name})"` 生成公式语法
- 新增 `<slices>` 元素，自动写入被过滤维度的完整列引用，位置在 `<aggregation>` 前
- 补充三个 `ns0:ui-manual-selection*` 属性

**同时修复**: `examples/superstore_recreated/build_exec_overview.py`
- `Top 5 Locations` 的 `configure_chart` 增加 `customized_label` 参数，消除 Tableau 默认渲染时出现的冗余 "State/Province" 列标题

---

### Bug #1: KPI Difference 工作表 — 列/轴/标签/颜色配置错误

**现象**: Sales KPI Difference 等工作表渲染不正确

**正确做法 (手动修复后)**:
- **列**: 使用 `MIN(1)` 作为列 (dummy measure), 而不是 `SUM(Sales Difference)`
- **轴**: 自定义固定范围 `min=0, max=1` (`range-type='fixed'`)
- **标记卡颜色**: `聚合(Sales Color Filter)` — derivation 应为 `User` (AGG), BAD→红色 `#e15759`, GOOD→绿色
- **标记卡标签**: `聚合(Sales Difference)` — derivation 应为 `User` (AGG)
- **自定义标签**: `<Sales Difference> vs PY` (带 "vs PY" 后缀)
- **文本格式**: 百分比 `p0.00%`
- **Mark sizing**: `marks-scaling-off`

**根因**: **SDK** — `configure_chart()` API 缺少以下能力:
1. 不支持自定义轴范围 (fixed min/max)
2. 不支持自定义标签模板 (customized-label with "vs PY")
3. 不支持 mark-sizing-off
4. 不支持 `MIN(1)` 作为 dummy 度量列
5. 颜色编码不支持指定 palette 映射 (BAD→red, GOOD→green)
6. 标签字段的 derivation 模式不正确 (应为 `User`/AGG)

**修复方式**: 用户在 Tableau 中手动修复了 Sales KPI Difference, 其他三个 (Profit/Quantity/Returns) 仍使用旧的简化模式

---

### Bug #2: 数据连接 — 表名猜测错误

**现象**: `set_hyper_connection(table_name="Extract")` 生成的 relation 使用 `Extract` 作为表名

**正确做法**: 应调用 API 读取 Hyper 文件 schema, 获取实际表名:
- `Orders_ECFCA1FB690A41FE803BC071773BA862`
- `People_D73023733B004CC1B3CB1ACF62F4A965`
- `Returns_2AA0FE4D737A4F63970131D0E7480A03`

且应生成 `<relation type='collection'>` 包含多表 + 列映射 `<cols><map ...>` + 表间关系 `<relationships>`

**根因**: **SDK** — `set_hyper_connection()` 不读取 Hyper 文件内部 schema, 只接受用户传入的 `table_name` 字符串, 无法处理多表 Hyper

---

### Bug #3: Mark type "Circle Mark" 不是有效枚举值

**现象**: Tableau 报错 `value 'Circle Mark' not in enumeration`

**正确值**: `"Circle"` (不含 "Mark" 后缀)

**根因**: **脚本** — 调用方传入了错误的 mark type 字符串, SDK 本身不做枚举校验

**状态**: 已修复

---

## 3. 样式学习 (从手动修复的 TWB 提取)

### KPI Difference 正确 XML 模式

```xml
<!-- 1. MIN(1) 作为 dummy 列 -->
<column caption='MIN(1)' datatype='integer' name='[Calculation_xxx]'
  role='measure' type='quantitative' user:unnamed='Sales KPI Difference'>
  <calculation class='tableau' formula='MIN(1)' />
</column>

<!-- 2. 固定轴范围 0-1 -->
<style-rule element='axis'>
  <format attr='display' value='false' />
  <format attr='display' class='0' field='[...usr:Calculation_xxx:qk]'
    scope='cols' value='true' />
  <encoding attr='space' class='0' field='[...usr:Calculation_xxx:qk]'
    field-type='quantitative' max='1' min='0' range-type='fixed'
    scope='cols' type='space' />
</style-rule>

<!-- 3. Mark sizing off -->
<mark-sizing mark-sizing-setting='marks-scaling-off' />

<!-- 4. 颜色和标签 encodings (都用 User/AGG derivation) -->
<encodings>
  <color column='[...usr:ColorFilter:nk]' />
  <text column='[...usr:Difference:qk]' />
</encodings>

<!-- 5. 自定义标签 "X vs PY" -->
<customized-label>
  <formatted-text>
    <run fontalignment='2' fontname='Tableau Medium' fontsize='8'>    &lt;</run>
    <run fontalignment='2' fontname='Tableau Medium' fontsize='8'>[ds].[usr:Diff:qk]</run>
    <run fontalignment='2' fontname='Tableau Medium' fontsize='8'>&gt; vs PY</run>
  </formatted-text>
</customized-label>

<!-- 6. 文本格式: 百分比 -->
<style-rule element='cell'>
  <format attr='text-format' field='[...usr:Diff:qk]' value='p0.00%' />
</style-rule>

<!-- 7. 颜色映射 (datasource 级别) -->
<style-rule element='mark'>
  <encoding attr='color' field='[...usr:ColorFilter:nk]' type='palette'>
    <map to='#e15759'>
      <bucket>"BAD"</bucket>
    </map>
  </encoding>
</style-rule>
```

### 数据连接正确 XML 模式

```xml
<!-- 多表 Hyper 连接 -->
<relation type='collection'>
  <relation connection='hyper.xxx' name='Orders_xxx'
    table='[Extract].[Orders_xxx]' type='table' />
  <relation connection='hyper.xxx' name='People_xxx'
    table='[Extract].[People_xxx]' type='table' />
  <relation connection='hyper.xxx' name='Returns_xxx'
    table='[Extract].[Returns_xxx]' type='table' />
</relation>

<!-- 列映射 -->
<cols>
  <map key='[Sales]' value='[Orders_xxx].[Sales]' />
  <!-- ... -->
</cols>

<!-- 表间关系 -->
<relationships>
  <relationship>
    <expression op='='>
      <expression op='[Region]' />
      <expression op='[Region (People_xxx)]' />
    </expression>
  </relationship>
</relationships>
```

---

## 4. SDK 增强建议 (按优先级)

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | Hyper schema 读取 | `set_hyper_connection()` 应能读取 hyper 文件获取表名和列名 |
| P0 | 自定义轴范围 | `configure_chart()` 支持 `axis_fixed_range=(min, max)` |
| P1 | 自定义标签模板 | 支持 `customized_label="<field> vs PY"` 模式 |
| P1 | 颜色 palette 映射 | 支持 `color_map={"BAD": "#e15759", "GOOD": "#03a44e"}` |
| P1 | Mark sizing off | 支持 `mark_sizing_off=True` |
| P2 | 文本格式 | 支持 `text_format={"field": "p0.00%"}` |
| P2 | MIN(1) dummy 度量 | 可内建为 KPI badge 的标准模式 |

---

## 5. 测试进度

- [x] 脚本能成功运行生成 TWB
- [x] TWB 能在 Tableau 中打开 (修复 Circle Mark 枚举问题)
- [x] Top N 过滤器生效 (Sales by Top Manufacturers / Top 5 Locations 均过滤到 Top 5)
- [ ] KPI Difference 工作表样式正确 (仅 Sales 手动修复, 其他 3 个待修复)
- [ ] 数据连接读取 Hyper schema (当前硬编码表名)
- [ ] 仪表板整体布局与原版一致
- [ ] 颜色/字体/间距与原版一致
