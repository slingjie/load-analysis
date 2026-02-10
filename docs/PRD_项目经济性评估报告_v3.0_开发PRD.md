# 开发 PRD：项目经济性评估报告 v3.0（图文 PDF 一键导出）

> 本文为“开发可落地版本”的 PRD：明确页面/接口/数据结构/异常兜底/验收用例。  
> 对应业务 PRD：`docs/PRD_项目经济性评估报告_v3.0_图文PDF.md`。

| 版本 | 日期 | 作者 | 变更说明 |
| --- | --- | --- | --- |
| v3.0-dev | 2025-12-14 | 系统架构师 | 将业务 PRD 拆解为开发 PRD：数据引用、API、页面与验收用例 |

---

## 1. 范围与约束

### 1.1 本期范围（必须）
- 新增“报告中心”页面：选择项目/数据集/运行快照，填写报告参数，预览并一键导出 PDF。
- PDF 报告结构与图表符合业务 PRD（章节按工作流顺序）。
- 典型日规则固定：
  - 收益最高日：`max(day.profit.main.profit)`
  - 最大负荷日：`max(按日聚合后的 max(load))`
- AI 文案润色开关：
  - 关闭：模板化文本（不依赖外网/密钥）
  - 开启：仅润色“摘要/结论/风险/建议”，严禁编造数值
- 不输出 NPV：不增加折现率输入、不展示 NPV 字段。
- **PDF 模板无固定公司 Logo/主题色**：默认中性风格；允许用户选填 Logo（可选），但不预置任何公司信息。

### 1.2 不做（v3.0 不包含）
- 拖拽式模板编辑
- Word 导出
- 多项目批量导出
- NPV/折现率

---

## 2. 数据引用总览（从程序“已实现能力”取数）

### 2.1 关键数据来源（现状）
- 负荷分析：后端 `/api/load/analyze` 返回 `meta/report/cleaned_points`
  - 后端模型：`backend/schemas.py:MetaInfo` 已包含 `avg_load_kw/max_load_kw/min_load_kw`
- TOU + 运行策略：前端 `appState`（`monthlySchedule/dateRules/prices`）
- cycles 测算：后端 `/api/storage/cycles`（由 `StorageCyclesPage` 调用），前端保存 `lastStorageRun`
- 典型日曲线：后端 `/api/storage/curves?date=...`（由 `StorageProfitPage` 调用）
- 经济性：后端 `/api/storage/economics`（由 `StorageEconomicsPage` 调用），前端保存 `lastEconomicsRun`
- 本地快照：`localProjectStore.ts` 已支持保存 `config_snapshot/cycles_snapshot/economics_snapshot/profit_snapshot` 与 `run_artifacts`

### 2.2 报告“report_data”统一结构（建议 v1）
> 目标：前端组装一次 `report_data`，后端只负责模板渲染与 PDF 生成。

```json
{
  "meta": {
    "report_version": "v3.0",
    "generated_at": "ISO8601",
    "project_name": "string",
    "owner_name": "string|null",
    "project_location": "string|null",
    "period_start": "YYYY-MM-DD",
    "period_end": "YYYY-MM-DD",
    "author_org": "string|null",
    "subtitle": "string|null",
    "logo_data_url": "data:image/png;base64,...|null",
    "total_investment_wanyuan": 123.45
  },
  "completeness": {
    "has_load": true,
    "has_tou": true,
    "has_cycles": true,
    "has_economics": true,
    "has_profit_curves_for_best_profit_day": true,
    "has_profit_curves_for_max_load_day": true,
    "missing_items": ["..."]
  },
  "load": {
    "meta": {
      "source_interval_minutes": 15,
      "total_records": 33888,
      "start": "ISO8601|null",
      "end": "ISO8601|null",
      "avg_load_kw": 0,
      "max_load_kw": 0,
      "min_load_kw": 0
    },
    "quality_report": { "missing": { "summary": {} }, "anomalies": [], "continuous_zero_spans": [] }
  },
  "tou": {
    "prices": "MonthlyTouPrices",
    "monthly_schedule": "Schedule",
    "date_rules": "DateRule[]"
  },
  "storage": {
    "cycles": "BackendStorageCyclesResponse|null",
    "cycles_payload": "StorageParamsPayload|null",
    "economics": { "input": "StorageEconomicsInput|null", "result": "StorageEconomicsResult|null", "user_share_percent": 0 },
    "typical_days": {
      "best_profit_day": { "date": "YYYY-MM-DD|null", "curves": "BackendStorageCurvesResponse|null" },
      "max_load_day": { "date": "YYYY-MM-DD|null", "curves": "BackendStorageCurvesResponse|null" }
    }
  },
  "charts": {
    "price_24h_png": "data:image/png;base64,...|null",
    "strategy_24h_png": "data:image/png;base64,...|null",
    "load_typical_png": "data:image/png;base64,...|null",
    "load_price_overlay_png": "data:image/png;base64,...|null",
    "capacity_compare_png": "data:image/png;base64,...|null",
    "cashflow_png": "data:image/png;base64,...|null",
    "best_profit_day_overlay_png": "data:image/png;base64,...|null",
    "max_load_day_overlay_png": "data:image/png;base64,...|null"
  },
  "ai_polish": {
    "enabled": false,
    "provider": "deepseek|null",
    "notes": "仅润色，不改数值"
  }
}
```

---

## 3. 页面与交互（前端）

### 3.1 页面：ReportCenterPage（新增）
**入口**：导航栏新增“报告中心”，或将现 `ProjectSummaryPage` 改造为报告中心（推荐保留旧页为“Markdown 报告（旧）”以回滚）。

**模块分区**：
1. 数据源选择区
   - Project（来自 `localProjectStore.listProjects()`）
   - Dataset（来自 `listDatasets(projectId)`）
   - Run（来自 `listRuns(projectId)`；并显示 run 中是否包含 cycles/economics/profit 快照）
   - 一键“使用当前页面最新结果”（直接用 `App.tsx` 内存态：`loadMeta/loadQuality/loadCleanedData/appState/lastStorageRun/lastProfitRun/lastEconomicsRun`）
2. 报告参数区
   - 必填：项目总投资（万元）
   - 选填：业主方、地点、作者/单位、封面副标题、Logo 上传（可选）
3. 完成度与缺失项提示
   - 缺失项清单：导出前必弹窗确认（但不强阻断，除必填项）
4. AI 文案润色开关
   - 开启时展示“将调用外部模型，仅润色文本，不改数值”的说明
5. 操作区
   - 预览（A4 分页视图）
   - 导出 PDF（下载）
   - 保存报告快照（保存到 `run_artifacts` 或新增 `report_snapshot`）

### 3.2 必填校验与导出门槛
- `total_investment_wanyuan` 缺失：阻断导出
- `project_name/period_start/period_end` 缺失：阻断导出
- cycles/economics/典型日缺失：允许导出，但必须弹出缺失项清单，并在报告对应章节展示“数据不足/未测算”

---

## 4. 典型日计算（算法细则）

### 4.1 收益最高日
输入：`BackendStorageCyclesResponse.days[]`  
规则：
- 仅考虑 `day.profit.main.profit` 为有限数值的日期
- 取最大值日期；若全为空或无 days：返回 `null`
- 若存在并列，优先选择日期最早或最晚（二选一固定即可，建议最早，便于可复现）

### 4.2 最大负荷日
输入：负荷点位 `LoadDataPoint[]` 或 `StoredLoadPoint[]`  
规则：
- 按 `YYYY-MM-DD` 分组
- 组内取 `max(load)`，全局取最大
- 若存在并列，同样采用固定 tie-break（建议最早）

### 4.3 典型日曲线获取
- 以 `StorageProfitPage` 的 `fetchStorageCurves(payload, date)` 为标准实现：
  - `payload` 优先使用 `lastStorageRun.payload`，否则用“默认 payload（由 schedule+points 构建）”
  - 对 `best_profit_day` 与 `max_load_day` 分别请求一次

---

## 5. 图表生成（前端导出为图片）

### 5.1 统一图表导出规范
- 每个图表导出为 PNG（建议 2x 像素比）
- 统一命名：`chart_id` → `data:image/png;base64,...`
- 对无法渲染的图表（缺数据）返回 `null`，由模板显示占位块

### 5.2 禁止依赖 CDN（离线要求）
- 当前部分页面使用 ECharts CDN 动态加载；报告导出链路必须改为本地依赖（npm 安装）或复用已有本地图表组件输出（避免网络依赖导致导出失败）。

---

## 6. 后端 API（PDF/HTML）

### 6.1 `POST /api/report/pdf`
输入：`report_data`（见 2.2）  
输出：`application/pdf`

错误码建议：
- 422：必填项缺失（项目名/周期/总投资）
- 400：report_data 结构非法（无法解析）
- 500：渲染失败（Chromium/模板异常）

### 6.2（可选）`POST /api/report/html`
用于开发调试排版，返回 `text/html`，便于快速定位分页/字体问题。

---

## 7. PDF 模板与排版（无固定 Logo/主题色）

### 7.1 基础规范
- A4，页边距固定（如：上下 18mm、左右 16mm）
- 页眉：`业主方名称（如有）- 储能项目经济性评估报告`
- 页脚：生成日期 + 页码
- 目录：可选（建议 v3.0 先不做自动目录页码，避免迭代复杂度）

### 7.2 视觉风格
- 不内置任何公司 Logo/主题色
- 默认中性色系（黑/灰/少量蓝色强调），避免“品牌绑定”
- 若用户上传 Logo，仅显示在封面右上或底部，不影响全局主题

---

## 8. AI 文案润色（可选开关）

### 8.1 输入与输出边界
- 输入：结构化数据（数值）+ 模板草稿段落
- 输出：仅允许修改自然语言段落（摘要/结论/风险/建议）
- 强约束：所有数值必须来自结构化数据；缺字段必须输出“数据不足/未测算”

### 8.2 可回退策略
- AI 调用失败：自动回退模板化文本，不影响 PDF 导出
- AI 开关默认关闭

---

## 9. 验收用例（开发可直接对照）

1. 完整数据链路（负荷+TOU+cycles+economics+典型日曲线）导出 PDF：
   - 下载成功，PDF 可打开
   - 至少 6 张图表存在且清晰
   - 关键数值与页面一致（IRR/回收期/LCOE/度电收益/cycles/放电能量/期末累计净现金流）
2. 缺 cycles：导出前提示缺失项；报告第 4 章显示“未测算”
3. 缺 economics：导出前提示缺失项；报告第 5 章显示“未测算”
4. 缺典型日曲线（curves 拉取失败）：典型日章节显示“数据不足/请求失败”
5. AI 开关开启但模型失败：仍能导出，文本回退模板

---

## 10. 开发说明（与现有代码的衔接建议）

### 10.1 复用点（优先复用，减少新逻辑）
- `localProjectStore.ts`：用于选择项目/数据集/运行快照；保存报告 artifacts
- `StorageProfitPage.tsx` 的 `fetchStorageCurves`：典型日曲线计算
- `StorageEconomicsPage.tsx`：现金流图与静态指标展示逻辑可抽取为 report 复用
- `types.ts`：统一字段单位与类型，避免报告出现 0

### 10.2 易错点（必须防护）
- 单位口径：`kW/kWh/元/万元` 必须在模板与表格中明确标注
- “总投资（万元）”与 `capex_total（元）` 口径不同：报告固定以用户填写为准，并可附录展示系统 CAPEX（可选）
- 缺数据时严禁自动填 0（除非该字段业务上本就允许为 0），应优先显示“未测算/数据不足”

