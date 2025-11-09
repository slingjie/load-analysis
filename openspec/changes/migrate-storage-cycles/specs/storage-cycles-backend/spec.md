## ADDED Requirements

### Requirement: 接口与入参契约（POST /api/storage/cycles）
系统应提供 `POST /api/storage/cycles` 接口，接收负荷文件（CSV/XLSX）与 JSON `payload`，完成参数校验并返回计算结果与报表下载路径。

#### Scenario: 成功请求返回计算结果
- 给定包含 `timestamp, load`（或 `timestamp, load_kw`）的负荷文件与符合契约的 `payload`（含 StorageParams、StrategySource、MonthlyTouPrices），
- 当调用 `POST /api/storage/cycles`，
- 则返回状态 200，JSON 含 `days[]`、`months[]`、`year{}`、`qc{}`、`excel_path`。

#### Scenario: 入参错误与异常处理
- 给定缺少必须字段或文件格式错误，
- 当调用接口，
- 则返回 400 并包含明确错误信息；内部异常返回 500 并带通用错误与追踪 ID。

### Requirement: 策略构造与最多两次循环（c1/c2）
从 24 小时格子与日期规则构造日内“充/放/待机”片段，支持跨日拼接；最终合并到最多两次循环（c1/c2）。

#### Scenario: 跨午夜合并
- 若当日 23:00–24:00 与次日 00:00–02:00 同类（如充电），
- 则应自动拼接为一个连续片段，供后续合并与计算。

#### Scenario: 小片段阈值与影响最小合并
- 当出现多于两次循环且存在小于阈值（默认 30 分钟）的片段，
- 则按“时长阈值 + 影响最小合并”策略收敛为 c1/c2，并在 QC 中记录合并说明。

### Requirement: TOU 段价映射与缺价处理
基于当日格子档位与当月价格生成 `[start,end)` 段并映射至 15 分钟点；缺价应计入 QC 并影响窗口均价。

#### Scenario: 缺价点与均价剔除
- 当某段或点位缺少价格时，
- 则该窗口均价计算应剔除缺价点；若全段缺价，均价为 `null`，并在 QC 累计缺价点位与记录数。

### Requirement: 许可功率与计费口径
系统应同时支持 `monthly_demand_max` 与 `transformer_capacity` 两种上限口径。

#### Scenario: 需量口径自动统计
- 在 `monthly_demand_max` 模式下，
- 系统应按月从负荷数据自动统计最大需量（kW），并作为 `limit_kw` 参与计算。

#### Scenario: 变压器容量口径
- 在 `transformer_capacity` 模式下，
- 系统应以 `transformer_capacity_kva * transformer_power_factor` 作为 `limit_kw`。

### Requirement: 计算口径（window_avg，physics 默认）
系统应实现 window_avg 计算口径，并以 `physics` 为默认能量公式。

#### Scenario: 电网侧能量换算（physics）
- 给定单边效率 η 与 DOD，
- 则充电能量（电网侧）= `base * DOD / η`，放电能量（电网侧）= `base * DOD * η`。

#### Scenario: 日循环数计算
- 对于 c1/c2 两次循环，
- 则 `cycles_day = min(fc1_charge, fc1_discharge) + min(fc2_charge, fc2_discharge)`，并汇总为月度与年度结果。

### Requirement: 报表导出与静态下载
系统应生成单文件多 Sheet 的 Excel 报表并提供静态直连下载路径。

#### Scenario: 多 Sheet 与命名
- 结果文件包含：Sheet1（结果：日、月、年概要）、Sheet2（TOU 配置快照）、Sheet3（缺失/缺价明细与合并说明），
- 命名规则为 `<源文件名>_计算结果.xlsx`，保存于 `outputs/<yyyyMMdd_HHmmss>/...` 并返回相对路径 `excel_path`。

### Requirement: 性能与稳定性
全年（96×365）规模在常规环境下应达到秒级~十秒级响应；大文件/异常文件错误提示清晰。

#### Scenario: 性能目标
- 给定全年 96×365 点负荷数据，
- 当计算完成时，
- 则端到端响应时间在秒级~十秒级（视环境）；内存占用稳定，不出现 OOM。

