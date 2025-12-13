# 设计：项目级测算快照保存与复用（本地优先，后续可迁移 Supabase）

## 目标与约束
- 目标：让用户“测算一次→下次可回看”，在不同会话中直接查看某次测算的结果（cycles/economics 等）与当时配置（TOU/储能逻辑/日期规则/价格），必要时可复算。
- 第一阶段约束：支持本地个人电脑使用（可离线），不引入登录与云端依赖。
- 第二阶段约束：前端为静态部署（Cloudflare），数据库与对象存储使用 Supabase；避免在前端暴露 Supabase Service Role Key。

## 方案对比（按阶段）

### 方案 A：仅本地持久化（IndexedDB/LocalStorage）
- 优点：实现成本最低；无需额外后端/鉴权；离线可用。
- 缺点：仅限单浏览器/单设备；无法跨设备、无法真正“项目级”；清理浏览器数据会丢失。
- 适用：第一阶段交付；个人单机使用、无需云部署。

### 方案 B（推荐）：前端直连 Supabase（Auth + Postgres + Storage）
- 优点：与 Cloudflare 静态部署天然兼容；可跨设备；RLS 可提供用户级隔离；后续扩展共享/协作较自然。
- 缺点：需要增加登录流程；需要设计表结构、RLS 与 Storage 规则；前端需要处理网络与缓存。
- 适用：第二阶段迁移目标；你描述的“前端上云 + DB 在 Supabase”的目标形态。

### 方案 C：后端代管 Supabase（后端用 Service Key 读写）
- 优点：前端更简单；可在后端做压缩/去重/权限统一；可避免大点位在前端来回传。
- 缺点：需要稳定部署后端并保管密钥；增加系统组件；对 Cloudflare-only 的轻量部署不友好。
- 适用：未来需要更强的服务端能力（大文件、复杂共享、多租户、审计）。

推荐路线：
1) 第一阶段：采用方案 A，先完成“项目快照本地保存/加载/查看”的最小闭环（包含输入引用 + 配置快照 + 结果快照）；
2) 第二阶段：在不破坏本地能力的前提下引入方案 B，并提供“本地→Supabase”迁移入口；
3) 如未来点位规模显著增大或希望减少前端带宽，再考虑演进到方案 C。

## 关键设计：统一存储抽象，降低迁移成本
为避免“先本地、后上云”带来大规模重构，建议在前端引入统一抽象（命名仅示意）：
- `ProjectStore`：负责项目的增删改查；
- `DatasetStore`：负责数据集元信息与点位内容的存取；
- `RunStore`：负责“测算快照（runs）”的保存、列表与加载；
- 两套实现：
  - `Local*Store`：IndexedDB（优先）/localStorage（降级）；
  - `Supabase*Store`：Postgres + Storage。

业务侧（UI/页面）仅依赖抽象接口；通过配置/开关决定当前使用本地或 Supabase 实现，从而把迁移风险控制在“数据层”。

## 推荐数据模型（最小可用 + 可扩展）

### 表：projects
- 字段建议：`id`, `owner_user_id`, `name`, `description`, `created_at`, `updated_at`
- 说明：最小实现只需 `owner_user_id + name`。

### 表：datasets
- 字段建议：`id`, `owner_user_id`, `project_id`, `name`, `source_filename`, `content_sha256`, `storage_path`, `start_time`, `end_time`, `interval_minutes`, `points_count`, `quality_report_json`, `meta_json`, `created_at`, `updated_at`
- 说明：
  - `storage_path` 指向 Supabase Storage 中的对象（建议存放标准化后的 CSV/JSONL，并可 gzip）。
  - `content_sha256` 用于去重（同一用户/项目重复上传可提示复用）。
  - `quality_report_json/meta_json` 直接复用后端返回，便于追溯。

### 表：runs（可选，后续增强）
- 字段建议：`id`, `owner_user_id`, `project_id`, `dataset_id`, `run_type`（如 cycles/economics）, `input_payload_json`, `result_summary_json`, `artifact_path`, `created_at`
- 说明：用于保存“某次测算的参数快照与结果摘要/报表链接”，让用户能回看与复算。

### 本地 runs 模型（第一阶段落地）
第一阶段建议在本地增加 `runs`，每条记录代表“某一次完整测算的快照”，字段建议：
- `id`, `project_id`, `name`, `created_at`
- `dataset_ref`: `{ dataset_id }` 或 `{ embedded_points }`（默认引用数据集，避免重复存点位）
- `config_snapshot`: `{ monthlySchedule, dateRules, prices }`（包含 TOU 与储能逻辑配置）
- `cycles_snapshot`: `{ payload, response, saved_at }`（至少保存 response + 关键参数）
- `economics_snapshot`: `{ input, result, saved_at }`（若用户完成经济性测算，保存完整结果明细）
- `profit_snapshot`: `{ payload, cycles_result, curves, saved_at }`（保存收益页所需的完整数据明细）
- `notes/tags`（可选）

### 导出文件（artifacts）保存
用户要求将导出文件（Excel/ZIP/CSV 等）纳入快照，本地建议增加 `run_artifacts`：
- `run_id`, `kind`（如 cycles_excel/business_zip/economics_cashflow_csv 等）, `filename`, `mime`, `blob`
- IndexedDB 支持直接存 Blob；导出/导入 JSON 时需对 Blob 执行 base64 编码/解码（注意体积与耗时提示）。

## RLS 与权限建议（第二阶段）
- `projects/datasets/runs` 全部开启 RLS，默认规则：
  - `owner_user_id = auth.uid()` 的行可读写。
  - `project_id` 关联时也应保证同一 owner。
- Storage：
  - 建议 bucket：`datasets`
  - 对象路径建议：`{auth.uid()}/{project_id}/{dataset_id}/data.csv.gz`
  - 访问策略：仅允许 owner 读写自己目录。

## 第一阶段最小闭环（保存快照→回看）
1) 输入准备：用户上传负荷文件并完成清洗（或加载本地数据集）；
2) 完成测算：用户在 cycles 页完成测算（可选：在 economics 页完成经济性计算）；
3) 保存快照：用户点击“保存本次测算为快照”，系统在本地持久化保存：
   - 数据集引用（dataset_id）或点位嵌入（仅当未保存为数据集时作为兜底）；
   - 当时配置快照（TOU/储能逻辑/日期规则/价格）与关键参数；
   - cycles 结果快照、economics 结果快照（若存在）；
4) 回看：用户刷新或下次进入系统，可在“项目/快照”页看到快照列表并查看详情；可一键加载该快照用于查看（可选：恢复配置用于复算）。

## 第二阶段：迁移到 Supabase 的链路补充（概览）
1) 仍保留本地保存能力作为离线/降级；
2) 当用户配置并登录 Supabase 后：
   - 新保存的数据集同时写入 Supabase（或由用户手动选择“同步到云端”）；
   - 提供“迁移向导”：列出本地项目/数据集，批量上传到 Supabase Storage 并写入 `datasets` 表；
   - 迁移完成后，可切换为“云端优先”，但仍允许回退到本地。

## 性能与体验建议（不强制）
- 解析与序列化：
  - 点位在 3~5 万量级时，浏览器解析 CSV/JSONL 是可行的，但建议 gzip + 流式解析（后续增强）。
- 缓存：
  - 可将最近一次加载的数据集缓存到 IndexedDB（减少重复下载）。
- 失败降级：
  - 若 Supabase 不可用（第二阶段），允许用户继续走“本地保存/加载/复用”与“本地上传→内存复用”原流程。
