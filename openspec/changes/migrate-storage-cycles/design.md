# 设计说明：储能充放次数测算（window_avg MVP）

## 架构总览
- 前端（React）：新增 `StorageCyclesPage`，复用现有 TOU 配置、日期规则与月度价格；本页独立上传负荷文件，提交至后端，展示日/月/年 cycles 与图表；提供报表下载入口。
- 后端（Python FastAPI/Flask 现有栈）：新增 `POST /api/storage/cycles`，完成入参校验、负荷解析、策略→掩码构造、TOU 映射、window_avg 计算、汇总、Excel 导出与静态下载链接生成。
- 存储：输出报表至 `outputs/<yyyyMMdd_HHmmss>/...`，静态直连（相对路径返回）。

## 数据模型与契约（草案）
- StorageParams：`capacity_kwh, c_rate, single_side_efficiency, depth_of_discharge, soc_min, soc_max, initial_soc=0.05, reserve_charge_kw, reserve_discharge_kw, metering_mode: 'monthly_demand_max'|'transformer_capacity', transformer_capacity_kva?, transformer_power_factor?, calc_style='window_avg', energy_formula='physics'|'sample', soc_carry_over=false, merge_threshold_minutes=30`
- StrategySource：`monthlySchedule`（月→24h格子→充放/待机），`dateRules`（工作日/节假日/自定义）。
- MonthlyTouPrices：`{1..12: {tierKey: price}}`。
- CyclesRequest：`{storage, strategySource, monthlyTouPrices}` + `file`。
- CyclesResponse：`{year: {...}, months: [...], days: [...], qc: {...}, excel_path: 'outputs/..../result.xlsx'}`。

## 策略构造与合并
1) 从 24 小时格子抽取“充/放/待机”片段（15 分钟粒度）；
2) 跨日拼接：当日末尾与次日开头若同类则合并；
3) 小片段阈值（默认 30 分钟）用于去噪；
4) 超过两次循环时，按“影响最小合并”策略收敛为 c1/c2 两次循环；
5) 产出 c1/c2 的 charge/discharge 掩码。

## 许可功率与计费上限
- `allow_ch = limit_kw - reserve_charge_kw - avg_load`
- `allow_dis = avg_load - reserve_discharge_kw`
- `limit_kw` 口径：
  - `monthly_demand_max`：后端按月从负荷数据统计最大需量（kW）。
  - `transformer_capacity`：`kva * power_factor`。

## 计算公式与汇总（window_avg，physics 默认）
- 电网侧能量：`E_in_grid = base * DOD / η`，`E_out_grid = base * DOD * η`（η 为单边效率）。
- 满充/放率：`full_charge_ratio = min(E_in_grid / capacity, 1)`；`full_discharge_ratio = min(E_out_grid / capacity, 1)`。
- 日循环数：`cycles_day = min(fc1_charge, fc1_discharge) + min(fc2_charge, fc2_discharge)`。
- 汇总：输出日表、月汇总、年累计；QC 含缺价/缺失/合并说明等。

## 报表与静态下载
- Excel 单文件多 Sheet：
  - Sheet1：结果（日、月、年概要）；
  - Sheet2：TOU 配置快照（按月/档位/价格）；
  - Sheet3：缺失/缺价明细与策略合并说明。
- 命名：`<源文件名>_计算结果.xlsx`；路径：`outputs/<yyyyMMdd_HHmmss>/...`；返回相对路径供前端拼接下载。

## 性能与内存
- 年度 96×365 点规模：目标秒级~十秒级完成；尽量采用向量化与分段聚合；Excel 写入批量化。

## 错误处理与 QC
- 负荷文件格式/列名校验、日期连续性检查、重采样与缺失策略、缺价统计、无效日列表；所有异常进入 QC，接口返回 200/400 对应场景明确。

## 未来扩展
- step_15min（SOC 逐点积分）、能量轨迹与收益；签名 URL 下载；更多计费口径。

