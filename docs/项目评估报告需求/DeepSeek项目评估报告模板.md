# 储能项目评估报告（模板）

> 说明：本模板用于业主方项目评估报告初稿，由系统基于负荷数据、TOU 配置和储能模拟结果自动生成，解决方案工程师可在此基础上再编辑完善。

---

## 第 1 章 项目概况与评估结论

### 1.1 项目基本信息
- 项目名称：{{project.name}}
- 项目地点：{{project.location}}
- 评估周期：{{project.periodDescription}}（例如：{{project.periodStart}} ~ {{project.periodEnd}}）
- 负荷数据来源：{{project.loadDataSource}}
- 电价 / TOU 配置来源：{{project.touSource}}
- 储能模拟版本与日期：{{project.simulationVersion}}，{{project.reportDate}}

### 1.2 首页评估结论摘要
> 本小节为管理层“先看一页”的结论性内容。

- 首年总收益（含主要收益项）：{{summary.firstYearRevenueDescription}}
- 等效年循环次数 / 日均循环次数：{{summary.cycleStats}}
- 储能利用小时数区间：{{summary.utilizationHoursRange}}
- 上传负荷文件数据完整情况：{{summary.loadDataCompleteness}}
- 综合结论（经济性与策略合理性）：{{summary.overallConclusion}}

---

## 第 2 章 用户负荷特征与典型运行情况

### 2.1 负荷总体特征
- 评估周期内平均负荷：{{loadProfile.avgLoad}}
- 峰值负荷：{{loadProfile.peakLoad}}
- 谷值负荷：{{loadProfile.valleyLoad}}
- 峰谷差情况：{{loadProfile.peakValleyDifferenceDescription}}

### 2.2 典型日/周运行模式
- 工作日与周末负荷曲线差异：{{loadProfile.workdayWeekendPattern}}
- 昼夜变化特征：{{loadProfile.dayNightPattern}}
- 季节性或月份差异：{{loadProfile.seasonalPattern}}

### 2.3 充放电潜力与可利用时段
- 典型尖峰时段及负荷水平：{{loadProfile.peakPeriods}}
- 典型低谷时段及负荷水平：{{loadProfile.valleyPeriods}}
- 适合作为储能充电 / 放电的时间窗口：{{loadProfile.storageOpportunityWindows}}

### 2.4 数据质量与代表性说明
- 负荷数据缺失/异常占比：{{quality.loadMissingRateDescription}}
- 清洗与插补处理说明：{{quality.loadCleaningSummary}}
- 对评估结论可靠性的影响说明：{{quality.impactOnConclusion}}

---

## 第 3 章 当前 TOU 配置与运行策略

### 3.1 TOU 配置概述
> 该表格为对外报告版本，可按需隐藏具体电价，仅展示结构。

- 电价政策 / TOU 方案名称：{{tou.name}}
- TOU 生效范围：{{tou.effectivePeriod}}

#### 3.1.1 TOU 时段与电价表

{{tou.tableMarkdown}}

### 3.2 电价与负荷适配度分析
- 高价（峰段）时段与高负荷时段重合情况：{{tou.matchHighLoad}}
- 低价（谷段）时段与可充电窗口重合情况：{{tou.matchLowLoad}}
- 价差结构对储能套利 / 削峰的支持程度：{{tou.priceSpreadSupport}}

### 3.3 当前运行策略（运行逻辑）

#### 3.3.1 口语化运行策略描述
- 总体调度思路：{{strategy.narrativeSummary}}
- 典型运行方式示例：{{strategy.typicalPatternExample}}

#### 3.3.2 运行规则摘要（文字版）
- 充电规则：{{strategy.chargeRules}}
- 放电规则：{{strategy.dischargeRules}}
- SOC 上下限与保护策略：{{strategy.socLimitsAndProtection}}
- 充/放电余量设置：{{strategy.reserveMarginSettings}}
- 特殊逻辑（如需量控制、保底电量等）：{{strategy.specialLogic}}

---

## 第 4 章 储能电站配置与模拟方式

### 4.1 储能配置情况
- 储能容量：{{storage.capacityMWh}} MWh
- 储能功率：{{storage.powerMW}} MW
- 配置口径：{{storage.configPerspective}}（例如：以按容为主 / 以按需为主 / 双口径对比）
- 充放电效率假设：{{storage.efficiencyDescription}}
- SOC 上下限设定：{{storage.socRangeDescription}}
- 充/放电余量：{{storage.reserveMarginDescription}}

### 4.2 模拟场景说明
- 基准场景名称及说明：{{scenarios.baseScenarioDescription}}
- 其他典型场景（如有）：{{scenarios.otherScenarioSummary}}
- 关键假设边界（电价、负荷、策略变化等）：{{scenarios.assumptionBoundary}}

### 4.3 运行逻辑与约束条件
- 运行目标（削峰、套利、需量控制等）：{{storage.operationObjectives}}
- 主要约束条件及其对结果的影响：{{storage.constraintsImpact}}

---

## 第 5 章 储能充放次数与收益评估

### 5.1 充放次数与循环利用情况
- 评估周期内等效年循环次数：{{results.effectiveAnnualCycles}}
- 日均循环次数：{{results.dailyCycles}}
- 工作日 / 周末循环模式差异：{{results.cyclePatternWorkdayWeekend}}

### 5.2 储能利用效率
- 年度（或评估周期）储能利用小时数区间：{{results.utilizationHoursRangeDetail}}
- 实际平均放电能量占可用容量比例：{{results.energyUtilizationRatio}}
- 是否存在“经常闲置”或“高峰时电量不足”的现象：{{results.utilizationIssues}}

### 5.3 收益构成与首年总收益
- 首年总收益：{{results.firstYearRevenueDetail}}
- 收益构成（削峰、需量费降低、价差套利等）：{{results.revenueComponents}}
- 单位容量 / 功率收益水平的定性判断：{{results.revenuePerUnitJudgement}}

### 5.4 经济性与敏感性简要分析
- 简要回收期判断（如已有）：{{results.paybackPeriodDescription}}
- 对关键参数（电价、利用小时数等）的敏感性定性分析：{{results.sensitivitySummary}}

---

## 第 6 章 风险点与优化建议

### 6.1 主要风险点
- 电价政策变化风险：{{risks.tariffPolicyRisk}}
- 数据代表性与质量风险：{{risks.dataQualityRisk}}
- 市场环境与负荷变化不确定性：{{risks.marketAndLoadUncertainty}}
- 其他重要风险（如有）：{{risks.otherRisks}}

### 6.2 策略与配置优化建议
> 建议以“方向性 + 清晰倾向”方式给出，供解决方案工程师与业主进一步讨论。

- 储能配置层面（容量 / 功率）：{{recommendations.storageSizing}}
- 运行策略层面（充放逻辑、SOC 管理等）：{{recommendations.operationStrategy}}
- TOU / 电价结构层面（如可与电网侧协同优化）：{{recommendations.touDesign}}
- 数据与运维层面（数据采集、监测、复评节奏）：{{recommendations.dataAndOandM}}

### 6.3 后续工作建议
- 建议的后续评估或试点步骤：{{recommendations.nextSteps}}
- 建议复评时间或触发条件：{{recommendations.reassessmentTriggers}}

---

## 第 7 章 附录：数据与参数表

### 7.1 负荷统计表
{{appendix.loadStatsTableMarkdown}}

### 7.2 TOU 参数表
{{appendix.touParamsTableMarkdown}}

### 7.3 储能参数表
{{appendix.storageParamsTableMarkdown}}

### 7.4 储能运行结果明细表
{{appendix.storageResultsTableMarkdown}}

### 7.5 数据质量与清洗说明
{{appendix.dataQualityDetailsMarkdown}}

---

> 提示：
> - 系统生成时可优先填充“摘要型”字段（如 {{summary.*}}），
>   对附录等长表格字段（如 {{appendix.*}}）可以按需开启或由人工二次补充；
> - DeepSeek 输出时应严格遵守上述章节结构与标题，方便自动比对和版本管理。