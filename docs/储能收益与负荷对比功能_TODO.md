# 储能收益与负荷对比功能 - 开发 TODO 列表

> 关联 PRD：`docs/储能收益与负荷对比功能 PRD.md`  
> 关联实现路线：`docs/储能收益与负荷对比功能_实现路线草案.md`

本文件用于跟踪“储能收益与负荷对比功能”的开发任务进度，按模块拆解为可执行的 checklist。实际开发中可在 IDE / Git 工具中勾选完成项。

---

## 一、后端开发 TODO（FastAPI + 服务层）

### 1. 数据模型（schemas.py）

- [ ] 新增 `StorageProfit` 模型（revenue/cost/profit/discharge_energy_kwh/charge_energy_kwh/profit_per_kwh）。  
- [ ] 新增 `StorageProfitWithFormulas` 模型（main/physics/sample 三个可选字段）。  
- [ ] 扩展 `StorageCyclesDay` 增加 `profit: Optional[StorageProfitWithFormulas] = None`。  
- [ ] 扩展 `StorageCyclesMonth` 增加同名字段。  
- [ ] 扩展 `StorageCyclesYear` 增加同名字段。  
- [ ] 检查/更新 Pydantic 字段描述，保证中文注释清晰、与 PRD 用语一致。

### 2. 逐点收益计算（backend/services/cycles.py）

- [ ] 梳理现有 step_15min 逻辑（`base_kwh_step15` 相关代码），确认可复用部分。  
- [ ] 定义并实现 `compute_profit_summary_step15(...)` 函数：  
  - [ ] 从 `series_15m` + `daily_ops` + `limit_info` + `storage_cfg` 构造逐点 `p_batt(t)`。  
  - [ ] 根据 `energy_formula` 计算 `p_in_grid/p_out_grid` 与 `e_in_grid/e_out_grid`。  
  - [ ] 结合 `price_series` 计算 `cost_t/rev_t/profit_t`。  
  - [ ] 按日汇总为 `StorageProfit` 对应的 dict。  
  - [ ] 按月/年聚合出 `StorageProfit` 汇总。  
  - [ ] 可选：同时计算 physics/sample 双口径，填充 `StorageProfitWithFormulas.physics/sample`。  
- [ ] 在收益计算中处理缺价点：跳过收益计算、累计到 `missing_prices`、记录提示 note。  
- [ ] 为收益计算添加必要的日志（logger.debug/info），便于调试和后期排查。

### 3. 挂接到 `/api/storage/cycles`（backend/app.py）

- [ ] 在 `compute_storage_cycles` 中调用 `compute_profit_summary_step15`：  
  - [ ] 传入已构建的 `series_15m`、`daily_ops`、`limit_info`、`storage_cfg`、`price_series`、`energy_formula`。  
  - [ ] 拿到日/月/年收益结果并映射到 `StorageCyclesDay/Month/Year.profit`。  
- [ ] 确保在收益计算失败或返回为空时，仍能正常返回原有 cycles 结果，并在 `qc.notes` 中附加提示。  
- [ ] 手动用一个简单数据集调用 `/api/storage/cycles`，检查响应 JSON 中 `profit` 字段结构是否符合预期。

### 4. 新增曲线接口 `/api/storage/cycles/curves`（第二阶段）

- [ ] 设计并实现 `StorageCurvesResponse` Pydantic 模型（如需）：  
  - [ ] `date`  
  - [ ] `points_original` / `points_with_storage`  
  - [ ] `summary` 中的最大需量、TOU 分档电量/电费、当日 profit 等字段。  
- [ ] 在 `backend/app.py` 中新增 `@app.post("/api/storage/cycles/curves")` 路由：  
  - [ ] 解析 `payload` 与 `date` 参数。  
  - [ ] 复用 `compute_storage_cycles` 的负荷解析与参数构建逻辑。  
  - [ ] 生成指定日期的 `points_original`。  
  - [ ] 使用逐点收益/功率逻辑生成 `points_with_storage`（`load_with_storage = load_original + p_grid_effect`）。  
  - [ ] 汇总并返回 `summary` 指标。  
- [ ] 对异常情况（日期无数据、payload 不合法等）返回合理的 HTTP 错误和中文提示。

---

## 二、前端开发 TODO（React + TS）

### 1. 类型与接口（types.ts / storageApi.ts）

- [ ] 在 `types.ts` 中新增：  
  - [ ] `BackendStorageProfit`  
  - [ ] `BackendStorageProfitWithFormulas`  
  - [ ] 扩展 `BackendStorageCyclesDay/Month/Year` 增加 `profit?: BackendStorageProfitWithFormulas | null`。  
- [ ] 新增曲线接口类型：  
  - [ ] `BackendStorageCurvesPoint`  
  - [ ] `BackendStorageCurvesSummary`  
  - [ ] `BackendStorageCurvesResponse`。  
- [ ] 在 `storageApi.ts` 中更新 `computeStorageCycles` 的返回类型引用（保持向后兼容）。  
- [ ] 新增 `fetchStorageCurves(payload, date)` 方法，封装 `/api/storage/cycles/curves` 调用与错误处理。

### 2. 新页面组件 `StorageProfitPage`

- [ ] 新建 `components/StorageProfitPage.tsx` 文件。  
- [ ] 定义 `Props`：`scheduleData`、`externalCleanedData`、（可选）`storageCyclesResult`。  
- [ ] 实现内部状态管理：  
  - [ ] 当前选择日期 `selectedDate`。  
  - [ ] 曲线数据 `curvesData`（`BackendStorageCurvesResponse | null`）。  
  - [ ] Loading / Error 状态。  
- [ ] 组件布局：  
  - [ ] 顶部参数/说明区域：展示当前 `energy_formula` 及简单说明。  
  - [ ] 收益汇总卡片区：基于 `/api/storage/cycles` 的 `year/months.days` 中 `profit` 字段。  
  - [ ] 日度曲线对比区：原负荷 vs 储能后负荷（可复用 `EChartTimeSeries`）。  
  - [ ] 指标对比表区：最大需量前后、分 TOU 档电量/电费、当日收益等。  
- [ ] 文案与提示：全部使用中文，并与 PRD 术语保持一致。

### 3. App 导航与页面挂接（App.tsx）

- [ ] 扩展 `currentPage` 的联合类型，增加 `'profit'`。  
- [ ] 在顶部导航区域新增 “收益与负荷对比” 按钮：点击切换到 `'profit'`。  
- [ ] 在 JSX 中挂载 `StorageProfitPage`：  
  - [ ] 传入 `scheduleData={appState}`。  
  - [ ] 传入 `externalCleanedData={loadCleanedData}`。  
  - [ ] 视情况传入 `storageCyclesResult`（若需要与 StorageCycles 联动）。  
- [ ] 更新悬浮目录 `navSections`，为 `'profit'` 页面增加合适的小节配置（比如“收益汇总”、“曲线对比”、“指标对比”）。

### 4. 与现有 StorageCycles 页联动（可选增强）

- [ ] 在 StorageCycles 页中，支持点击某一日的 cycles/尖段统计，跳转到 StorageProfit 页并自动选中该日期。  
- [ ] 通过 URL 参数或全局状态传递 `selectedDate`，在 StorageProfit 页初始化时立即发起曲线请求。  

---

## 三、测试与验证 TODO

### 1. 手工测试用例

- [ ] 构造一个简单的 1 个月负荷数据（平稳负荷 + 清晰尖峰），手工在 Excel 中计算：  
  - [ ] 验证 physics 口径下的收益与程序一致。  
  - [ ] 验证 sample 口径下的收益与程序一致。  
- [ ] 验证 energy_formula 切换：同一数据下 physics / sample 的收益变化符合直觉。  
- [ ] 验证缺价点处理：部分 TOU 未设置价格时，不报错且收益略小，QC 中有缺价统计。  
- [ ] 验证极端配置：容量极大/极小、效率极低/极高情况下，收益与曲线不出现 NaN/Infinity。

### 2. 回归检查

- [ ] 在合并代码前，使用旧版本的 `/api/storage/cycles` 请求样例，对比新旧响应中：  
  - [ ] `year/months/days` 的 `cycles` 数值完全一致。  
  - [ ] `qc` 字段中原有内容不变（仅新增 notes 时需确认合理性）。  
- [ ] 检查前端旧功能：  
  - [ ] TOU 配置页、负荷分析页、StorageCycles 页在新代码下仍正常工作。  
  - [ ] 新增页面未对旧页产生布局/状态副作用。

---

## 四、文档与后续工作 TODO

- [ ] 根据最终实现，回填/修订 `docs/储能收益与负荷对比功能 PRD.md` 中实际字段命名与接口路径（若有调整）。  
- [ ] 在 README 或其他对外文档中加入简要说明：  
  - [ ] 如何启用储能收益与负荷对比功能。  
  - [ ] 后端接口概览（cycles + curves）。  
- [ ] 视业务反馈，收集下一阶段需求（如 SOC 曲线、更多计费口径、多方案对比等），记录到新的待办文档中。

