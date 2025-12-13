# M2 阶段需求文档 (Product Requirements Document)

**版本**: v1.0  
**日期**: 2025-12-08  
**状态**: 已批准 ✅  
**删除内容**: "尖段优先"(Price-Priority) 放电策略 — 改用程序当前时序计算结果

---

## 📋 执行摘要

### 背景
用户需要对不同容量的储能系统进行**批量经济性对比**，从而找到最优的投资方案。当前系统已支持单项目的经济性分析，但缺乏**跨容量**的快速对比和**参数预设**功能。

### 核心需求
1. **分离设计**: 储能参数、批量容量对比、经济性分析三个独立 Tab
2. **快速预设**: 一键应用"保守/标准/乐观"预设方案
3. **对比篮**: 支持选中多个容量做并排对比（最多 5 个）
4. **跨 Tab 导航**: 从批量对比 → 点击行项 → 自动导航到经济性分析

### 成功指标
- 用户可在 **3 步内** 完成从批量对比到经济性分析的完整流程
- 支持**一键预设**，降低参数配置难度
- 支持**多容量对比**，提升决策效率

---

## 🎯 详细需求

### 需求 1: 三 Tab 架构（分离设计）

#### 1.1 Tab 结构

| Tab ID | 标签 | 组件 | 职责 |
|--------|------|------|------|
| `storage` | 💾 储能参数 | `StorageParamsPage` | 输入储能系统参数（C-Rate、效率、DOD 等） |
| `cycles` | 📊 批量容量对比 | `StorageCyclesPage` (简化版) | 定义容量范围 → 批量计算 cycles → 显示表格/图表 |
| `economics` | 💹 经济性分析 | `StorageEconomicsPage` (增强版) | 基于选定容量，配置经济性参数 → 计算 IRR/回收期 → 展示现金流 |

#### 1.2 数据流向

```
[用户输入] → StorageParamsPage (设置储能参数)
                    ↓
             StorageCyclesPage (批量容量配置 5000-7000, 步长 500)
                    ↓ [开始批量容量对比]
         POST /api/storage/cycles × N (并发度 3)
                    ↓
         BatchCapacityTable (显示所有容量的 cycles 结果)
                    ↓
         [用户点击某行: 📊 经济性分析]
                    ↓
         StorageEconomicsPage (容量自动填充, 显示首年收益)
                    ↓ [选择经济性参数 or 快速预设]
         POST /api/storage/economics (计算回收期/IRR)
                    ↓
         [显示指标卡片、现金流图表、返回按钮]
```

#### 1.3 Tab 切换行为

- Tab 之间**独立保存状态**，切换不清除数据
- `StorageEconomicsPage` 识别 URL 参数或导航状态，自动填充容量
- "← 返回批量对比" 按钮支持快速回到 `StorageCyclesPage`

---

### 需求 2: 快速预设方案 ⭐

#### 2.1 三套预设方案

**保守方案** (Conservative)
```json
{
  "id": "conservative",
  "label": "保守方案",
  "description": "高成本、高衰减、快回收",
  "params": {
    "capexPerWh": 1.2,              // 1.2 元/Wh
    "projectYears": 15,             // 15 年
    "omCostRatio": 0.02,            // 2% 年运维成本
    "firstYearDecayRate": 0.05,     // 5% 首年衰减
    "subsequentDecayRate": 0.03     // 3% 后续年衰减
  }
}
```

**标准方案** (Standard) — 行业典型值
```json
{
  "id": "standard",
  "label": "标准方案",
  "description": "行业典型值",
  "params": {
    "capexPerWh": 1.0,
    "projectYears": 15,
    "omCostRatio": 0.015,
    "firstYearDecayRate": 0.03,
    "subsequentDecayRate": 0.02
  }
}
```

**乐观方案** (Optimistic)
```json
{
  "id": "optimistic",
  "label": "乐观方案",
  "description": "低成本、低衰减、高收益",
  "params": {
    "capexPerWh": 0.8,
    "projectYears": 15,
    "omCostRatio": 0.01,
    "firstYearDecayRate": 0.02,
    "subsequentDecayRate": 0.015
  }
}
```

#### 2.2 UI 交互

- **位置**: 经济性参数表单顶部
- **样式**: 三个竖排按钮，每个按钮显示标签 + 简短描述
- **行为**: 点击后，自动填充对应预设参数值
- **反馈**: Toast 提示 "已应用'标准方案'"

#### 2.3 手动配置折叠区

用户可手动调整参数，支持的字段：
- 基础参数（展开状态）
  - 单位投资成本 (元/Wh)
  - 项目年限 (年)
  - 年运维成本比例 (%)
  
- 高级参数（可折叠）
  - 首年衰减率 (%)
  - 后续年衰减率 (%)
  - 电芯更换年份 (可选)
  - 电芯更换成本比例 (可选)

---

### 需求 3: 对比篮功能 ⭐

#### 3.1 对比篮概念

- **用途**: 用户可从批量对比表格选中 **2-5 个容量**，进行并排对比
- **存储**: 全局状态保存已选容量集合 `Set<number>`
- **显示**: 批量对比表格上方显示"已选 N 个"摘要区

#### 3.2 表格列扩展

| 列 | 内容 | 新增 |
|----|----|------|
| 对比 | Checkbox 多选 | ✅ |
| 容量 (kWh) | 4500, 5000, 5500, ... | 原有 |
| 循环数 (次/年) | 计算结果 | 原有 |
| 首年收益 (万元) | 计算结果 | 原有 |
| 状态 | ✅/❌/⏳ | 原有 |
| 操作 | 📊 经济性分析 按钮 | ✅ 新增 |

#### 3.3 对比篮摘要区

```html
<div class="comparison-basket-summary">
  📊 已选对比: 2 个
  5500, 6000 kWh
  [查看对比] [清空]
</div>
```

#### 3.4 对比模态框

**触发**: 点击"查看对比"按钮

**内容**:
- 标题: "容量对比 (N 个)"
- 对比表格: 已选容量的并排展示
- 列: 容量, 循环数, 收益, [可选] 回收期, IRR
- 功能: 
  - "显示/隐藏 经济性数据" 切换
  - "🔄 为全部容量计算经济性" 按钮（批量调用 /api/storage/economics）
  - 关闭按钮

**约束**:
- 最多选 5 个容量（超过 5 个时，Checkbox 禁用）
- 若某容量未计算经济性，对应单元格显示"-"

---

### 需求 4: 跨 Tab 导航

#### 4.1 导航流程

```
StorageCyclesPage (Tab: 批量容量对比)
    ↓ [点击某行的 📊 经济性分析 按钮]
    ↓
StorageEconomicsPage (Tab: 经济性分析 自动激活)
    ↓ [页面自动填充容量信息]
    ↓ [用户调整经济性参数，点击 🔄 计算经济性]
    ↓
[显示 IRR、回收期、现金流图表]
    ↓ [点击 ← 返回批量对比 按钮]
    ↓
StorageCyclesPage (恢复到之前的批量结果)
```

#### 4.2 状态传递

- **方式**: React `useLocation().state` 或 URL query params
- **传递数据**:
  ```typescript
  {
    capacityKwh: 5500,
    firstYearProfit: 825000,          // 从 cycles 结果获取
    yearEqCycles: 245
  }
  ```
- **自动填充**: `StorageEconomicsPage` 识别导航参数，自动显示容量卡片

#### 4.3 返回机制

- "← 返回批量对比" 按钮：`setActiveTab('cycles')`
- 批量对比结果保留在全局状态，用户返回时仍可见

---

### 需求 5: 全局状态结构

#### 5.1 React State 设计

```typescript
interface StorageAnalysisState {
  // M1: 批量容量对比
  batchResults: BatchCapacityItem[];           // 所有容量结果
  storageParams: StorageParamsTemplate;        // 储能参数快照
  
  // M2: 经济性分析
  selectedCapacityForEconomics?: {
    capacityKwh: number;
    firstYearProfit: number;
    yearEqCycles: number;
  };
  economicsParams: EconomicsParams;            // 用户配置的经济性参数
  economicsResults: Map<number, StorageEconomicsResult>;  // 容量 → 经济性结果缓存
  
  // M3: 对比篮
  comparisonBasket: Set<number>;               // 已选容量集合
}
```

#### 5.2 全局 Hook

```typescript
export const useStorageAnalysis = () => {
  // 返回状态 + 更新方法
  return {
    state,
    selectCapacityForEconomics(item),     // 导航到经济性分析
    updateEconomicsParams(params),        // 更新参数
    saveEconomicsResult(capacity, result), // 缓存经济性结果
    toggleComparison(capacity),           // 切换对比篮
    clearBasket(),                        // 清空对比篮
  };
};
```

---

### 需求 6: API 集成

#### 6.1 现有 API（无需修改）

**POST /api/storage/cycles**
- 输入: 容量 + 储能参数 + 负荷数据
- 输出: 循环数、首年收益、月度利润等
- 用途: 批量容量对比的数据源

**POST /api/storage/economics**
- 输入: 容量 + 首年收益 + 经济性参数（项目年限、衰减率、运维成本等）
- 输出: 静态回收期、IRR、NPV、年度现金流
- 用途: 经济性分析的数据源

#### 6.2 前端调用方式

```typescript
// 1. 批量计算 cycles（并发度 3）
const computeStorageCycles = async (capacityKwh: number) => {
  const response = await fetch('/api/storage/cycles', {
    method: 'POST',
    body: formData // 包含文件和参数
  });
  return response.json();
};

// 2. 单个容量计算经济性
const computeStorageEconomics = async (input: {
  capacity_kwh: number;
  first_year_revenue: number;    // 从 cycles 获取
  project_years: number;
  capex_per_wh: number;
  om_cost_ratio: number;
  first_year_decay_rate: number;
  subsequent_decay_rate: number;
}) => {
  const response = await fetch('/api/storage/economics', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input)
  });
  return response.json();
};
```

---

## 🎨 UI/UX 规范

### 样式指南

- **色系**: 
  - 主色: 蓝色 (`#3b82f6`)
  - 成功: 绿色 (`#10b981`)
  - 警告: 黄色 (`#f59e0b`)
  - 错误: 红色 (`#ef4444`)

- **间距**: 
  - 卡片间距: 20px
  - 表单项: 12px 行高

- **排版**:
  - 标题: PingFang SC, 16px, 600 weight
  - 正文: PingFang SC, 14px, 400 weight

### 响应式设计

- 桌面: 1920px 宽度
- 表格可水平滚动（移动端）
- 模态框宽度: 1000px（desktop）/ 90vw（mobile）

---

## ✅ 验收标准

### 功能验收

| 项目 | 标准 | 验收方式 |
|------|------|---------|
| 分离设计 | 三个独立 Tab 可正常切换，状态保留 | 手工测试 |
| 快速预设 | 点击预设按钮，参数立即更新 | 手工测试 + 数据验证 |
| 对比篮 | 支持选中 2-5 个容量，显示摘要 | 手工测试 |
| 跨 Tab 导航 | 批量对比 → 点击行 → 经济性分析自动激活 | 手工测试 |
| 现金流图表 | 显示年度现金流、回收期标记线 | 截图对比 |

### 性能验收

| 指标 | 目标 | 验收方式 |
|------|------|---------|
| 批量计算(10容量) | < 15 秒 | 计时测试 |
| 经济性计算(1容量) | < 2 秒 | 计时测试 |
| UI 响应 | 无卡顿，Checkbox 切换即时 | 肉眼观察 |

### 兼容性

- 浏览器: Chrome 90+, Edge 90+, Safari 14+
- 分辨率: 1024px+ (支持平板)

---

## 📚 附录

### A. 经济性计算公式

#### A.1 静态回收期
```
静态回收期 = 初始投资 / 年均净现金流
           = (Capacity × capexPerWh) / (年均收益 - 年均运维成本)
```

#### A.2 IRR (内部收益率)
```
NPV = Σ(CF_t / (1 + IRR)^t) - InitialInvestment = 0
```

#### A.3 衰减模型
```
Year 1: Revenue = firstYearProfit
Year 2+: Revenue = prevYearRevenue × (1 - subsequentDecayRate)
```

### B. 测试数据

**样例**: 5500 kWh 储能系统
- 循环数: 245 次/年
- 首年收益: 825,000 元
- 投资成本（标准预设）: 5500 × 1.0 = 550 万元
- 预期回收期: ~6.7 年
- 预期 IRR: 15.2%

### C. 相关文档

- [批量容量经济性对比功能需求.md](../docs/批量容量经济性对比功能需求.md) — 原始需求文档（已更新）
- [开发计划.md](./02_开发计划.md) — 详细的实现路线图
- [架构设计.md](./03_架构设计.md) — 技术架构和数据流
- [测试计划.md](./04_测试计划.md) — 验收测试用例

---

**审批记录**:
- ✅ 2025-12-08: 批准，删除"尖段优先"策略，基于时序计算
