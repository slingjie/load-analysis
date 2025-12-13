## ADDED Requirements

### Requirement: Supabase 环境配置与初始化
系统 MUST 支持在前端通过环境变量配置 Supabase 连接，并在配置存在时完成客户端初始化。

#### Scenario: 环境变量
- 当配置 `VITE_SUPABASE_URL` 与 `VITE_SUPABASE_ANON_KEY` 时，
- 前端应能初始化 Supabase 客户端并用于后续读写。

#### Scenario: 缺失配置降级
- 当缺失 Supabase 配置时，
- 系统应以“本地持久化保存/复用”的流程运行，并向用户提示“云端保存不可用（当前为本地模式）”。

### Requirement: 登录与会话恢复（默认推荐）
系统 MUST 在启用 Supabase 模式时支持最小登录能力并在刷新后恢复会话，以实现用户级数据隔离。

#### Scenario: 登录/登出
- 用户可进行登录与登出操作；
- 未登录用户不可访问其私有项目/数据集列表。

#### Scenario: 会话恢复
- 当用户刷新页面或重新进入系统时，
- 系统应恢复上次登录会话（若会话仍有效），并可继续访问其项目/数据集。

### Requirement: 数据权限（RLS）
Supabase 数据表 MUST 开启 RLS，默认按用户隔离项目与数据集。

#### Scenario: 用户隔离
- 当用户 A 访问 `projects/datasets` 时，
- 不应读取或写入用户 B 的数据。

### Requirement: 本地数据迁移到 Supabase（第二阶段）
系统 MUST 在启用 Supabase 模式且检测到存在本地项目/数据集时，提供将本地数据迁移到 Supabase 的入口。

#### Scenario: 迁移向导
- 当用户进入“项目/数据集管理”并启用 Supabase 模式时，
- 系统应提供“迁移到云端”的入口，展示将迁移的项目/数据集数量与预计数据量，并允许用户确认后执行迁移。

#### Scenario: 迁移结果
- 当迁移执行完成时，
- 系统应提示成功/失败清单，并确保已迁移的数据集可在云端列表中加载使用。
