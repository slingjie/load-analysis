from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class MissingHoursByMonth(BaseModel):
    """按月分类的缺失统计"""
    month: str = Field(description="月份，格式为 YYYY-MM")
    missing_days: int = Field(description="该月缺失的天数")
    missing_hours: int = Field(description="该月缺失的小时数")


class MissingSummary(BaseModel):
    """缺失信息汇总"""
    missing_days: List[str] = Field(default_factory=list, description="缺失日期列表")
    missing_hours_by_month: List[MissingHoursByMonth] = Field(
        default_factory=list, description="按月分类的缺失小时统计"
    )
    summary: dict = Field(
        default_factory=dict,
        description="汇总信息：total_missing_days、total_missing_hours"
    )


class ValueAnomaly(BaseModel):
    kind: Literal["null", "zero", "negative"]
    count: int
    ratio: float
    samples: List[str] = Field(default_factory=list, description="示例时间戳（最多10条）")


class ContinuousZeroSpan(BaseModel):
    start: str
    end: str
    length_hours: int


class QualityReport(BaseModel):
    missing: MissingSummary
    anomalies: List[ValueAnomaly]
    continuous_zero_spans: List[ContinuousZeroSpan] = Field(default_factory=list)


class CleanedPoint(BaseModel):
    timestamp: str
    load_kwh: float


class MetaInfo(BaseModel):
    source_interval_minutes: int
    total_records: int
    start: Optional[str]
    end: Optional[str]


class LoadAnalysisResponse(BaseModel):
    cleaned_points: List[CleanedPoint]
    report: QualityReport
    meta: MetaInfo


# =========================
# 储能次数测算 - 响应模型（MVP 占位）
# =========================

class StorageCyclesDay(BaseModel):
    """日度结果（占位版）"""
    date: str = Field(description="日期 YYYY-MM-DD")
    cycles: float = Field(default=0.0, description="当日充放次数（占位）")


class StorageCyclesMonth(BaseModel):
    """月度结果（占位版）"""
    year_month: str = Field(description="年月 YYYY-MM")
    cycles: float = Field(default=0.0, description="当月合计次数（占位）")


class StorageCyclesYear(BaseModel):
    """年度结果（占位版）"""
    year: int = Field(description="年份，如 2025；0 表示未知/占位")
    cycles: float = Field(default=0.0, description="年度累计次数（占位）")


class TipDischargePoint(BaseModel):
    """尖段采样点（可选，用于前端小图/表格）"""
    time: str = Field(description="HH:mm 或带日期的时间字符串")
    load_kw: float = Field(description="尖段负荷（kW）")


class TipDischargeSummary(BaseModel):
    """尖段放电占比汇总"""
    avg_tip_load_kw: float = Field(default=0.0, description="尖时段负荷均值（kW）")
    tip_hours: float = Field(default=0.0, description="尖时段总时长（小时）")
    discharge_count: float = Field(default=0.0, description="放电次数（支持非整数均值）")
    capacity_kwh: float | None = Field(default=None, description="储能容量（kWh）")
    energy_need_kwh: float | None = Field(default=None, description="尖段能量需求（kWh）")
    ratio: float | None = Field(default=None, description="尖放电占比（0-1）")
    tip_points: list[TipDischargePoint] | None = Field(default=None, description="尖段采样点列表")
    note: str | None = Field(default=None, description="说明或口径备注")
    day_stats: list[dict] | None = Field(default=None, description="日度尖占比 [{date, avg_load_kw, tip_hours, energy_need_kwh, discharge_count, ratio}]")
    month_stats: list[dict] | None = Field(default=None, description="1-12 月平均尖占比 [{month, ratio}]")


class StorageQC(BaseModel):
    """质量与提示指标（占位版）"""
    notes: List[str] = Field(default_factory=list, description="提示或说明")
    missing_prices: int = Field(default=0, description="缺价点位计数（占位）")
    missing_points: int = Field(default=0, description="缺失点位计数（占位）")
    merged_segments: int = Field(default=0, description="策略合并次数（占位）")
    # 计费上限信息（任务3）
    limit_mode: Optional[str] = Field(default=None, description="计费上限口径：monthly_demand_max 或 transformer_capacity")
    transformer_limit_kw: Optional[float] = Field(default=None, description="变压器口径的上限功率（kW）")
    monthly_demand_max: List[dict] = Field(default_factory=list, description="每月最大需量统计：[{year_month, max_kw}]")


class StorageWindowMonthSummary(BaseModel):
    """按 Window_debug 汇总的月度 C1/C2 + charge/discharge 结果。"""

    year_month: str = Field(description="年月 YYYY-MM")
    # C1 + charge：第一次充电窗口的满循环等效次数之和
    first_charge_cycles: float = Field(default=0.0, description="第一次充电(C1+charge) 当月等效满循环次数之和")
    # C1 + discharge：第一次放电窗口
    first_discharge_cycles: float = Field(default=0.0, description="第一次放电(C1+discharge) 当月等效满循环次数之和")
    # C2 + charge：第二次充电窗口
    second_charge_cycles: float = Field(default=0.0, description="第二次充电(C2+charge) 当月等效满循环次数之和")
    # C2 + discharge：第二次放电窗口
    second_discharge_cycles: float = Field(default=0.0, description="第二次放电(C2+discharge) 当月等效满循环次数之和")


class StorageCyclesResponse(BaseModel):
    """储能充放次数测算响应（MVP 占位）"""
    year: StorageCyclesYear
    months: List[StorageCyclesMonth] = Field(default_factory=list)
    days: List[StorageCyclesDay] = Field(default_factory=list)
    qc: StorageQC = Field(default_factory=StorageQC)
    excel_path: Optional[str] = Field(default=None, description="报表路径（占位）")
    # 可选：Window_debug 的月度汇总（供前端展示满充/满放率等统计）
    window_month_summary: Optional[List[StorageWindowMonthSummary]] = Field(
        default=None,
        description="[{year_month, first_charge_cycles, first_discharge_cycles, second_charge_cycles, second_discharge_cycles}]",
    )
    # 可选：尖段放电占比汇总
    tip_discharge_summary: Optional[TipDischargeSummary] = Field(
        default=None,
        description="尖段放电占比汇总",
    )
