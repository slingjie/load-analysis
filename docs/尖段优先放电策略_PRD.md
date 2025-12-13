# 尖段优先放电策略 - 产品需求文档（PRD）

## 文档信息

| 项目 | 内容 |
|------|------|
| **文档版本** | v1.0 |
| **创建日期** | 2025-12-06 |
| **负责人** | 待定 |
| **状态** | 待审核 |
| **优先级** | P1（高优先级） |

---

## 1. 需求背景

### 1.1 业务问题

在当前储能收益计算中，当放电时段同时包含**峰电价**和**尖电价**时，系统采用**时序放电策略**：

- **现状**：按时间顺序线性放电，每个 15 分钟点独立计算收益
- **问题**：未充分利用高价时段（尖段），导致收益未达最优

**示例场景**：
```
某日放电窗口 18:00-21:00（电池可放 2000 kWh）
├─ 18:00-19:00 (峰段, 1.03元/kWh)  → 当前：放电 500 kWh，收益 515 元
├─ 19:00-21:00 (尖段, 1.45元/kWh)  → 当前：放电 1500 kWh，收益 2175 元
└─ 总收益：2690 元

优化后（尖段优先）：
├─ 18:00-19:00 (峰段, 1.03元/kWh)  → 优化：放电 0 kWh，收益 0 元
├─ 19:00-21:00 (尖段, 1.45元/kWh)  → 优化：放电 2000 kWh，收益 2900 元
└─ 总收益：2900 元（提升 7.8%）
```

### 1.2 业务价值

- **直接收益提升**：同等储能容量下，年收益预计提升 **5-15%**（取决于峰尖价差）
- **投资决策优化**：更准确的收益预测，提高项目可行性评估精度
- **竞争力增强**：为客户提供更优的储能调度策略建议

---

## 2. 需求概述

### 2.1 功能定义

新增**尖段优先放电策略**（Price-Priority Discharge Strategy），在储能收益计算中：

1. **保持充放电时段判定逻辑不变**（由 TOU 配置的"充/放/待机"决定）
2. **在放电窗口内**，按电价从高到低排序 15 分钟点
3. **优先向高价时段分配电池可放电量**，直到电量耗尽或达到约束上限

### 2.2 用户故事

**作为** 储能项目评估人员  
**我希望** 系统能够按尖段优先策略计算收益  
**以便** 获得更贴近实际运营场景的收益预测

### 2.3 成功标准

- ✅ 用户可在 UI 中选择"时序放电"或"尖段优先"两种策略
- ✅ 尖段优先策略下，同一日放电窗口内，高价时段的放电量 ≥ 低价时段
- ✅ 收益计算结果符合手工验算（误差 < 0.1%）
- ✅ 充放电次数计算逻辑保持不变（按时段窗口统计，不受能量分配影响）
- ✅ 向后兼容：默认策略为"时序放电"，已有配置和结果不受影响

---

## 3. 详细功能设计

### 3.1 策略对比

| 维度 | 时序放电（Sequential） | 尖段优先（Price-Priority） |
|------|----------------------|---------------------------|
| **分配逻辑** | 按时间顺序，逐点线性放电 | 按电价排序，优先填充高价点 |
| **适用场景** | 保守测算、政策约束场景 | 最大化收益、灵活调度场景 |
| **计算复杂度** | O(n) | O(n log n)（需排序） |
| **兼容性** | 完全兼容现有逻辑 | 新增模式，可切换 |

### 3.2 算法流程

```
输入：
  - 15 分钟负荷序列（含 TOU 档位、电价、运行逻辑）
  - 储能配置（容量、C-Rate、效率、DoD）
  - 放电策略选择（sequential / price-priority）

处理（按日期分组）：
  FOR EACH 日期 d:
    1. 筛选当日放电时段点集合 D = {t | op(t) == '放'}
    2. IF 策略 == 'price-priority':
         a. 按 price(t) 降序排列 D
         b. 计算当日可放总电量 E_max（基于充电窗口的满充率）
         c. 从最高价点开始，依次分配 min(点功率上限, 剩余电量)
       ELSE:
         a. 保持时序，按时间顺序分配
    3. 计算收益：revenue = Σ (e_out(t) × price(t))

输出：
  - profit_days[]：每日收益明细（包含分配后的 discharge_energy_kwh）
  - profit_summary：总收益、总次数、平均度电收益
```

### 3.3 约束条件

#### 3.3.1 变压器容量约束
每个 15 分钟点的放电功率不能超过变压器限制：
```python
max_discharge_power(t) = min(
    limit_kw(t),                    # 变压器额定容量
    battery_capacity * c_rate       # 电池最大放电倍率
)
```

#### 3.3.2 当日充电量约束
当日放电总量不能超过当日充入电量（考虑效率）：
```python
max_discharge_energy(d) = charged_energy(d) × dod × efficiency
```

#### 3.3.3 电池 SOC 约束
```python
soc_min ≤ SOC(t) ≤ soc_max
# 其中 SOC(t) = SOC(t-1) + (charge_energy(t) - discharge_energy(t)) / battery_capacity
```

#### 3.3.4 时段完整性约束
- 仅在**同一日期**内的放电窗口进行优化
- 跨日充放电场景：分别在各自日期内优化（不跨日聚合）

---

## 4. 界面设计

### 4.1 储能次数计算页面（StorageCyclesPage.tsx）

**新增控件**：策略选择器

```
┌─────────────────────────────────────────────┐
│ 储能参数配置                                 │
├─────────────────────────────────────────────┤
│ 电池容量：[2000] kWh                         │
│ 充放电倍率：[0.5] C                          │
│ 单边效率：[92.2] %                           │
│ 放电深度：[90] %                             │
│                                             │
│ ┌───────────────────────────────────────┐   │
│ │ 放电策略：                              │   │
│ │  ○ 时序放电（默认）                      │   │
│ │  ● 尖段优先                             │   │
│ │                                         │   │
│ │ ℹ️ 尖段优先：在放电窗口内，优先向最高价  │   │
│ │   格时段分配电量，以最大化收益           │   │
│ └───────────────────────────────────────┘   │
│                                             │
│ [开始计算]                                   │
└─────────────────────────────────────────────┘
```

### 4.2 收益对比页面（StorageProfitPage.tsx）

**新增显示**：策略标识

```
计算配置快照
├─ 电池容量：2000 kWh
├─ 计量模式：月最大需量
├─ 能量公式：physics
└─ 放电策略：尖段优先 ✨  ← 新增

年度收益汇总
├─ 总收益：125,800 元 (+8.2% vs 时序放电)  ← 对比提示
├─ 总成本：32,400 元
└─ 净利润：93,400 元
```

---

## 5. 技术实现

### 5.1 后端改动

#### 5.1.1 新增函数（`backend/services/cycles.py`）

```python
def _allocate_discharge_by_price(
    discharge_points: pd.DataFrame,
    max_discharge_energy: float,
    storage_cfg: dict,
    price_series: pd.Series
) -> pd.DataFrame:
    """
    按价格优先分配放电能量。
    
    参数：
        discharge_points: 放电时段点集合（已过滤 op=='放'）
        max_discharge_energy: 当日最大可放电量（kWh）
        storage_cfg: 储能配置
        price_series: 时间 -> 电价映射
    
    返回：
        分配后的 DataFrame，含 'e_out_allocated' 列
    """
    df = discharge_points.copy()
    df['price'] = df.index.map(price_series)
    df = df.sort_values('price', ascending=False)
    
    remaining = max_discharge_energy
    df['e_out_allocated'] = 0.0
    
    for idx, row in df.iterrows():
        if remaining <= 0:
            break
        
        max_power = min(
            row['limit_kw'],
            storage_cfg['battery_capacity_kwh'] * storage_cfg['c_rate']
        )
        
        allocated = min(max_power * 0.25, remaining)
        df.at[idx, 'e_out_allocated'] = allocated
        remaining -= allocated
    
    return df
```

#### 5.1.2 修改主函数（`compute_profit_summary_step15`）

```python
def compute_profit_summary_step15(
    series_15m: pd.DataFrame,
    daily_ops: pd.DataFrame,
    storage_cfg: dict,
    price_series: pd.Series,
    discharge_strategy: str = 'sequential',  # 新增参数
    ...
):
    # ...existing code...
    
    for date_str, day_df in series_15m.groupby('date_str'):
        discharge_mask = day_df['op'] == '放'
        
        if discharge_strategy == 'price-priority' and discharge_mask.any():
            # 新逻辑：按价格分配
            charged_energy = _compute_charged_energy(day_df[day_df['op'] == '充'])
            max_discharge = charged_energy * dod * efficiency
            
            discharge_df = _allocate_discharge_by_price(
                day_df[discharge_mask],
                max_discharge,
                storage_cfg,
                price_series
            )
            
            day_df.loc[discharge_mask, 'e_out_main_kwh'] = discharge_df['e_out_allocated']
        else:
            # 原逻辑：时序分配
            # ...existing code...
        
        # ...revenue calculation...
```

#### 5.1.3 Schema 更新（`backend/schemas.py`）

```python
class StorageWindowsRequest(BaseModel):
    # ...existing fields...
    discharge_strategy: Literal['sequential', 'price-priority'] = Field(
        default='sequential',
        description="放电能量分配策略：sequential=时序放电, price-priority=尖段优先"
    )
```

### 5.2 前端改动

#### 5.2.1 类型定义（`types.ts`）

```typescript
export type DischargeStrategy = 'sequential' | 'price-priority';

export interface StorageCalculationConfig {
  // ...existing fields...
  discharge_strategy: DischargeStrategy;
}
```

#### 5.2.2 UI 组件（`StorageCyclesPage.tsx`）

```typescript
const [dischargeStrategy, setDischargeStrategy] = useState<DischargeStrategy>('sequential');

// 在参数配置区域添加：
<div className="mb-4">
  <label className="block text-sm font-medium mb-2">
    放电策略
  </label>
  <div className="space-y-2">
    <label className="flex items-center">
      <input
        type="radio"
        value="sequential"
        checked={dischargeStrategy === 'sequential'}
        onChange={(e) => setDischargeStrategy(e.target.value as DischargeStrategy)}
        className="mr-2"
      />
      <span>时序放电（默认）</span>
    </label>
    <label className="flex items-center">
      <input
        type="radio"
        value="price-priority"
        checked={dischargeStrategy === 'price-priority'}
        onChange={(e) => setDischargeStrategy(e.target.value as DischargeStrategy)}
        className="mr-2"
      />
      <span>尖段优先</span>
    </label>
  </div>
  <p className="text-xs text-gray-500 mt-1">
    尖段优先：在放电窗口内，优先向最高价格时段分配电量，以最大化收益
  </p>
</div>
```

---

## 6. 测试验证

### 6.1 单元测试用例

#### 用例 1：基础尖段优先分配

```python
def test_price_priority_basic():
    """验证尖段优先基本逻辑"""
    # 构造数据：3个放电点，电价分别为 0.6, 1.0, 1.5
    df = pd.DataFrame([
        {'time': '06:00', 'op': '放', 'limit_kw': 500, 'price': 0.6},  # 平
        {'time': '08:00', 'op': '放', 'limit_kw': 500, 'price': 1.0},  # 峰
        {'time': '10:00', 'op': '放', 'limit_kw': 500, 'price': 1.5},  # 尖
    ])
    
    result = compute_profit_summary_step15(
        df, 
        storage_cfg={'battery_capacity_kwh': 2000, 'c_rate': 0.5},
        discharge_strategy='price-priority',
        max_discharge_energy=300  # 只能放 300 kWh
    )
    
    # 断言：10:00（尖段）应优先放满
    assert result.loc['10:00', 'e_out_kwh'] == 125  # 500kW × 0.25h
    # 08:00（峰段）放部分
    assert result.loc['08:00', 'e_out_kwh'] == 125
    # 06:00（平段）放剩余
    assert result.loc['06:00', 'e_out_kwh'] == 50
```

#### 用例 2：变压器容量约束

```python
def test_transformer_limit():
    """验证变压器容量约束生效"""
    df = pd.DataFrame([
        {'time': '10:00', 'op': '放', 'limit_kw': 300, 'price': 1.5},  # 受限
    ])
    
    result = compute_profit_summary_step15(
        df,
        storage_cfg={'battery_capacity_kwh': 2000, 'c_rate': 1.0},  # 电池支持 2000kW
        discharge_strategy='price-priority',
        max_discharge_energy=500
    )
    
    # 断言：实际放电不超过变压器容量
    assert result.loc['10:00', 'e_out_kwh'] == 75  # 300kW × 0.25h
```

### 6.2 回归测试

**测试文件**：`负荷测试数据/中恒新材料负荷数据 展示用.csv`

**测试步骤**：
1. 配置 TOU 调度（1 月：00-06 充电，19-21 放电，其中 19-20 为峰，20-21 为尖）
2. 分别使用两种策略计算全年收益：
   - 策略A（sequential）：预期年收益 ≈ 116,000 元
   - 策略B（price-priority）：预期年收益 ≈ 125,000 元（提升 7.8%）
3. 验证充放电次数一致（约 350 次/年）

### 6.3 边界场景

| 场景 | 预期行为 |
|------|---------|
| 所有放电点电价相同 | 两种策略结果一致 |
| 放电窗口只有 1 个点 | 两种策略结果一致 |
| 当日无充电（max_discharge=0） | 所有放电点能量为 0 |
| 跨日放电 | 按各自日期独立优化 |
| 电池容量小于单点需求 | 受 C-Rate 约束，不会过载 |

---

## 7. 上线计划

### 7.1 里程碑

| 阶段 | 任务 | 工期 | 交付物 |
|------|------|------|--------|
| **Phase 1: 后端开发** | 实现 `_allocate_discharge_by_price()` 函数 | 1 天 | 可运行的 Python 函数 |
| | 修改 `compute_profit_summary_step15()` | 1 天 | 完整的策略切换逻辑 |
| | 更新 Schema + API 接口 | 0.5 天 | Swagger 文档更新 |
| **Phase 2: 前端开发** | 添加策略选择器 UI | 0.5 天 | StorageCyclesPage 更新 |
| | 更新类型定义 | 0.5 天 | types.ts 更新 |
| | 结果展示增强 | 0.5 天 | 策略标识显示 |
| **Phase 3: 测试验证** | 单元测试编写 | 1 天 | 5+ 测试用例 |
| | 回归测试执行 | 0.5 天 | 测试报告 |
| | 文档更新 | 0.5 天 | 测试指引更新 |
| **Phase 4: 上线部署** | UAT 测试 | 1 天 | 验收报告 |
| | 生产部署 | 0.5 天 | 版本发布 |

**总工期**：约 **7-8 个工作日**

### 7.2 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 策略切换导致历史数据不一致 | 高 | 低 | 默认保持 sequential，明确标注策略 |
| 变压器约束处理不当 | 中 | 中 | 充分测试边界场景 |
| 性能下降（排序开销） | 低 | 低 | 仅对放电点排序，影响可控 |
| 用户误解策略含义 | 中 | 中 | UI 提供清晰说明 + 帮助文档 |

---

## 8. 待确认事项

### 🔴 高优先级

1. **策略默认值**
❓ 问题：新配置默认使用哪种策略？
   选项 A：sequential（保守测算，向后兼容）
   选项 B：price-priority（最大化收益）
   
   选择 A，避免影响历史数据对比

2. **跨日充放电处理**
❓ 问题：如果周一充电，周二才放电，如何分配？
   选项 A：严格按日分组，周二只能放周二的充电量
   选项 B：允许跨日累积，使用"电池 SOC 连续追踪"
   
   选择 A（简化实现），Phase 2 再考虑 B

3. **历史数据兼容性**
   ❓ 问题：已有的计算结果需要追加策略标识吗？
   选项 A：仅新计算显示策略，历史数据不回填
   选项 B：给历史数据默认标注为 'sequential'
   
   选择 A，避免数据污染，在 `lastStorageRun` 中新增 `discharge_strategy` 字段

### 🟡 中优先级

4. **UI 交互优化**
   - ❓ 是否需要"对比模式"（同时显示两种策略的收益）？
   - 暂不需要，Phase 2 功能，当前先支持单一策略选择

5. **Excel 导出**
   - ❓ 导出的 Excel 报表是否需要显示策略信息？
   - 在"配置参数"工作表中新增一行"放电策略"

6. **性能优化**
❓ 问题：如果排序导致性能下降 > 20%，是否需要缓存？
   
   优化方案：
   - 缓存当日的价格排序结果
   - 使用 numpy 加速排序
   
   先实现功能，观察性能，按需优化

### 🟢 低优先级

7. **多策略对比分析**
   - ❓ 未来是否支持更多策略（如"谷充优先"、"峰谷套利"）？
   - 预留扩展接口，当前聚焦尖段优先

8. **AI 推荐策略**
   - ❓ 是否需要系统根据电价结构自动推荐最优策略？
   - 建议：Phase 3 功能

---

## 9. 参考资料

- [储能收益与负荷对比功能 PRD](./储能收益与负荷对比功能 PRD.md)
- [储能收益与负荷对比功能_测试指引](./储能收益与负荷对比功能_测试指引.md)
- [充放电率计算沟通](./充放电率计算沟通.md)
- [AGENTS.md](../AGENTS.md) - Change Proposal 流程

---

## 10. 审批签字

| 角色 | 姓名 | 日期 | 签名 |
|------|------|------|------|
| 产品经理 | 待定 | - | - |
| 技术负责人 | 待定 | - | - |
| 测试负责人 | 待定 | - | - |

---

**文档版本历史**

| 版本 | 日期 | 修改人 | 修改内容 |
|------|------|--------|---------|
| v1.0 | 2025-12-06 | AI Assistant | 初始版本 |
