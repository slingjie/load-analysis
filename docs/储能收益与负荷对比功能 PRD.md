# 储能收益与负荷对比功能 PRD（重排版）

## 0. 文档信息

- 文档名称：储能收益与负荷对比功能 PRD  
- 版本：v1.0（草案）  
- 适用系统：现有“负荷分析 + TOU 配置 + 储能次数测算”工具  
- 关联文档：  
  - `docs/储能次数计算对话关键内容记录.md`  
  - `docs/储能次数计算待办.md`  

---

## 1. 背景与范围

### 1.1 背景

当前系统已完成“储能充放次数测算”核心能力，主要包括：

- 基于 TOU 电价、充放逻辑（格子配置）、日期规则和负荷数据：
  - 构建 15 分钟负荷序列 `series_15m`
  - 生成按日的运行逻辑 `daily_ops`、C1/C2 窗口掩码 `daily_masks`
  - 计算日/月/年的等效满充满放次数（`cycles`）
  - 生成 `window_debug` 报表，输出：
    - 窗口能量：`base_kwh`、`e_grid_kwh_*`
    - 满充/满放率：`full_ratio_*`
    - step_15min 对拍列：`*_step15`

- 已具备“尖段放电占比”分析（`tip_discharge_summary`），可以回答：
  - 尖段平均负荷
  - 尖段时长、能量需求
  - 当前容量下尖段放电满足程度（0–100%）

但现有结果主要聚焦于“循环次数 / 能量窗口”，尚未体现：

- 经济收益（充电成本、放电收入、净收益）
- 储能投运前后负荷曲线的变化（削峰填谷效果）

### 1.2 目标

在现有“储能充放次数测算”基础上，新增：

1. **收益计算能力**

   - 在 15 分钟粒度上，基于实际充放电量与电价计算：
     - 充电成本（cost）
     - 放电收入（revenue）
     - 净收益（profit）
   - 支持日 / 月 / 年三级汇总，与现有 `cycles`、`tip_discharge_summary` 统一输出。

2. **负荷曲线对比能力**

   - 对比“原始负荷曲线 vs 引入储能后的负荷曲线”：
     - 可视化削峰填谷效果
     - 支持选择指定日期查看双曲线
     - 输出需量、电量、电费等关键指标的前后对比

3. **前端展示与交互**

   - 新增一页增加“收益与负荷对比”模块：
     - 曲线图：原负荷 vs 储能后负荷
     - 收益与费用汇总卡片 / 表格
     - 与现有 `energy_formula`（physics/sample）设置联动，保持主口径一致

### 1.3 范围说明

- 本 PRD 覆盖：
  - 后端收益计算逻辑
  - 后端负荷对比数据输出
  - 前端 StorageCycles 页面新增展示模块

- 本 PRD 不覆盖（保留在 `储能次数计算待办.md`）：
  - StorageCycles 既有 UI 布局优化
  - 配置导入导出、保存配置的细节
  - “step_15min 作为 SOC 逐点积分模式、跨日 SOC 结转”的实现  
    > 本期 step_15min 仅用于能量/收益积分与曲线对比，不改变 `cycles` 口径、不实现 SOC 仿真。

---

## 2. 术语与统一口径

### 2.1 关键术语

- **原始负荷曲线（原负荷）**  
  导入的未应用储能策略的负荷时间序列，记为 `load_original(t)`，粒度为 15 分钟。  
  在代码中对应 `series_15m["load_kw"]`。

- **储能出力（对电网视角）**

  采用“对电网为正”的统一约定：

  - `p_grid_effect(t) > 0`：从电网吸电（充电），对电网等效为“增加负荷”
  - `p_grid_effect(t) < 0`：向电网送电（放电），对电网等效为“降低负荷”

- **储能后负荷曲线（新负荷）**

  引入储能策略后，对电网的等效负荷序列：

  ```text
  load_with_storage(t) = load_original(t) + p_grid_effect(t)
  ```

  粒度为 15 分钟。

- **单边效率 η**  
  `single_side_efficiency`，0 < η ≤ 1。

- **DOD（Depth of Discharge）**  
  `depth_of_discharge`，用于折算“电池侧基数能量”与“电网侧能量”之间的比例。

- **时间粒度与日界**

  - 所有计算基于 15 分钟网格（Δt = 0.25 h）。
  - 时间统一转为“本地朴素时间”（`Asia/Shanghai`），与 TOU 配置与日期规则保持一致。
  - window_avg 逻辑已启用“跨午夜拼接（首尾同类窗口合并）”。

### 2.2 能量折算口径

#### 2.2.1 physics 口径（主物理口径）

以“电池侧基数能量 base_kwh”为起点折算到电网侧：

- 电网侧充电量：`E_in_grid = base_kwh × DOD / η`
- 电网侧放电量：`E_out_grid = base_kwh × DOD × η`

其中 `base_kwh` 来源于：

- 窗口平均法：`base_kwh = allow_kw × window_hours`
- 逐点积分：`base_kwh_step15 = Σ_t (allow_kw(t) × 0.25h)`

#### 2.2.2 sample 口径（对拍/手算口径）

保持与手算常见公式一致：

- 电网侧充电量：`E_in_grid = base_kwh / DOD × η`
- 电网侧放电量：`E_out_grid = base_kwh / DOD / η`

说明：

- physics 更符合能量守恒的物理过程，当前 cycles 主口径已采用 physics。
- sample 用于与手工估算公式对拍，方便用户校验。

---

## 3. 现有实现综述（作为前置条件）

### 3.1 负荷分析与 TOU 配置

- Load Analysis：
  - `/api/load/analyze`：上传负荷文件 → 质量分析 + 清洗后的点序列 `cleaned_points`。
  - 输出 `cleaned_points(t)` 可在前端与 StorageCyclesPage 复用。

- TOU + 储能运行逻辑：
  - TOU 档位（尖/峰/平/谷等） + 运行逻辑（待机/充电/放电）通过时间格子配置完成；
  - 月度 schedule + 日期规则 `dateRules` → `daily_ops`（每日日 0..23 小时的运行逻辑）。

### 3.2 储能次数测算（window_avg）

- `/api/storage/cycles`：
  - 入参：负荷（文件或 points）、储能配置、TOU 配置、日期规则。
  - 核心过程：
    - 标准化为 15 分钟负荷序列 `series_15m`。
    - 构建 `daily_ops` / `daily_masks`（C1/C2 + charge/discharge 窗口）。
    - 计算计费上限信息 `limit_info`：
      - `monthly_demand_max`（每月最大需量）
      - 或 `transformer_capacity_kva × power_factor`
    - window_avg 法计算日 cycles：
      - `base_kwh = allow_kw × hours`
      - `e_grid_kwh_*` 按 physics/sample 折算
      - `full_ratio_*` 表示单窗口内的满充/满放率
    - 聚合为：
      - `days`: `{ date, cycles }[]`
      - `months`: `{ year_month, cycles }[]`
      - `year`: `{ year, cycles }`
    - 质量与提示 `qc`：
      - `notes`、`missing_prices`、`merged_segments` 等
    - 尖段放电占比 `tip_discharge_summary`。

- 现有 `window_debug` 报表提供：
  - 每日 C1/C2、charge/discharge 的窗口明细；
  - window_avg 与 step_15min 的对拍列。

### 3.3 与本期需求的关系

- 本期收益与负荷对比功能需要在以上成果基础上：
  - **继续使用 window_avg** 作为 cycles 主口径（不改变现有结果）；  
  - **复用 step_15min 对拍能力**，在逐点上计算收益与负荷变化；  
  - 扩展响应结构与前端展示，不破坏现有接口兼容性。

---

## 4. 收益计算设计

### 4.1 总体原则

1. **不假定“满充满放”**  
   单次充放电能量基于窗口内逐点的允许功率与负荷情况计算，而不是简单使用“设计容量 × DOD”。

2. **主口径采用 step_15min**  
   收益计算以 15 分钟为时间步长，在每个时间点上使用实际允许功率和电价进行积分。

3. **收益口径与 energy_formula 联动**  
   - 当前 payload 中 `storage.energy_formula ∈ { physics, sample }`。  
   - 收益主口径跟随 `energy_formula`：
     - `energy_formula = physics`：收益按 physics 口径计算；
     - `energy_formula = sample`：收益按 sample 口径计算。
   - 同时可选输出 physics/sample 双口径作为对拍字段。

4. **缺价点处理策略**  
   - 对于 `price(t)` 缺失或无效的时间点：
     - 不计入 cost、rev、profit（视为“收益未知点”而非 0 元）；  
     - 仅累计到 `qc.missing_prices`，供质量提示使用。

### 4.2 单点功率与电量

以下逻辑用于收益计算所需的 step_15min 序列。

#### 4.2.1 电池侧允许功率

- 在现有 window_avg 逻辑基础上，为每个 15 分钟点 t 计算电池侧允许功率 `p_batt(t)`（kW）：
  - 若运行逻辑为充电（op=充）：
    - `p_batt(t) = max(limit_kw - reserve_charge_kw - load_original(t)', 0)`
  - 若运行逻辑为放电（op=放）：
    - `p_batt(t) = - max(load_original(t)' - reserve_discharge_kw, 0)`  
  - 其中：
    - `limit_kw`：来自 `limit_info`（变压器容量或 monthly_demand_max）
    - `reserve_charge_kw` / `reserve_discharge_kw`：保留功率
    - `load_original(t)'`：经 15 分钟重采样后的原始负荷
  - 注：实际实现可直接复用现有 `_step15` 中对 `allow_series` 的计算逻辑，只需明确其符号与 op 的关系。

#### 4.2.2 电网侧功率与电量

- 时间步长：`Δt = 0.25 h`。
- 根据 `energy_formula` 不同分两种情况：

1. **energy_formula = physics**

   - 充电（`p_batt(t) > 0`）：
     - 电网侧功率：`p_in_grid(t) = p_batt(t) / η`
   - 放电（`p_batt(t) < 0`）：
     - 电网侧功率：`p_out_grid(t) = -p_batt(t) × η`（注意取正值）

2. **energy_formula = sample**

   - 按 sample 口径定义折算，保持与现有 sample 能量口径对拍（具体实现沿用当前 window_debug 中 sample 折算逻辑）。

- 电网侧电量（kWh）：

  ```text
  e_in_grid(t)  = max(p_in_grid(t), 0) × Δt      # 仅充电时有值
  e_out_grid(t) = max(p_out_grid(t), 0) × Δt     # 仅放电时有值
  ```

### 4.3 单点收益

对每个 15 分钟点 t：

- 电价：`price(t)`（元/kWh），由 `build_price_series` 提供。
- 单点充电成本：`cost_t  = e_in_grid(t)  × price(t)`
- 单点放电收入：`rev_t   = e_out_grid(t) × price(t)`
- 单点净收益：`profit_t = rev_t - cost_t`

若 `price(t)` 缺失或无效，则跳过该点，不计入上述三项，只计入 `qc.missing_prices`。

### 4.4 日 / 月 / 年级别汇总指标

#### 4.4.1 日收益（对日 d）

对属于日期 d 的所有时间点 t：

- 总充电成本：`cost_day[d]   = Σ_t∈d cost_t`
- 总放电收入：`rev_day[d]    = Σ_t∈d rev_t`
- 净收益：`profit_day[d]     = rev_day[d] - cost_day[d]`
- 放电总电量：`E_out_day[d]  = Σ_t∈d e_out_grid(t)`
- 充电总电量：`E_in_day[d]   = Σ_t∈d e_in_grid(t)`
- 单位放电电量收益（若 `E_out_day > 0`）：
  - `profit_per_kwh_day[d] = profit_day[d] / E_out_day[d]`

#### 4.4.2 月收益（对月 m）

对属于该月的所有日 d：

- `cost_month[m]   = Σ_d∈m cost_day[d]`
- `rev_month[m]    = Σ_d∈m rev_day[d]`
- `profit_month[m] = rev_month[m] - cost_month[m]`
- `E_out_month[m]  = Σ_d∈m E_out_day[d]`
- `E_in_month[m]   = Σ_d∈m E_in_day[d]`
- `profit_per_kwh_month[m]` 同上按月计算。

#### 4.4.3 年收益（对年 y）

对该年内所有月 m：

- `cost_year   = Σ_m cost_month[m]`
- `rev_year    = Σ_m rev_month[m]`
- `profit_year = rev_year - cost_year`
- 同时可输出：
  - 年总放电电量 `E_out_year`
  - 年平均单位收益 `profit_per_kwh_year`

---

## 5. 负荷曲线对比设计

### 5.1 功能目标

对每个给定的储能测算方案，支持：

1. 指定自然日 d 的双曲线对比：
   - 原始负荷曲线：`load_original(t)`
   - 储能后负荷曲线：`load_with_storage(t) = load_original(t) + p_grid_effect(t)`

2. 提供关键指标前后对比：
   - 当日最大需量（kW）及变化百分比
   - 按尖/峰/平/谷分档的电量、电费及变化情况
   - 当日收益（`profit_day`）、当日 cycles（来自 window_avg）

3. 为进一步输出 Excel 报表提供数据基础。

### 5.2 数据定义

- `points_original`：
  - `[ { timestamp: string, load_kw: number } ]`
  - 15 分钟粒度，时间为本地朴素时间。

- `points_with_storage`：
  - 同样粒度与时间戳格式。
  - 负荷值：`load_with_storage(t)`。

- 指标对比（举例）：
  - `max_demand_original_kw` / `max_demand_new_kw`
  - `energy_by_tier_original` / `energy_by_tier_new`
  - `bill_by_tier_original` / `bill_by_tier_new`
  - `profit_day_main`（与收益模块对齐）

### 5.3 物理约束

- 新负荷曲线应满足：
  - 对于采用 **变压器容量** 口径时：
    - `load_with_storage(t) ≤ transformer_capacity_kva × power_factor`
  - 对于采用 **monthly_demand_max** 口径时：
    - 不强制改变最大需量约束（用于计费基准），但从直觉上应出现“削峰”效果。
- 本期不考虑 `c_rate` 对逐点储能功率的限制（保持与现有 window_avg 保守策略一致），后续可扩展。

---

## 6. 接口与数据结构变更

### 6.1 `/api/storage/cycles` 响应扩展

在现有响应结构基础上，新增收益字段，保证向后兼容。

#### 6.1.1 新数据结构示例（后端 Pydantic）

```python
class StorageProfit(BaseModel):
    revenue: float = 0.0               # 放电收入
    cost: float = 0.0                  # 充电成本
    profit: float = 0.0                # 净收益
    discharge_energy_kwh: float = 0.0  # 放电电量
    charge_energy_kwh: float = 0.0     # 充电电量
    profit_per_kwh: float = 0.0        # 单位放电电量收益（若无放电则为 0）

class StorageProfitWithFormulas(BaseModel):
    # 主口径：与请求中的 energy_formula 一致
    main: Optional[StorageProfit] = None
    # 可选：固定 physics / sample 两套对拍用字段
    physics: Optional[StorageProfit] = None
    sample: Optional[StorageProfit] = None

class StorageCyclesDay(BaseModel):
    date: str
    cycles: float
    profit: Optional[StorageProfitWithFormulas] = None  # 新增

class StorageCyclesMonth(BaseModel):
    year_month: str
    cycles: float
    profit: Optional[StorageProfitWithFormulas] = None  # 新增

class StorageCyclesYear(BaseModel):
    year: int
    cycles: float
    profit: Optional[StorageProfitWithFormulas] = None  # 新增
```

> 说明：  
> - 当前代码中的 `StorageCyclesDay/Month/Year` 仅含 `{ date/year_month/year, cycles }`，没有 `windows` 字段，本 PRD 不在这些模型上增加窗口明细，只通过新增 `profit` 承载收益数据。  
> - `window_debug` 仍承担窗口级别的核对职责。

#### 6.1.2 Response 示例（前端 TS 参考）

在 `types.ts` 中扩展：

```ts
export interface BackendStorageProfit {
  revenue: number;
  cost: number;
  profit: number;
  discharge_energy_kwh: number;
  charge_energy_kwh: number;
  profit_per_kwh: number;
}

export interface BackendStorageProfitWithFormulas {
  main?: BackendStorageProfit | null;
  physics?: BackendStorageProfit | null;
  sample?: BackendStorageProfit | null;
}

export interface BackendStorageCyclesDay {
  date: string;
  cycles: number;
  profit?: BackendStorageProfitWithFormulas | null;
}

export interface BackendStorageCyclesMonth {
  year_month: string;
  cycles: number;
  profit?: BackendStorageProfitWithFormulas | null;
}

export interface BackendStorageCyclesYear {
  year: number;
  cycles: number;
  profit?: BackendStorageProfitWithFormulas | null;
}
```

`BackendStorageCyclesResponse` 结构保持不变，仅内部 day/month/year 对象增加 `profit` 字段。

### 6.2 曲线接口：`/api/storage/cycles/curves`

#### 6.2.1 设计选择说明

为避免引入 `task_id` 与结果持久化，本版采用 **无 task_id** 方案：

- 接口为 `POST /api/storage/cycles/curves`；
- 前端在请求中携带与 `/api/storage/cycles` 相同的 `payload`（或简化版）和目标日期 `date`；
- 后端按同一逻辑重新计算指定日期的曲线与指标。  
  > 数据量相对较小，可接受重复计算。

#### 6.2.2 请求

```jsonc
POST /api/storage/cycles/curves

{
  "payload": { ... 同 /api/storage/cycles payload ... },
  "date": "YYYY-MM-DD"
}
```

- `payload`：可直接复用 `compute_storage_cycles` 的 JSON 结构（storage + strategySource + monthlyTouPrices + points/文件）。
- `date`：需要返回曲线的目标自然日。

#### 6.2.3 响应

```jsonc
{
  "date": "2025-01-01",
  "points_original": [
    { "timestamp": "2025-01-01T00:00:00", "load_kw": 123.4 },
    ...
  ],
  "points_with_storage": [
    { "timestamp": "2025-01-01T00:00:00", "load_kw": 98.7 },
    ...
  ],
  "summary": {
    "max_demand_original_kw": 456.7,
    "max_demand_new_kw": 321.0,
    "max_demand_reduction_kw": 135.7,
    "max_demand_reduction_ratio": 0.297,   // 29.7%

    "energy_by_tier_original": {
      "尖": 1000.0,
      "峰": 2000.0,
      "平": 1500.0,
      "谷": 800.0
    },
    "energy_by_tier_new": { ... },

    "bill_by_tier_original": {
      "尖": 8000.0,
      "峰": 6000.0,
      ...
    },
    "bill_by_tier_new": { ... },

    "profit_day_main": { ... 同 StorageProfit ... }
  }
}
```

> 说明：  
> - `points_*` 均为 15 分钟粒度。  
> - `summary` 字段可适当精简或扩展，以前端展示为准。  
> - 若前端只需要曲线，可先期只返回 `points_original` / `points_with_storage`，后续再补 `summary`。

---

## 7. 前端交互与展示要求

### 7.1 StorageCyclesPage 入口

- 入口仍在 StorageCycles 页面顶部导航中，不额外增加新页面。
- 增加一个“收益与负荷对比”子区块，位于现有统计模块之后。

### 7.2 展示内容（建议）

1. **汇总卡片**（日/月/年）：
   - 年度（或上传区间）：
     - 年总 cycles（现有）
     - 年总收益（profit_year_main）
     - 年总放电电量 / 单位收益
   - 当前选择月份：
     - 月 cycles
     - 月 profit / cost / revenue 等。

2. **日度收益视图**：
   - 支持选择某一日（或点击热力图/表格行）：
     - 显示当日 cycles、profit_day_main、E_out_day 等。
   - 可扩展为日度热力图（X：日期，Y：收益/单位收益）。

3. **负荷曲线对比图**：
   - X 轴：当日 0:00–24:00；
   - Y 轴：负荷（kW）；
   - 曲线 1：原负荷 `points_original`；
   - 曲线 2：储能后负荷 `points_with_storage`；
   - 可选：标注尖段时段、放电窗口。

4. **前后指标对比表**：
   - 最大需量（值 + 占比变化）
   - TOU 分档电量、电费
   - 当日收益与尖段放电占比（可与 `tip_summary` 联动）。

5. **能量公式提示**：
   - 在页面顶部或收益区域显示当前 `energy_formula`：
     - 示例：“当前能量口径：physics（可在参数中切换为 sample）”
   - 若同时输出 physics/sample 结果，可加小标签提示：
     - “sample 列仅用于核算对拍，不参与主线图表统计”。

---

## 8. 非功能性与验证要求

### 8.1 性能

- 单日曲线：最多 96 个点，两条曲线，数据量很小。
- 年度收益/次数：
  - 约 365 × 96 ≈ 3.5 万点的逐点积分，当前 Python + pandas 能力可以承受。
- 若用户上传多年的数据：
  - 建议用年度或日期范围分页处理；
  - 曲线接口按日请求，避免一次性返回过大数组。

### 8.2 一致性与可核对性

- 收益结果应可通过导出 Excel + 手算进行对拍：
  - 对应 physics / sample 两套口径；
  - 报表中保留关键中间列（如 `e_grid_kwh_*_step15`、`price`、`load_original`、`load_with_storage`）供审计。
- 回归要求：
  - 关闭收益/曲线功能时，原有 cycles 结果完全不变；
  - 即使开启收益/曲线功能，cycles 仍基于 window_avg：
    - 新增 step_15min 只用于收益与负荷对比，不改变 cycles 口径。

### 8.3 兼容性

- `/api/storage/cycles` 旧前端仍可正常解析旧字段，不依赖 `profit`。
- 新前端逻辑应对 `profit` 为 null/缺失的情况做宽容处理。

---

## 9. 未来扩展（非本期范围）

- 引入真正的 “step_15min + SOC 跨日结转” 模式，模拟 SOC 曲线：
  - 支持功率限制（c_rate × 容量）；
  - 支持 SOC 上下限约束；
  - 支持跨日 SOC 传递。
- 支持多储能配置方案对比（A/B 容量、不同策略）：
  - 同一负荷与 TOU 下对比多组收益与负荷曲线。
- 支持更多计费机制：
  - 需求电费、需量阶梯、力率考核等。

