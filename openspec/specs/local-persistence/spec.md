# local-persistence Specification

## Purpose
TBD - created by archiving change add-project-dataset-records. Update Purpose after archive.
## Requirements
### Requirement: 本地项目与数据集持久化（默认启用）
系统 MUST 支持在本地持久化保存“项目”与“负荷数据集”，用于个人电脑场景下的跨会话复用（刷新/重启浏览器后仍可用）。

#### Scenario: 初始化与可用性
- 当用户首次打开系统时，
- 系统应创建/初始化本地存储（优先 IndexedDB；如不可用则降级到 localStorage），并保证核心功能可用。

#### Scenario: 离线可用
- 当浏览器处于离线状态时，
- 系统仍可加载本地已保存的数据集并用于测算（后端计算本身仍需后端可达，若后端不可达应给出可读提示）。

### Requirement: 本地保存数据集（来源于负荷分析结果）
系统 MUST 支持将负荷分析得到的点位序列保存为本地数据集，并关联到本地项目。

#### Scenario: 保存数据集
- 当用户已完成负荷分析且存在 `cleaned_points/meta/report`，
- 用户输入数据集名称并点击“保存到项目”，
- 系统应将点位与元信息保存到本地，并在数据集列表中可见。

#### Scenario: 重复保存提示
- 当用户尝试保存与现有数据集内容相同的数据（可通过 hash 或时间范围+点数等启发式判断），
- 系统应提示用户可复用已有数据集，避免无意义重复保存（实现口径可在实现阶段细化）。

### Requirement: 本地数据集加载到全局负荷状态
系统 MUST 支持从本地存储加载某个数据集到全局负荷状态，以供多个页面复用同一份数据。

#### Scenario: 加载并切换
- 当用户选择某个数据集并执行“加载/使用”，
- 系统应更新全局 `loadCleanedData/loadMeta/loadQuality`（或等价状态），并使负荷分析页与测算页同步引用该数据集。

### Requirement: 本地数据集维护能力
系统 MUST 支持对本地项目/数据集进行基础维护，以满足日常测试迭代。

#### Scenario: 重命名与删除
- 用户可重命名项目/数据集；
- 用户可删除数据集（可选：同时删除其点位内容）。

#### Scenario: 导入与导出（JSON）
- 用户可导出单个项目（含其数据集）为 JSON 文件；
- 用户可从 JSON 文件导入项目，用于备份或跨电脑迁移（第二阶段上云前的过渡手段）。

### Requirement: 本地测算快照持久化（Runs）
系统 MUST 支持在本地持久化保存项目测算快照（runs），并与项目关联。

#### Scenario: 刷新后仍可查看
- 当用户保存了至少一条快照后，
- 刷新页面或重新打开系统，
- 快照列表与详情仍可访问。

