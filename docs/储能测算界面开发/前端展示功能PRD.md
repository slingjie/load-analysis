# 储能次数测算前端展示功能 PRD

**版本：** v1.0  
**创建日期：** 2025-11-10  
**目标页面：** Storage Cycles Page  
**相关文件：** `components/StorageCyclesPage.tsx`

---

## 📋 一、需求概述

### 1.1 背景
当前 Storage Cycles 页面仅提供基础的柱状图和折线图展示，无法直观呈现储能充放电次数的时空分布规律。需要优化可视化方案，提升用户对储能运行状态的分析效率。

### 1.2 目标
1. **日度次数可视化**：采用日历热力图，直观展示全年每日充放电次数分布
2. **月度次数可视化**：将柱状图改为折线图，突出趋势变化
3. **增强交互体验**：提供联动下钻、数据导出、异常标注等功能
4. **提升决策支持**：增加 KPI 概览、策略对比、日内详情等分析维度

---

## 📊 二、核心功能设计

### 2.1 日度次数 - 日历热力图 (Calendar Heatmap)

#### **功能描述**
- 使用 ECharts Calendar 组件，按年度展示 365 天的充放电次数
- 每个日期格子颜色深浅代表循环次数强度（0 → 高频）

#### **数据源**
```typescript
// 后端返回结构（已实现）
interface BackendStorageCyclesDay {
  date: string;    // 'YYYY-MM-DD'
  cycles: number;  // 1.85
}
```

#### **视觉规范**
- **颜色渐变**：`['#eff6ff', '#3b82f6', '#1e40af']`（浅蓝 → 深蓝）
- **网格尺寸**：自适应容器宽度，建议高度 240px
- **工具提示**：
  ```
  2024-03-15
  循环次数：1.85
  策略：峰谷套利
  ```

#### **交互功能**
- 鼠标悬停显示详情
- 点击日期触发日内详情面板展开
- 支持按年份切换（多年数据场景）

#### **技术实现**
```typescript
const calendarOption = {
  tooltip: { position: 'top' },
  visualMap: {
    min: 0,
    max: 3,
    calculable: true,
    orient: 'horizontal',
    left: 'center',
    top: 'top',
    inRange: {
      color: ['#eff6ff', '#3b82f6', '#1e40af']
    }
  },
  calendar: {
    range: selectedYear,
    cellSize: ['auto', 16],
    splitLine: { show: true, lineStyle: { color: '#e2e8f0' } },
    itemStyle: { borderWidth: 1, borderColor: '#fff' },
    yearLabel: { show: true },
    dayLabel: { nameMap: 'cn' },
    monthLabel: { nameMap: 'cn' }
  },
  series: [{
    type: 'heatmap',
    coordinateSystem: 'calendar',
    data: daysData.map(d => [d.date, d.cycles])
  }]
};
```

---

### 2.2 月度次数 - 折线图 (Line Chart)

#### **功能描述**
- 替换现有柱状图为折线图，适合展示时间序列趋势
- 添加面积填充和平均线标注

#### **数据源**
```typescript
interface BackendStorageCyclesMonth {
  year_month: string; // '2024-03'
  cycles: number;     // 12.45
}
```

#### **视觉规范**
- **主色调**：`#3b82f6`（蓝色）
- **面积填充**：`rgba(59, 130, 246, 0.1)`（10% 透明度）
- **平均线**：虚线样式，标注数值
- **峰值标注**：最高/最低月份红色标记

#### **增强功能**
```typescript
series: [{
  name: '月循环次数',
  type: 'line',
  smooth: true,
  data: monthsData.map(m => m.cycles),
  itemStyle: { color: '#3b82f6' },
  areaStyle: { 
    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
      { offset: 0, color: 'rgba(59, 130, 246, 0.3)' },
      { offset: 1, color: 'rgba(59, 130, 246, 0.05)' }
    ])
  },
  markLine: {
    silent: true,
    data: [{ type: 'average', name: '平均值' }],
    lineStyle: { type: 'dashed', color: '#64748b' },
    label: { formatter: '{c} 次/月' }
  },
  markPoint: {
    data: [
      { type: 'max', name: '最高', itemStyle: { color: '#ef4444' } },
      { type: 'min', name: '最低', itemStyle: { color: '#10b981' } }
    ]
  }
}]
```

#### **交互功能**
- 点击月份下钻到日历热力图对应月份
- 支持区域缩放（dataZoom）
- 导出当前视图为图片

---

### 2.3 KPI 概览卡片 (Dashboard Cards)

#### **功能描述**
在页面顶部展示 4 个关键指标卡片

#### **指标定义**
```typescript
interface KPIMetrics {
  totalCycles: number;      // 年累计次数
  avgCycles: number;        // 月均次数 = totalCycles / 12
  maxMonth: {               // 最高月
    yearMonth: string;
    cycles: number;
  };
  minMonth: {               // 最低月
    yearMonth: string;
    cycles: number;
  };
}
```

#### **视觉设计**
```tsx
<div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
  <KPICard 
    title="年累计次数" 
    value={result.year.cycles.toFixed(2)} 
    icon="🔄"
    color="blue"
  />
  <KPICard 
    title="月均次数" 
    value={(result.year.cycles / 12).toFixed(2)} 
    icon="📊"
    color="green"
  />
  <KPICard 
    title="最高月次数" 
    value={maxMonth.cycles.toFixed(2)} 
    subtitle={maxMonth.year_month}
    icon="📈"
    color="red"
  />
  <KPICard 
    title="最低月次数" 
    value={minMonth.cycles.toFixed(2)} 
    subtitle={minMonth.year_month}
    icon="📉"
    color="gray"
  />
</div>
```

---

### 2.4 日内充放电详情面板 (Daily Detail Panel)

#### **功能描述**
用户点击热力图某一天后，展开该日的详细分析面板

#### **展示内容**
1. **24 小时甘特图**：
   - 蓝色块：充电时段
   - 橙色块：放电时段
   - 灰色块：待机时段
   
2. **SOC 曲线**：
   - Y 轴：SOC% (0-100)
   - X 轴：24 小时时间轴
   
3. **功率对比曲线**：
   - 原始负荷（灰线）
   - 储能调整后负荷（蓝线）

#### **数据需求**
需要后端新增接口返回单日详情：
```typescript
interface DayDetailRequest {
  date: string; // 'YYYY-MM-DD'
}

interface DayDetailResponse {
  date: string;
  cycles: number;
  segments: {
    startTime: string;  // 'HH:mm'
    endTime: string;
    action: '充' | '放' | '待机';
    power_kw: number;
  }[];
  soc_curve: {
    timestamp: string;
    soc_percent: number;
  }[];
  load_comparison: {
    timestamp: string;
    original_load_kw: number;
    adjusted_load_kw: number;
  }[];
}
```

---

### 2.5 数据导出功能

#### **功能列表**
1. **Excel 导出**（当前已实现）：完整的年/月/日数据表
2. **图表导出**：PNG/SVG 格式
3. **参数配置快照**：JSON 文件保存当前储能配置

#### **实现方式**
```typescript
// 利用 ECharts toolbox
toolbox: {
  feature: {
    saveAsImage: {
      title: '保存为图片',
      pixelRatio: 2
    },
    dataView: {
      title: '数据视图',
      readOnly: true
    }
  }
}
```

---

### 2.6 异常检测标注

#### **功能描述**
基于后端返回的 `qc.notes` 数据，在图表上标注异常日期

#### **异常类型**
- 需量超标日
- 缺失电价日
- 缺失负荷点日

#### **视觉表现**
```typescript
markPoint: {
  data: anomalyDays.map(d => ({
    name: d.type, // '需量超标'
    coord: [d.date, d.cycles],
    value: d.cycles,
    itemStyle: { 
      color: '#ef4444',
      borderColor: '#dc2626',
      borderWidth: 2
    },
    label: {
      formatter: '{b}\n{c} 次',
      position: 'top'
    }
  }))
}
```

---

## 🎯 三、开发优先级

### Phase 1：核心图表（Week 1）
- [x] 月度折线图替换柱状图
- [ ] 日历热力图实现
- [ ] KPI 概览卡片
- [ ] 基础交互（悬停、点击）

### Phase 2：增强分析（Week 2）
- [ ] 日内详情面板（需后端接口）
- [ ] 图表联动（月→日下钻）
- [ ] 数据导出（图表 PNG）
- [ ] 异常标注

### Phase 3：高级功能（Week 3）
- [ ] 多配置对比视图
- [ ] 年度对比（年份切换）
- [ ] 自定义时间范围筛选
- [ ] 移动端适配

---

## 🎨 四、设计规范

### 4.1 色彩方案
```typescript
const COLORS = {
  primary: '#3b82f6',      // 主色（蓝色）
  charge: '#3b82f6',       // 充电
  discharge: '#f97316',    // 放电
  standby: '#94a3b8',      // 待机
  success: '#10b981',      // 成功/最低
  danger: '#ef4444',       // 危险/最高
  warning: '#f59e0b',      // 警告
  gray: '#64748b',         // 辅助文字
  heatmap: ['#eff6ff', '#3b82f6', '#1e40af']
};
```

### 4.2 布局结构
```
┌─────────────────────────────────────────────────┐
│ 参数配置区域（现有）                                │
├─────────────────────────────────────────────────┤
│ KPI 概览卡片（4 列网格）                           │
├─────────────────────────────────────────────────┤
│ 月度趋势折线图（高度 320px）                       │
├─────────────────────────────────────────────────┤
│ 日度热力图（高度 240px）+ 年份选择器               │
├─────────────────────────────────────────────────┤
│ [可选] 日内详情面板（点击后展开）                  │
│  - 甘特图 + SOC 曲线 + 功率对比                    │
└─────────────────────────────────────────────────┘
```

### 4.3 响应式断点
- **Desktop**：≥ 1024px（4 列 KPI）
- **Tablet**：768-1023px（2 列 KPI）
- **Mobile**：< 768px（1 列 KPI，图表高度缩减）

---

## 🔧 五、技术实现细节

### 5.1 组件拆分
```typescript
// 现有组件
components/StorageCyclesPage.tsx

// 新增子组件（建议）
components/storage/
  ├── StorageKPICards.tsx          // KPI 概览
  ├── StorageMonthlyLineChart.tsx  // 月度折线图
  ├── StorageDailyHeatmap.tsx      // 日历热力图
  ├── StorageDailyDetail.tsx       // 日内详情面板
  └── StorageChartExporter.tsx     // 导出工具
```

### 5.2 状态管理
```typescript
interface StorageCyclesState {
  result: BackendStorageCyclesResponse | null;
  selectedYear: string;           // 热力图年份
  selectedMonth: string | null;   // 月度图选中月
  selectedDay: string | null;     // 日度图选中日
  dayDetail: DayDetailResponse | null;
  loading: boolean;
  error: string | null;
}
```

### 5.3 性能优化
- **大数据场景**：365 天数据使用虚拟滚动
- **图表懒加载**：日内详情面板按需加载
- **防抖处理**：年份切换时添加 300ms 防抖
- **缓存策略**：已查询的日内详情缓存到 Map

---

## 📝 六、后端接口需求

### 6.1 现有接口（已实现）
```
POST /api/storage/cycles
Request: { file, payload }
Response: {
  year: { cycles },
  months: [{ year_month, cycles }],
  days: [{ date, cycles }],
  qc: { notes, ... },
  excel_path
}
```

### 6.2 新增接口需求
```typescript
// 获取单日详情
GET /api/storage/cycles/day-detail?date=2024-03-15
Response: {
  date: '2024-03-15',
  cycles: 1.85,
  segments: [...],
  soc_curve: [...],
  load_comparison: [...]
}
```

---

## ✅ 七、验收标准

### 功能验收
- [ ] 日历热力图正确展示 365 天数据
- [ ] 月度折线图显示趋势，包含平均线和峰值标注
- [ ] KPI 卡片数据准确（年/月均/最高/最低）
- [ ] 点击热力图日期能展开详情面板
- [ ] 图表支持导出 PNG
- [ ] 异常日期有红色标注

### 性能验收
- [ ] 图表渲染时间 < 1s（1000 条数据）
- [ ] 交互响应时间 < 200ms
- [ ] 内存占用 < 100MB

### 兼容性验收
- [ ] Chrome/Edge 最新版
- [ ] Safari 15+
- [ ] Firefox 最新版
- [ ] 响应式适配 375px - 1920px

---

## 📚 八、参考资料

### 8.1 ECharts 官方示例
- [Calendar Heatmap](https://echarts.apache.org/examples/zh/editor.html?c=calendar-heatmap)
- [Line Chart with MarkLine](https://echarts.apache.org/examples/zh/editor.html?c=line-markline)
- [Gantt Chart](https://echarts.apache.org/examples/zh/editor.html?c=custom-gantt-flight)

### 8.2 项目内参考
- `components/EChartTimeSeries.tsx` - 时间轴折线图
- `components/MonthlyAverageStackedChart.tsx` - 堆叠柱状图
- `components/LoadAnalysisPage.tsx` - KPI 卡片布局

---

## 📞 九、联系方式

**产品负责人**：[待填写]  
**开发负责人**：[待填写]  
**测试负责人**：[待填写]

---

**文档更新记录**
| 版本 | 日期 | 修改人 | 修改内容 |
|------|------|--------|----------|
| v1.0 | 2025-11-10 | AI Assistant | 初版创建 |
