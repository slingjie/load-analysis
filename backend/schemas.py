from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class MissingHoursByMonth(BaseModel):
    """每月缺失小时统计"""

    month: str = Field(description="月份，格式为 YYYY-MM")
    missing_days: int = Field(description="该月缺失的自然日数量")
    missing_hours: int = Field(description="该月缺失的数据小时数")


class MissingSummary(BaseModel):
    """缺失信息汇总"""

    missing_days: List[str] = Field(default_factory=list, description="缺失日期列表")
    missing_hours_by_month: List[MissingHoursByMonth] = Field(
        default_factory=list,
        description="按月统计的缺失小时信息",
    )
    summary: dict = Field(
        default_factory=dict,
        description="汇总信息，如 total_missing_days / total_missing_hours",
    )


class ValueAnomaly(BaseModel):
    """数值异常信息"""

    kind: Literal["null", "zero", "negative"]
    count: int
    ratio: float
    samples: List[str] = Field(default_factory=list, description="示例时间点（最多 10 条）")


class ContinuousZeroSpan(BaseModel):
    """连续零值区间"""

    start: str
    end: str
    length_hours: int


class QualityReport(BaseModel):
    """数据质量报告"""

    missing: MissingSummary
    anomalies: List[ValueAnomaly]
    continuous_zero_spans: List[ContinuousZeroSpan] = Field(default_factory=list)


class CleanedPoint(BaseModel):
    """清洗后的单点负荷"""

    timestamp: str
    load_kwh: float


class MetaInfo(BaseModel):
    """数据元信息"""

    source_interval_minutes: int
    total_records: int
    start: Optional[str]
    end: Optional[str]


class LoadAnalysisResponse(BaseModel):
    """负荷分析接口响应"""

    cleaned_points: List[CleanedPoint]
    report: QualityReport
    meta: MetaInfo


# =========================
# 储能收益与次数计算 - 核心模型
# =========================


class StorageProfit(BaseModel):
    """单一口径的储能收益结构"""

    revenue: float = Field(default=0.0, description="放电收入，单位：元")
    cost: float = Field(default=0.0, description="充电成本，单位：元")
    profit: float = Field(default=0.0, description="净收益，单位：元（revenue - cost）")
    discharge_energy_kwh: float = Field(default=0.0, description="放电电量，单位：kWh（电网侧）")
    charge_energy_kwh: float = Field(default=0.0, description="充电电量，单位：kWh（电网侧）")
    profit_per_kwh: float = Field(default=0.0, description="单位放电电量收益，单位：元/kWh")


class StorageProfitWithFormulas(BaseModel):
    """同时承载 physics / sample 双口径结果"""

    # 与 payload.storage.energy_formula 对应的主口径
    main: Optional[StorageProfit] = Field(default=None, description="主口径（当前 energy_formula）对应的收益")
    # 物理主口径 physics
    physics: Optional[StorageProfit] = Field(default=None, description="physics 口径收益（可选）")
    # 手算/示例口径 sample
    sample: Optional[StorageProfit] = Field(default=None, description="sample 口径收益（可选）")


class StorageCyclesDay(BaseModel):
    """按日统计的储能等效满充满放次数与收益"""

    date: str = Field(description="日期 YYYY-MM-DD")
    cycles: float = Field(default=0.0, description="当日等效满充满放次数")
    profit: Optional[StorageProfitWithFormulas] = Field(
        default=None,
        description="当日收益信息（可为空，表示未计算或无数据）",
    )


class StorageCyclesMonth(BaseModel):
    """按月统计的储能等效满充满放次数与收益"""

    year_month: str = Field(description="月份 YYYY-MM")
    cycles: float = Field(default=0.0, description="该月等效满充满放次数汇总")
    profit: Optional[StorageProfitWithFormulas] = Field(
        default=None,
        description="该月收益汇总信息（可为空）",
    )


class StorageCyclesYear(BaseModel):
    """按年统计的储能等效满充满放次数与收益"""

    year: int = Field(description="年份，0 表示未知或占位")
    cycles: float = Field(default=0.0, description="全年等效满充满放次数汇总")
    profit: Optional[StorageProfitWithFormulas] = Field(
        default=None,
        description="全年收益汇总信息（可为空）",
    )


class TipDischargePoint(BaseModel):
    """尖段典型点（可用于前端小图/标注）"""

    time: str = Field(description="HH:mm 当天的时间字符串")
    load_kw: float = Field(description="该时刻负荷，单位 kW")


class TipDischargeSummary(BaseModel):
    """尖段放电占比分析结果"""

    avg_tip_load_kw: float = Field(default=0.0, description="尖段平均负荷，单位 kW")
    tip_hours: float = Field(default=0.0, description="尖段总时长，单位小时")
    discharge_count: float = Field(default=0.0, description="尖段放电等效次数（可为非整数）")
    capacity_kwh: float | None = Field(default=None, description="当前假设的储能容量，单位 kWh")
    energy_need_kwh: float | None = Field(default=None, description="尖段能量需求，单位 kWh")
    ratio: float | None = Field(default=None, description="尖段放电满足程度 0-1")
    tip_points: list[TipDischargePoint] | None = Field(default=None, description="尖段典型点列表")
    note: str | None = Field(default=None, description="说明或备注")
    day_stats: list[dict] | None = Field(
        default=None,
        description="按日统计 [{date, avg_load_kw, tip_hours, energy_need_kwh, discharge_count, ratio}]",
    )
    month_stats: list[dict] | None = Field(
        default=None,
        description="1-12 月的平均满足度 [{month, ratio}]",
    )


class StorageQC(BaseModel):
    """储能计算质量指标"""

    notes: List[str] = Field(default_factory=list, description="提示信息及说明")
    missing_prices: int = Field(default=0, description="价格缺失的 15 分钟点数量")
    missing_points: int = Field(default=0, description="负荷数据缺失的 15 分钟点数量")
    merged_segments: int = Field(default=0, description="被合并的小窗口段数量")
    # 限值信息（变压器容量 / 月最大需量）
    limit_mode: Optional[str] = Field(
        default=None,
        description="限值模式：monthly_demand_max 或 transformer_capacity",
    )
    transformer_limit_kw: Optional[float] = Field(
        default=None,
        description="变压器容量折算的有功功率上限，单位 kW",
    )
    monthly_demand_max: List[dict] = Field(
        default_factory=list,
        description="每月最大需量 [{year_month, max_kw}]",
    )


class StorageWindowMonthSummary(BaseModel):
    """Window_debug 汇总的按月 C1/C2 + charge/discharge 统计"""

    year_month: str = Field(description="月份 YYYY-MM")
    # C1 + charge：第一次充电窗口在该月贡献的等效满充次数
    first_charge_cycles: float = Field(default=0.0, description="C1+charge 当月等效充电次数之和")
    # C1 + discharge：第一次放电窗口
    first_discharge_cycles: float = Field(default=0.0, description="C1+discharge 当月等效放电次数之和")
    # C2 + charge：第二次充电窗口
    second_charge_cycles: float = Field(default=0.0, description="C2+charge 当月等效充电次数之和")
    # C2 + discharge：第二次放电窗口
    second_discharge_cycles: float = Field(default=0.0, description="C2+discharge 当月等效放电次数之和")


class StorageCyclesResponse(BaseModel):
    """储能等效满充满放次数 + 质量指标 + 按月窗口汇总"""

    year: StorageCyclesYear
    months: List[StorageCyclesMonth] = Field(default_factory=list)
    days: List[StorageCyclesDay] = Field(default_factory=list)
    qc: StorageQC = Field(default_factory=StorageQC)
    excel_path: Optional[str] = Field(
        default=None,
        description="后端导出 Excel 报表路径（相对路径，可选）",
    )
    # 可选：基于 window_debug 汇总得到的按月 C1/C2 窗口统计
    window_month_summary: Optional[List[StorageWindowMonthSummary]] = Field(
        default=None,
        description="[{year_month, first_charge_cycles, first_discharge_cycles, second_charge_cycles, second_discharge_cycles}]",
    )
    # 可选：尖段放电占比分析
    tip_discharge_summary: Optional[TipDischargeSummary] = Field(
        default=None,
        description="尖段放电占比分析结果",
    )


class StorageCurvesPoint(BaseModel):
    """15 分钟负荷曲线上的单点"""

    timestamp: str = Field(description="时间戳，ISO8601 字符串")
    load_kw: float = Field(description="负荷，单位 kW")


class StorageCurvesSummary(BaseModel):
    """指定日期的关键负荷与费用指标"""

    max_demand_original_kw: float = Field(default=0.0, description="原始负荷曲线下的最大需量 kW")
    max_demand_new_kw: float = Field(default=0.0, description="引入储能后的最大需量 kW")
    max_demand_reduction_kw: float = Field(default=0.0, description="最大需量降低值 kW")
    max_demand_reduction_ratio: float = Field(default=0.0, description="最大需量降低比例 0-1")
    energy_by_tier_original: dict[str, float] = Field(
        default_factory=dict,
        description="各 TOU 分段下原始负荷电量 kWh",
    )
    energy_by_tier_new: dict[str, float] = Field(
        default_factory=dict,
        description="各 TOU 分段下引入储能后的电量 kWh",
    )
    bill_by_tier_original: dict[str, float] = Field(
        default_factory=dict,
        description="各 TOU 分段下原始电费 元",
    )
    bill_by_tier_new: dict[str, float] = Field(
        default_factory=dict,
        description="各 TOU 分段下引入储能后的电费 元",
    )
    profit_day_main: Optional[StorageProfit] = Field(
        default=None,
        description="该日主口径（energy_formula）下的收益汇总信息",
    )


class StorageCurvesResponse(BaseModel):
    """/api/storage/cycles/curves 接口返回的数据结构"""

    date: str = Field(description="日期 YYYY-MM-DD")
    points_original: List[StorageCurvesPoint] = Field(description="原始负荷曲线 15 分钟点")
    points_with_storage: List[StorageCurvesPoint] = Field(description="引入储能后的等效负荷曲线 15 分钟点")
    summary: StorageCurvesSummary = Field(description="选定日期的关键指标与收益汇总")

