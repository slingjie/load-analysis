# 设计：项目级数据集保存与复用（本地优先，后续可迁移 Supabase）

## 目标与约束
- 目标：让用户“上传一次→多次复用”，在不同页面/不同会话中直接引用已保存的负荷数据集进行测算。
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
1) 第一阶段：采用方案 A，先完成“输入数据集本地保存/加载/复用”的最小闭环；
2) 第二阶段：在不破坏本地能力的前提下引入方案 B，并提供“本地→Supabase”迁移入口；
3) 如未来点位规模显著增大或希望减少前端带宽，再考虑演进到方案 C。

## 关键设计：统一存储抽象，降低迁移成本
为避免“先本地、后上云”带来大规模重构，建议在前端引入统一抽象（命名仅示意）：
- `ProjectStore`：负责项目的增删改查；
- `DatasetStore`：负责数据集元信息与点位内容的存取；
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

## RLS 与权限建议（第二阶段）
- `projects/datasets/runs` 全部开启 RLS，默认规则：
  - `owner_user_id = auth.uid()` 的行可读写。
  - `project_id` 关联时也应保证同一 owner。
- Storage：
  - 建议 bucket：`datasets`
  - 对象路径建议：`{auth.uid()}/{project_id}/{dataset_id}/data.csv.gz`
  - 访问策略：仅允许 owner 读写自己目录。

## “引用数据集”复用链路（第一阶段最小闭环）
1) 用户上传负荷文件 → 现有后端 `/api/load/analyze` → 前端得到 `cleaned_points/meta/report`（现有能力）。
2) 用户点击“保存到项目”：
   - 前端将 `cleaned_points` 规范化为统一格式（timestamp, load_kwh），写入 IndexedDB（优先）；
   - 同时保存数据集元信息（时间范围、点数、采样间隔、质量报告与元信息）。
3) 用户后续进入系统，选择项目与数据集：
   - 前端从本地存储拉取点位数据并解析为 `LoadDataPoint[]`；
   - 写入 `App.tsx` 全局的 `loadCleanedData/loadMeta/loadQuality`；
   - `StorageCyclesPage` 勾选“复用已分析/已加载数据”后，走 `payload.points` 调用现有后端测算接口（无需再次上传文件）。

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
