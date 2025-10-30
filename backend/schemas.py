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
