# project-run-snapshots Specification

## Purpose
TBD - created by archiving change add-project-dataset-records. Update Purpose after archive.
## Requirements
### Requirement: 项目级测算快照（Runs）持久化
系统 MUST 支持在本地持久化保存“项目测算快照”，用于在下次打开时直接查看测算结果与当时配置。

#### Scenario: 保存快照（cycles 必须）
- 当用户完成一次 cycles 测算并获得后端返回结果时，
- 用户可将本次测算保存为快照，
- 快照 MUST 至少包含：所属项目、负荷数据引用（数据集或点位兜底）、配置快照（TOU/储能逻辑/日期规则/价格）与 cycles 结果。

#### Scenario: 保存快照（economics 可选）
- 当用户已完成 economics 计算并获得结果时，
- 保存快照时应同时保存 economics 输入与结果（若不存在则允许为空）。

#### Scenario: 保存快照（profit 必须）
- 当用户完成收益页所需的数据获取（至少包含 cycles_result，且如存在 curves 数据则一并保存）时，
- 保存快照 MUST 同时保存 `StorageProfitPage` 的完整数据明细（用于下次直接回看收益曲线与指标）。

### Requirement: 快照列表与详情查看
系统 MUST 支持按项目列出快照，并提供快照详情页用于回看关键数据。

#### Scenario: 列表展示
- 当用户进入某项目时，
- 系统应展示该项目下快照列表（至少包含：名称、创建时间、是否包含 economics）。

#### Scenario: 详情展示
- 当用户打开某条快照时，
- 系统应展示 cycles 关键指标（年累计/月度/日度等）、profit 关键指标与曲线概览，以及 economics 关键指标（若存在），并展示保存时的配置快照概要。

### Requirement: 快照加载与复用
系统 MUST 支持将某条快照加载回应用上下文用于查看与后续操作。

#### Scenario: 加载用于查看
- 当用户在快照详情页点击“加载此快照”时，
- 系统应将其引用的负荷数据集加载为全局负荷数据（必要时从本地数据集读取点位），并可用于页面间复用。

#### Scenario: 恢复配置（可选）
- 当用户选择“按快照恢复配置”时，
- 系统应将快照中的 TOU/储能逻辑/日期规则/价格写回当前编辑配置（或作为新配置导入），以便复算与对比。

### Requirement: 快照导入导出（本地备份）
系统 MUST 支持以 JSON 形式导出/导入项目快照，便于备份与跨电脑迁移（作为第二阶段上云前的过渡手段）。

#### Scenario: 导出包含快照
- 当用户导出项目为 JSON 时，
- 导出内容 MUST 包含：项目、数据集元信息与点位、快照（runs）记录，以及快照导出文件（Excel/ZIP/CSV 等）的二进制内容（建议以 base64 形式封装）。

#### Scenario: 导入包含快照
- 当用户导入项目 JSON 时，
- 系统应恢复项目、数据集与快照，并保证快照仍可被加载查看。

