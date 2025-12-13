# dataset-reuse Specification

## Purpose
TBD - created by archiving change add-project-dataset-records. Update Purpose after archive.
## Requirements
### Requirement: 引用已保存数据集参与测算（避免重复上传）
系统 MUST 支持在测算页面直接引用已加载的数据集点位进行计算，避免用户重复上传文件。

#### Scenario: 储能次数测算复用点位
- 当用户已加载某个数据集，且进入“储能测算”页面，
- 用户选择“复用已分析/已加载数据”后提交测算，
- 前端应通过 `payload.points` 提交点位数组，后端无需再接收文件也能完成计算。

#### Scenario: 无数据集时回退上传
- 当用户未加载任何数据集时，
- 测算页面应提示用户上传文件或先加载数据集，并保留原有上传能力。

### Requirement: 全局负荷数据引用一致性
系统 MUST 保证“负荷分析页”与“测算页”引用的是同一份全局负荷序列，以减少口径不一致导致的误差。

#### Scenario: 切换数据集
- 当用户切换到另一数据集并加载成功后，
- 负荷分析页的图表/统计应同步切换到新数据集，测算页的“复用数据”也应使用新数据集。

