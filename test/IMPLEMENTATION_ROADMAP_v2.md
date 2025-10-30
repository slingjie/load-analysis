# 📋 实现方案 v2.0 - 数据完整性分析

## 🎯 需求变更摘要

**原始需求 (v1.0):**
- 对原始数据进行清洗，输出小时级数据
- 基于清洗后的数据进行质量分析

**新需求 (v2.0):**
1. **不进行数据清洗** - 仅对原始数据进行完整性分析
2. **按月分类缺失分析** - 缺失统计按月份汇总展示

---

## 🔧 技术变更

### 后端变更

#### 1. quality.py 修改

**关键变化:**
- `build_quality_report(raw_df)` 签名改为：不再需要 `CleanResult`
- `_collect_missing(raw_df)` 直接分析原始数据
- 返回按月分类的缺失统计

**新的返回结构:**
```python
{
    "missing": {
        "missing_days": ["2024-10-27", "2024-10-28", ...],  # 缺失日期列表
        "missing_hours_by_month": [
            {
                "month": "2024-10",
                "missing_days": 5,      # 该月缺失的天数
                "missing_hours": 120    # 该月缺失的小时数（= 缺失天数 * 24）
            },
            ...
        ],
        "summary": {
            "total_missing_days": 5,    # 总缺失天数
            "total_missing_hours": 120  # 总缺失小时数
        }
    },
    "anomalies": [...],                 # 仍然检测 null/zero/negative
    "continuous_zero_spans": []         # 不再分析（v2.0 范围外）
}
```

#### 2. app.py 修改

**关键变化:**
- 删除 `from .services import cleaner` 导入
- 删除 `cleaner.clean_and_aggregate()` 调用
- `quality.build_quality_report()` 直接传入原始数据框

**新的处理流程:**
```
上传文件
  ↓
loader.load_dataframe()  ← 解析文件
  ↓
quality.build_quality_report(raw_df)  ← 直接分析原始数据
  ↓
返回原始数据点 + 分析报告
```

#### 3. schemas.py 修改

**新增类:**
```python
class MissingHoursByMonth(BaseModel):
    month: str          # "2024-10" 格式
    missing_days: int
    missing_hours: int

class MissingSummary(BaseModel):
    missing_days: List[str]
    missing_hours_by_month: List[MissingHoursByMonth]
    summary: dict       # {"total_missing_days": int, "total_missing_hours": int}
```

---

### 前端变更

#### 1. types.ts 修改

**新增类型:**
```typescript
interface BackendMissingHoursByMonth {
  month: string;          // "2024-10"
  missing_days: number;
  missing_hours: number;
}

interface BackendMissingSummary {
  missing_days: string[];
  missing_hours_by_month: BackendMissingHoursByMonth[];
  summary: {
    total_missing_days: number;
    total_missing_hours: number;
  };
}
```

#### 2. LoadAnalysisPage.tsx 修改

**QualityReportPanel 更新:**

原结构:
```
基础信息 | 缺失情况
异常值统计
连续零值时段
```

新结构:
```
基础信息 | 缺失总体情况
按月分类缺失统计（表格）
缺失日期详情（列表）
异常值统计
```

**显示内容:**

| 模块 | 内容 |
|------|------|
| 基础信息 | 时间范围、原始记录数、采样间隔 |
| 缺失总体 | 缺失天数、缺失小时数、完整度% |
| 按月统计 | 月份、缺失天数、缺失小时数（表格） |
| 缺失日期 | 完整的缺失日期列表（分行显示） |
| 异常值 | null/zero/negative 统计及示例 |

---

## 📊 数据流示例

### 输入
```csv
timestamp,load
2024-11-01 00:00:00,100.5
2024-11-01 01:00:00,110.3
...
2025-10-26 23:00:00,95.2
```

### 处理
1. loader 解析 CSV → 34,560 条记录
2. quality.build_quality_report() 分析：
   - 扫描365天窗口（2024-10-27 ~ 2025-10-26）
   - 识别 5 个缺失天（2024-10-27~31）
   - 按月统计：10月缺失5天120小时，其他月正常

### 输出
```json
{
  "report": {
    "missing": {
      "missing_days": ["2024-10-27", "2024-10-28", "2024-10-29", "2024-10-30", "2024-10-31"],
      "missing_hours_by_month": [
        {
          "month": "2024-10",
          "missing_days": 5,
          "missing_hours": 120
        }
      ],
      "summary": {
        "total_missing_days": 5,
        "total_missing_hours": 120
      }
    },
    "anomalies": [
      {"kind": "null", "count": 0, "ratio": 0.0, "samples": []},
      {"kind": "zero", "count": 2, "ratio": 0.0058, "samples": ["2025-05-31T11:00Z", ...]},
      {"kind": "negative", "count": 0, "ratio": 0.0, "samples": []}
    ],
    "continuous_zero_spans": []
  },
  "cleaned_points": [...原始数据点...],
  "meta": {
    "source_interval_minutes": 0,
    "total_records": 34560,
    "start": "2024-11-01T00:00:00",
    "end": "2025-10-26T23:00:00"
  }
}
```

---

## 🎨 前端UI 展示

### QualityReportPanel 新布局

```
┌─────────────────────────────────────────────────────┐
│  4. 数据完整性分析报告                              │
├─────────────────────────────────────────────────────┤
│ ┌──────────────────┐  ┌──────────────────────────┐  │
│ │ 基础信息          │  │ 缺失总体情况             │  │
│ │ 时间范围: ...     │  │ 缺失天数: 5             │  │
│ │ 记录数: 34560     │  │ 缺失小时: 120           │  │
│ │ 采样间隔: 0 分钟  │  │ 完整度: 99.28%          │  │
│ └──────────────────┘  └──────────────────────────┘  │
├─────────────────────────────────────────────────────┤
│  按月分类缺失统计                                   │
│  ┌────────┬──────────┬──────────┐                  │
│  │ 月份   │ 缺失天数 │缺失小时数│                  │
│  ├────────┼──────────┼──────────┤                  │
│  │2024-10 │    5     │   120    │                  │
│  └────────┴──────────┴──────────┘                  │
├─────────────────────────────────────────────────────┤
│  缺失日期详情                                       │
│  • 2024-10-27                                       │
│  • 2024-10-28                                       │
│  • 2024-10-29                                       │
│  • 2024-10-30                                       │
│  • 2024-10-31                                       │
├─────────────────────────────────────────────────────┤
│  异常值统计                                         │
│  ┌──────────────┐  ┌──────────────┐               │
│  │ 空值         │  │ 零值         │               │
│  │ 数量: 0      │  │ 数量: 2      │               │
│  │ 占比: 0.00%  │  │ 占比: 0.01%  │               │
│  └──────────────┘  └──────────────┘               │
└─────────────────────────────────────────────────────┘
```

---

## ✅ 实现完成检查清单

### 后端
- [x] quality.py - `_collect_missing()` 改为处理原始数据
- [x] quality.py - `build_quality_report()` 签名改为只需 raw_df
- [x] quality.py - 返回按月分类的缺失统计
- [x] app.py - 删除 cleaner 导入和调用
- [x] app.py - 返回原始数据点
- [x] schemas.py - 新增 MissingHoursByMonth、更新 MissingSummary

### 前端
- [x] types.ts - 新增 BackendMissingHoursByMonth
- [x] types.ts - 更新 BackendMissingSummary
- [x] LoadAnalysisPage.tsx - 更新 QualityReportPanel 组件
- [x] LoadAnalysisPage.tsx - 适配新的数据结构
- [x] LoadAnalysisPage.tsx - 移除清洗效果相关显示

### 文档
- [x] 本文档 - 说明所有变更
- [ ] 创建测试脚本验证新流程

---

## 🧪 测试验证

### 测试场景
1. **正常完整数据** - 365天连续数据，无缺失
2. **部分缺失数据** - 某月缺失若干天
3. **月初缺失** - 如示例中 2024-10 月初5天缺失
4. **异常值检测** - null/zero/negative 值正确统计

### 验证清单
- [ ] 按月统计准确无误
- [ ] 完整度计算正确
- [ ] 前端展示对应数据值
- [ ] 无异常值时正确显示
- [ ] 表格排版合理

---

## 📝 更改日志

**v2.0 (当前)**
- 变更：不进行数据清洗，仅进行完整性分析
- 变更：缺失分析改为按月分类
- 删除：连续零值分析
- 新增：月份维度的缺失统计表格
- 新增：完整度百分比计算

**v1.0 (原始版本)**
- 功能：完整的数据清洗管道
- 功能：质量报告生成
- 功能：时间序列可视化

---

## 🚀 下一步

1. **后端测试** - 运行 FastAPI 服务，上传测试文件
2. **前端测试** - 验证 QualityReportPanel 显示正确
3. **完整测试** - 使用实际数据验证所有功能
4. **性能测试** - 确保大文件处理速度 <5 秒
5. **上线部署** - 更新生产环境代码

---

## 💡 FAQ

**Q: 为什么不进行数据清洗？**
A: 用户需求是分析原始数据的完整性，而不是获得清洗后的数据。清洗是额外的处理，会改变原始值。

**Q: `source_interval_minutes` 为什么是 0？**
A: 原始数据的采样间隔不确定（可能是 15 分钟、30 分钟等），所以设为 0。如需推断间隔，可在前端根据原始数据计算。

**Q: 如何判断完整度？**
A: 完整度 = 1 - (缺失小时数 / 期望总小时数)
期望总小时数 = 365 * 24 = 8760 小时

---

**方案制定时间**: 2025-10-30  
**状态**: ✅ 已实现
