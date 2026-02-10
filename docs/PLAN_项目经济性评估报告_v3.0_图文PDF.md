# 开发计划（Plan）：项目经济性评估报告 v3.0（图文 PDF 一键导出）

> 本计划以“最小可交付（MVP）→ 可用增强（E1）→ 体验增强（E2）”分阶段推进。  
> 依赖开发 PRD：`docs/PRD_项目经济性评估报告_v3.0_开发PRD.md`。

| 版本 | 日期 | 作者 | 说明 |
| --- | --- | --- | --- |
| v3.0-plan | 2025-12-14 | 系统架构师 | 拆解任务、里程碑、交付物、验证清单 |

---

## 0. 里程碑定义

### M0：技术预研完成（0.5 天）
- 确认后端可运行 Headless Chromium（Playwright/Chromium）并输出 PDF
- 确认中文字体渲染与分页边距稳定

### M1：MVP 可导出 PDF（2–4 天）
- 报告中心页面可选择数据源、填写总投资、导出 PDF
- PDF 含封面、页眉页脚、核心指标、至少 6 张图表（缺数据可占位）
- 典型日规则生效（收益最高日/最大负荷日）
- 方案 A（双轨并行）落地：保留旧 Markdown 报告入口不变，新增 PDF 报告中心入口

### M2：可追溯与稳定性增强（2–3 天）
- 报告导出后保存报告快照/制品（artifact）
- 缺失项清单弹窗与报告占位提示完善
- AI 润色开关接入（失败自动降级）

### M3：体验增强（可选，2–5 天）
- A4 预览分页体验优化
- 表格跨页/长表分页优化
- 手动选择典型日日期（覆盖默认规则）

---

## 1. 任务拆解（按模块）

### 1.0 方案 A：与原功能双轨并行（必须）
- 保留现有“Markdown 报告（旧）”页面与接口不变（用于生成纯文本报告初稿）
- 新增“PDF 报告中心（新）”入口与页面（正式交付）
- 导航与文案区分：明确“旧=Markdown 初稿/新=PDF 交付”
- 回滚策略：PDF 导出链路异常时不影响旧功能使用

### 1.1 前端：ReportCenterPage（核心）
- 新建页面与路由/导航入口
- 数据源选择：Project/Dataset/Run（复用 `localProjectStore.ts`）
- 参数表单：总投资（万元）必填；其余选填；Logo 上传（可选）
- 完成度检查：生成缺失项清单（阻断项/提示项）
- 预览：A4 容器 + 分章渲染（MVP 可先“导出为主，预览简版”）

交付物：
- 新组件：`components/ReportCenterPage.tsx`（或改造现 `ProjectSummaryPage.tsx`）
- 新的报告数据组装函数：`utils/reportDataBuilder.ts`（建议新增）

### 1.2 前端：典型日计算与曲线拉取
- 实现 `pickBestProfitDay(cyclesResponse)`：从 `days` 选 `profit.main.profit` 最大日期
- 实现 `pickMaxLoadDay(loadPoints)`：按日聚合 `max(load)` 最大日期
- 对两个日期分别调用 `fetchStorageCurves(payload, date)`，得到曲线

交付物：
- `utils/reportTypicalDays.ts`（建议新增）

### 1.3 前端：图表导出为 PNG（chart_images）
- 定义 chart_id 列表与导出规范（2x/3x）
- 复用现有 ECharts 实例导出（`getDataURL`），或实现统一 `renderToPng()` 工具
- 缺数据时返回 `null` 并在报告中展示占位块
- 去除 CDN 依赖：报告导出链路必须使用本地 ECharts（避免网络失败）

交付物：
- `utils/reportChartExport.ts`（建议新增）
- 若现有组件仍通过 CDN 加载 ECharts：为报告导出新增一套“本地 ECharts 渲染组件”

### 1.4 后端：PDF 生成服务
- 新增 API：
  - `POST /api/report/pdf`：返回 `application/pdf`
  - （可选）`POST /api/report/html`：返回 HTML 便于调试
- 模板渲染：
  - 使用 Jinja2/字符串模板生成 HTML（推荐后端渲染，前端只传数据+图片）
  - 嵌入 `chart_images`（base64）与表格数据
- PDF 导出：
  - 使用 Playwright 生成 PDF（A4、边距、页眉页脚）
  - 失败返回清晰错误信息（字体缺失/Chromium 不可用等）

交付物：
- `backend/services/report_pdf.py`（建议新增）
- `backend/app.py` 增加路由
- `backend/schemas.py` 增加请求模型（如 `ReportPdfRequest`）

### 1.5 AI 文案润色（可选开关）
- 开关关闭：模板化文本（强默认）
- 开关开启：调用 LLM 仅润色文本段落；失败降级
- 需要“文本字段与数值字段分离”，避免模型改数值

交付物：
- `backend/services/report_ai_polish.py`（建议新增，可复用 deepseek 调用封装）

### 1.6 报告快照与制品保存（可追溯）
- 导出成功后：
  - 前端保存 `report_data` JSON（作为 artifact）
  - 保存 PDF 文件（作为 artifact）
- 复用 `localProjectStore.ts` 的 `run_artifacts`（kind：`report_pdf`、`report_data_json`）

交付物：
- `localProjectStore.ts`：增加/复用保存 artifact 的调用点（若已有则直接调用）
- `ReportCenterPage`：导出后写入 artifact

---

## 2. 风险清单与应对

1. 中文字体缺失导致 PDF 乱码/换行异常  
   - 应对：随服务打包字体或指定系统字体；增加“字体自检”接口/日志
2. 图表清晰度不足  
   - 应对：2x/3x 导出；PDF 中固定宽度并禁用缩放模糊
3. 缺数据导致“0 值误导”  
   - 应对：缺失项清单 + 报告占位提示；模板层不自动填 0
4. 网络依赖（CDN）导致导出失败  
   - 应对：报告导出链路完全本地化（ECharts/字体/模板）

---

## 3. 手工验证清单（每次发版必跑）

- 完整数据样例导出：打开 PDF、检查页码/页眉页脚/图表清晰度
- 缺 cycles 导出：提示缺失项；报告对应章节为占位
- 缺 economics 导出：提示缺失项；报告对应章节为占位
- 典型日同日冲突：只展示一次并标题标注
- AI 开关开启但失败：仍能导出且文本降级

---

## 4. 建议的交付顺序（推荐）

1) 后端先打通最小 PDF 导出（固定 HTML + 假数据）→ 确保环境可用  
2) 前端组装 `report_data`（不含 AI）→ 能导出“真实数据 PDF”  
3) 加典型日曲线拉取 + 图表导出 → 报告图文完整  
4) 加缺失项清单与占位策略 → 稳定可交付  
5) 最后接 AI 文案润色开关（可选）→ 体验增强但不影响主链路
