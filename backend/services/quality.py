from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from .cleaner import CleanResult


def _format_iso(dt: pd.Timestamp) -> str:
    return dt.to_pydatetime().isoformat()


def _collect_anomalies(raw: pd.DataFrame, total: int) -> List[Dict]:
    results: List[Dict] = []
    conditions = {
        "null": raw["load"].isna(),
        "zero": (raw["load"].fillna(0) == 0) & (raw["load"].notna()),
        "negative": (raw["load"].fillna(0) < 0) & (raw["load"].notna()),
    }

    for kind, mask in conditions.items():
        count = int(mask.sum())
        ratio = round(count / total, 6) if total else 0.0
        timestamps = raw.loc[mask, "timestamp"].dropna().head(10)
        samples = [_format_iso(ts) for ts in timestamps]
        results.append({
            "kind": kind,
            "count": count,
            "ratio": ratio,
            "samples": samples,
        })

    return results


def _collect_missing(raw: pd.DataFrame) -> Dict:
    """对原始数据进行完整性分析，按月分类统计缺失情况。

    变更点：
    - 不再基于清洗结果，而是直接分析原始数据。
    - 构造365天期望窗口，统计缺失的天和小时。
    - 按月份分类返回缺失情况。
    """

    raw = raw.copy()
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], errors="coerce")
    raw = raw.dropna(subset=["timestamp"])

    if raw.empty:
        return {
            "missing_days": [],
            "missing_hours_by_month": [],
            "summary": {
                "total_missing_days": 0,
                "total_missing_hours": 0,
            }
        }

    # 提取所有存在的小时时间戳
    timestamps = raw["timestamp"].unique()
    timestamps = pd.to_datetime(timestamps)
    
    if len(timestamps) == 0:
        return {
            "missing_days": [],
            "missing_hours_by_month": [],
            "summary": {
                "total_missing_days": 0,
                "total_missing_hours": 0,
            }
        }

    # 构造期望的365天窗口（以最后一天为锚点）
    end_day = timestamps.max().normalize()
    expected_start_day = (end_day - pd.Timedelta(days=364)).normalize()
    expected_days = pd.date_range(expected_start_day, end_day, freq="D")

    # 存在数据的小时集合
    present_hours = set(timestamps.normalize())

    # 缺失整天：期望日期中完全不在 present_hours 的日期
    missing_days = [day.strftime("%Y-%m-%d") for day in expected_days if day not in present_hours]

    # 按月分类统计缺失小时
    missing_hours_by_month: List[Dict] = []
    total_missing_hours = 0

    for month_start in pd.date_range(expected_start_day, end_day, freq="MS"):
        month_end = (month_start + pd.DateOffset(months=1)) - pd.Timedelta(days=1)
        month_days = pd.date_range(month_start.normalize(), month_end.normalize(), freq="D")

        missing_count = sum(1 for day in month_days if day not in present_hours)
        month_str = month_start.strftime("%Y-%m")

        if missing_count > 0:
            missing_hours_by_month.append({
                "month": month_str,
                "missing_days": missing_count,
                "missing_hours": missing_count * 24,  # 整天缺失 = 24小时
            })
            total_missing_hours += missing_count * 24

    return {
        "missing_days": missing_days,
        "missing_hours_by_month": missing_hours_by_month,
        "summary": {
            "total_missing_days": len(missing_days),
            "total_missing_hours": total_missing_hours,
        }
    }


def _collect_zero_spans(result: CleanResult) -> List[Dict]:
    index = result.hourly_energy.index
    values = result.hourly_energy.to_numpy()
    present = (~result.missing_hours).to_numpy()

    zero_mask = np.isclose(values, 0.0, atol=1e-6) & present

    spans: List[Dict] = []
    start_ts = None
    length = 0

    for idx, is_zero in enumerate(zero_mask):
        if is_zero:
            if start_ts is None:
                start_ts = index[idx]
                length = 1
            else:
                length += 1
        else:
            if start_ts is not None:
                end_ts = index[idx - 1]
                spans.append({
                    "start": _format_iso(start_ts),
                    "end": _format_iso(end_ts),
                    "length_hours": length,
                })
                start_ts = None
                length = 0

    if start_ts is not None:
        end_ts = index[len(zero_mask) - 1]
        spans.append({
            "start": _format_iso(start_ts),
            "end": _format_iso(end_ts),
            "length_hours": length,
        })

    return spans


def build_quality_report(raw: pd.DataFrame) -> Tuple[Dict, Dict]:
    """对原始数据进行完整性分析，不涉及数据清洗。

    参数:
        raw: 原始数据框，包含 'timestamp' 和 'load' 列

    返回:
        (report_dict, meta_dict) 元组
    """
    total_records = len(raw)

    raw_copy = raw.copy()
    raw_copy["timestamp"] = pd.to_datetime(raw_copy["timestamp"], errors="coerce")
    raw_valid = raw_copy.dropna(subset=["timestamp"])

    if raw_valid.empty:
        return {
            "missing": {
                "missing_days": [],
                "missing_hours_by_month": [],
                "summary": {"total_missing_days": 0, "total_missing_hours": 0}
            },
            "anomalies": [],
            "continuous_zero_spans": [],
        }, {
            "source_interval_minutes": 0,
            "total_records": total_records,
            "start": None,
            "end": None,
        }

    timestamps = raw_valid["timestamp"]
    time_range_start = timestamps.min()
    time_range_end = timestamps.max()
    
    # 计算负荷统计数据
    raw_copy["load"] = pd.to_numeric(raw_copy["load"], errors="coerce")
    load_valid = raw_copy["load"].dropna()
    
    if len(load_valid) > 0:
        avg_load_kw = float(load_valid.mean())
        max_load_kw = float(load_valid.max())
        min_load_kw = float(load_valid.min())
    else:
        avg_load_kw = 0.0
        max_load_kw = 0.0
        min_load_kw = 0.0

    report = {
        "missing": _collect_missing(raw_copy),
        "anomalies": _collect_anomalies(raw_copy, total_records),
        "continuous_zero_spans": [],  # 不再分析连续零段
    }

    meta = {
        "source_interval_minutes": 0,  # 原始数据不确定采样间隔，设为0
        "total_records": total_records,
        "start": _format_iso(time_range_start),
        "end": _format_iso(time_range_end),
        "avg_load_kw": round(avg_load_kw, 2),
        "max_load_kw": round(max_load_kw, 2),
        "min_load_kw": round(min_load_kw, 2),
    }

    return report, meta
