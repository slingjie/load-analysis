# 储能充放次数测算 - 开发任务清单（按天）

版本：v0.1（草案）
编码：UTF-8

## 概述
- 目标：在当前系统中落地“储能充放次数测算（window_avg 口径）”，并提供参数输入、结果可视化与 Excel 导出。
- 口径默认：window_avg、physics、initial_soc=0.05、合并阈值=30分钟（前端可调）、按需量模式（monthly_demand_max）后端按月自动统计最大需量。
- 报表：单文件多 Sheet；下载：静态目录直连。

### 参考资源
- 参考程序根路径：D:\Desktop\ai\1028负荷展示和tou配置\参考储能次数测算程序文件夹
- 关键文件：app/services/compute.py、app/services/strategy.py、app/utils/tou.py、app/schemas.py、app/main.py

## 第一天：后端接口与契约
- [ ] 新增 `POST /api/storage/cycles`（multipart：`file` + `payload`）。
- [ ] 数据模型：
  - [ ] `StorageParams`（含 merge_threshold_minutes）。
  - [ ] `StrategySource`（`monthlySchedule`、`dateRules`）。
  - [ ] `MonthlyTouPrices`（12个月档位→价格）。
  - [ ] `CyclesRequest`/`CyclesResponse`（年/月/日、QC、`excel_path`）。
- [ ] 负荷解析与规范化为 `timestamp, load_kw`，支持 CSV/XLSX。
- [ ] 入参校验与错误处理（400/500）。

## 第二天：策略与 TOU 映射
- [ ] 从格子按 15 分钟抽取“充/放/待机”片段；实现“跨日同类合并”。
- [ ] 合并到最多两次循环（c1/c2）：
  - [ ] 小片段阈值（默认30分钟，可配置）。
  - [ ] 超 2 次循环时按“影响最小合并”。
- [ ] 生成 TOU 段与价：基于当日格子档位 + 当月价格 → `[start,end)`，映射至 15 分钟时点；缺价记录 QC。

## 第三天：window_avg 计算与汇总
- [ ] 许可功率：
  - [ ] `allow_ch = limit_kw - reserve_charge_kw - avg_load`
  - [ ] `allow_dis = avg_load - reserve_discharge_kw`
  - [ ] limit_kw：
    - [ ] `monthly_demand_max`：后端按月自动统计最大需量（kW）。
    - [ ] `transformer_capacity`：`kva * power_factor`。
- [ ] 电网侧能量（physics）：`E_in_grid = base * DOD / η`，`E_out_grid = base * DOD * η`。
- [ ] 满充/放率与日循环数；日/月/年汇总与 QC。
- [ ] 响应结果返回（含 `excel_path` 占位）。

## 第四天：报表导出与静态下载
- [ ] Excel 单文件多 Sheet：
  - [ ] Sheet1：计算结果（日、月、年概要）。
  - [ ] Sheet2：TOU 配置快照。
  - [ ] Sheet3：缺失/缺价明细、策略合并说明。
- [ ] 输出到 `outputs/<yyyyMMdd_HHmmss>/...`，返回相对路径（静态直连）。
- [ ] 清理策略（最近 N 批次或按天数）。

## 第五天：前端“储能测算页”与联调
- [ ] 新增 `StorageCyclesPage`：
  - [ ] 表单：容量、倍率、效率、SOC 上/下限、`initial_soc`、余量、计费口径、能量公式（默认 physics）、跨日结转（默认关）、合并阈值（默认30，可调）。
  - [ ] 文件上传（本页独立）；提交调用后端；异常与 QC 提示。
  - [ ] 图表：月度次数柱状、日度次数折线；头部年累计次数。
  - [ ] 报表下载入口（静态链接）。

## 第六天：对拍与优化
- [ ] 用样例数据对拍（见“验收要点与测试用例.md”）：年累计、月度、日度一致。
- [ ] 边界优化：
  - [ ] 多于两次循环合并效果与提示。
  - [ ] 价格缺失/数据缺失的 QC 完整性。
  - [ ] 性能优化（全年数据秒级~十秒级）。

## 第七天：文档与交付
- [ ] 接口说明与用户指南（中文）。
- [ ] 演示脚本：导入→配置→计算→导出→下载→查看图表。
- [ ] 交付总结与后续增强（step_15min、能量轨迹、收益）。

---

备注：若遇外部因素影响进度，优先确保第1~第4天的后端链路与报表导出；前端联调可在第5天并行推进。
