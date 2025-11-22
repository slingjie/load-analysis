from __future__ import annotations

"""
储能充放次数测算 - 基础服务（MVP 占位）

职责：
- 解析上传负荷文件，标准化为 `timestamp, load_kw`
- 基础校验与 15 分钟重采样（不做插值策略，保持保守）
"""

from datetime import timedelta, datetime
import logging
from typing import Tuple, Optional, Dict, List, Any

import pandas as pd
import os
from pathlib import Path

from . import loader

TZ_NAME = os.environ.get("APP_LOCAL_TZ", "Asia/Shanghai")


logger = logging.getLogger("load-analysis")

# 全局 DOD 兜底值，避免遗留引用导致 NameError；实际计算使用各函数内部的 effective_dod
dod: float = 1.0


class CyclesError(ValueError):
    """储能测算前置校验错误。"""


def parse_load_series(file_bytes: bytes) -> pd.DataFrame:
    """解析负荷文件为 `timestamp, load_kw`，并重采样至 15 分钟。

    规则：
    - 支持 Excel/CSV（委托 loader.load_dataframe）
    - 列名标准化为 timestamp(datetime64[ns]), load_kw(float)
    - 时间索引去重与排序
    - 按 15 分钟重采样为守约（默认取均值，不做插值）；
    - 返回 DataFrame，索引为 DatetimeIndex，含列 `load_kw`
    """
    raw = loader.load_dataframe(file_bytes)

    # 期待列存在
    if "timestamp" not in raw.columns:
        raise CyclesError("未找到时间列（timestamp）。")
    load_col = "load_kw" if "load_kw" in raw.columns else ("load" if "load" in raw.columns else None)
    if load_col is None:
        raise CyclesError("未找到负荷列（load 或 load_kw）。")

    df = raw[["timestamp", load_col]].copy()
    # 统一将带时区的时间戳转换为“本地朴素时间”，与排程的本地日界一致
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    try:
        if getattr(ts.dt, "tz", None) is not None:
            ts = ts.dt.tz_convert(TZ_NAME).dt.tz_localize(None)
    except Exception:
        try:
            ts = ts.dt.tz_localize(None)
        except Exception:
            pass
    df["timestamp"] = ts
    df = df.dropna(subset=["timestamp"]).reset_index(drop=True)
    df.rename(columns={load_col: "load_kw"}, inplace=True)
    df["load_kw"] = pd.to_numeric(df["load_kw"], errors="coerce")

    # 设为索引并按时间排序，去重（保留首次）
    df = df.set_index("timestamp").sort_index()
    df = df[~df.index.duplicated(keep="first")]

    # 重采样至 15 分钟网格（取均值），不插值
    resampled = df.resample("15min").mean()

    # 返回标准化结构
    return resampled[["load_kw"]]


def parse_points_series(points: List[Dict[str, Any]]) -> pd.DataFrame:
    """将前端已分析的点数组（timestamp, load_kwh）转换为 15 分钟序列。

    参数:
      points: [{"timestamp": ISO8601字符串, "load_kwh": 数值}, ...]
    返回:
      索引为 DatetimeIndex 的 DataFrame，列为 load_kw，重采样至 15min 平均。
    """
    if not points:
        return pd.DataFrame(index=pd.to_datetime([]), data={"load_kw": []})
    df = pd.DataFrame(points)
    # 兼容键名 load 与 load_kwh
    if "load_kwh" not in df.columns and "load" in df.columns:
        df = df.rename(columns={"load": "load_kwh"})
    # 统一将带时区的时间戳转换为“本地朴素时间”，与排程的本地日界一致
    ts = pd.to_datetime(df["timestamp"], errors="coerce")
    try:
        if getattr(ts.dt, "tz", None) is not None:
            ts = ts.dt.tz_convert(TZ_NAME).dt.tz_localize(None)
    except Exception:
        try:
            ts = ts.dt.tz_localize(None)
        except Exception:
            pass
    df["timestamp"] = ts
    df["load_kwh"] = pd.to_numeric(df["load_kwh"], errors="coerce")
    df = df.dropna(subset=["timestamp"]).sort_values("timestamp").set_index("timestamp")
    df = df[~df.index.duplicated(keep="first")]
    resampled = df.resample("15min").mean()
    return resampled.rename(columns={"load_kwh": "load_kw"})[["load_kw"]]


def compute_limit_info(
    series_15m: pd.DataFrame,
    metering_mode: str,
    transformer_capacity_kva: Optional[float] = None,
    transformer_power_factor: Optional[float] = None,
) -> dict:
    """计算计费上限信息。

    - monthly_demand_max：按月统计 15 分钟负荷的最大值（kW）。
    - transformer_capacity：基于 `kva * power_factor` 计算上限（kW）。

    返回：
    {
      'limit_mode': 'monthly_demand_max' | 'transformer_capacity',
      'monthly_demand_max': List[{'year_month': 'YYYY-MM', 'max_kw': float}],
      'transformer_limit_kw': float | None,
      'notes': List[str]
    }
    """
    mode = (metering_mode or "monthly_demand_max").strip()
    mode = mode if mode in {"monthly_demand_max", "transformer_capacity"} else "monthly_demand_max"

    notes: List[str] = []
    monthly: List[dict] = []
    transformer_limit: Optional[float] = None

    if series_15m.empty or "load_kw" not in series_15m.columns:
        notes.append("负荷数据为空或缺少 load_kw 列，无法统计最大需量。")
    else:
        # 确保索引为 DatetimeIndex
        s = series_15m.copy()
        if not isinstance(s.index, pd.DatetimeIndex):
            s.index = pd.to_datetime(s.index, errors="coerce")
        s = s.dropna(subset=["load_kw"])  # 去除 NaN

        # 按月统计 15 分钟点的最大值（kW）
        if not s.empty:
            month_key = s.index.strftime("%Y-%m")
            grp = s.assign(_ym=month_key).groupby("_ym")["load_kw"].max()
            monthly = [
                {"year_month": ym, "max_kw": float(val) if pd.notna(val) else 0.0}
                for ym, val in grp.items()
            ]

    if mode == "transformer_capacity":
        if transformer_capacity_kva is None or transformer_power_factor is None:
            notes.append("变压器口径缺少参数：kVA 或功率因数。已回退为 monthly_demand_max。")
            mode = "monthly_demand_max"
        else:
            try:
                transformer_limit = float(transformer_capacity_kva) * float(transformer_power_factor)
            except Exception:  # pragma: no cover
                transformer_limit = None
                notes.append("变压器口径参数无法计算上限，已回退为 monthly_demand_max。")
                mode = "monthly_demand_max"

    return {
        "limit_mode": mode,
        "monthly_demand_max": monthly,
        "transformer_limit_kw": transformer_limit,
        "notes": notes,
    }


# -------------------------
# 策略 → 日度运行逻辑与连段（占位合并规则）
# -------------------------

def _date_range(start: datetime, end: datetime) -> List[datetime]:
    cur = datetime(start.year, start.month, start.day)
    days: List[datetime] = []
    while cur.date() <= end.date():
        days.append(cur)
        cur += timedelta(days=1)
    return days


def _match_rule(d: datetime, date_rules: List[dict]) -> Optional[dict]:
    for r in date_rules or []:
        try:
            start = datetime.fromisoformat(str(r.get("startDate")) + "T00:00:00")
            end = datetime.fromisoformat(str(r.get("endDate")) + "T23:59:59")
        except Exception:
            continue
        if start <= d <= end:
            return r
    return None


def _extract_hour_ops(cell: dict) -> str:
    op = (cell or {}).get("op", "待机")
    if op not in ("充", "放", "待机"):
        return "待机"
    return op


def build_daily_ops(
    series_15m: pd.DataFrame,
    monthly_schedule: List[List[dict]] | None,
    date_rules: List[dict] | None,
) -> Dict[str, List[str]]:
    """构造每一天 24 小时的运行逻辑（仅使用 op: 充/放/待机）。

    优先级：命中日期规则则使用规则的 24 小时表，否则采用月度 schedule 的相应月份。
    返回：{ 'YYYY-MM-DD': ['待机'|'充'|'放'] * 24 }
    """
    if series_15m.empty:
        return {}
    if not isinstance(series_15m.index, pd.DatetimeIndex):
        raise CyclesError("series_15m 索引必须是 DatetimeIndex")

    start = series_15m.index.min().to_pydatetime()
    end = series_15m.index.max().to_pydatetime()
    days = _date_range(start, end)

    daily: Dict[str, List[str]] = {}
    for d in days:
        key = d.strftime("%Y-%m-%d")
        rule = _match_rule(d, date_rules or [])
        if rule and isinstance(rule.get("schedule"), list) and len(rule["schedule"]) >= 24:
            ops = [
                _extract_hour_ops(rule["schedule"][h])
                for h in range(24)
            ]
        else:
            m_idx = d.month - 1
            row = (monthly_schedule[m_idx] if (monthly_schedule and 0 <= m_idx < len(monthly_schedule)) else None) or []
            ops = [
                _extract_hour_ops(row[h] if h < len(row) else None)
                for h in range(24)
            ]
        daily[key] = ops
    return daily


def _merge_head_tail_runs(runs: List[tuple[str, List[int]]], enabled: bool = False) -> List[tuple[str, List[int]]]:
    """可选地合并首尾同类（充/放）为一段；默认关闭以避免跨日误并造成窗口均值偏差。"""
    if not enabled:
        return runs
    if not runs:
        return runs
    if len(runs) == 1:
        return runs
    first_k, first_hours = runs[0]
    last_k, last_hours = runs[-1]
    if first_k == last_k:
        merged = (first_k, sorted(set(last_hours + first_hours)))
        return [merged] + runs[1:-1]
    return runs


def _hour_runs_from_ops(ops: List[str], wrap_across_midnight: bool = False) -> List[tuple[str, List[int]]]:
    """从 24 小时逻辑序列提取连续连段（忽略待机）。"""
    runs: List[tuple[str, List[int]]]= []
    cur_kind: Optional[str] = None
    cur_hours: List[int] = []
    for h in range(24):
        k = ops[h]
        if k not in ("充", "放"):
            if cur_kind is not None:
                runs.append((cur_kind, cur_hours))
                cur_kind, cur_hours = None, []
            continue
        if cur_kind != k:
            if cur_kind is not None:
                runs.append((cur_kind, cur_hours))
            cur_kind = k
            cur_hours = [h]
        else:
            cur_hours.append(h)
    if cur_kind is not None:
        runs.append((cur_kind, cur_hours))
    # 首尾同类合并（可选）
    runs = _merge_head_tail_runs(runs, enabled=wrap_across_midnight)
    return runs


def build_daily_cycles_masks(
    daily_ops: Dict[str, List[str]],
    merge_threshold_minutes: int = 30,
    wrap_across_midnight: bool = False,
) -> tuple[Dict[str, dict], int, List[dict]]:
    """基于日度逻辑构造 c1/c2 充/放掩码（按小时索引集合）。

    - 仅按小时粒度；后续窗口平均将映射到 15 分钟网格
    - 合并阈值：当连段总时长（小时*60）< 阈值时丢弃该段（视为噪声）
    - 超过两次的连段：第 3 段及以后并入 c2 的同类集合，并累计 merged 计数
    返回：(masks_by_date, merged_count)
      masks_by_date: {
        'YYYY-MM-DD': {
            'c1': { 'charge_hours': [...], 'discharge_hours': [...] },
            'c2': { 'charge_hours': [...], 'discharge_hours': [...] },
        }
      }
    """
    masks: Dict[str, dict] = {}
    merged_total = 0
    runs_debug: List[dict] = []
    for key, ops in daily_ops.items():
        runs_pre = _hour_runs_from_ops(ops, wrap_across_midnight=wrap_across_midnight)
        # 过滤小片段（按分钟阈值）
        runs_flt = []
        for i, (k, hrs) in enumerate(runs_pre):
            length_min = len(hrs) * 60
            filtered = length_min < (merge_threshold_minutes or 0)
            runs_debug.append({
                "date": key,
                "seq": i,
                "kind": k,
                "start_hour": min(hrs) if hrs else None,
                "end_hour": (max(hrs) + 1) if hrs else None,  # 半开区间
                "length_hours": len(hrs),
                "filtered_by_threshold": bool(filtered),
                "merged_to": None,
                "wrap_across_midnight": bool(wrap_across_midnight),
            })
            if not filtered:
                runs_flt.append((k, hrs))

        c1 = {"charge_hours": set(), "discharge_hours": set()}
        c2 = {"charge_hours": set(), "discharge_hours": set()}
        for i, (k, hrs) in enumerate(runs_flt):
            target = c1 if i < 2 else c2
            if i >= 4:
                merged_total += 1
            if k == "充":
                target["charge_hours"].update(hrs)
            elif k == "放":
                target["discharge_hours"].update(hrs)
            # 标注合并目标
            for dbg in runs_debug:
                if dbg["date"] == key and dbg["seq"] == i and not dbg["filtered_by_threshold"]:
                    dbg["merged_to"] = "c1" if i < 2 else "c2"
        masks[key] = {
            "c1": {"charge_hours": sorted(c1["charge_hours"]), "discharge_hours": sorted(c1["discharge_hours"])},
            "c2": {"charge_hours": sorted(c2["charge_hours"]), "discharge_hours": sorted(c2["discharge_hours"])},
        }
    return masks, merged_total, runs_debug


def count_missing_prices(monthly_prices: List[dict] | None) -> tuple[int, List[int]]:
    """统计月度 TOU 价格缺失项数量。

    参数：monthly_prices: 长度应为 12 的数组，每项为 { tierId: price | null }
    返回：(缺失数量, 异常月份索引列表)
    """
    if not monthly_prices:
        return 0, []
    missing = 0
    bad_months: List[int] = []
    for i, mp in enumerate(monthly_prices):
        if not isinstance(mp, dict):
            bad_months.append(i)
            continue
        for tier in ("尖", "峰", "平", "谷", "深"):
            v = mp.get(tier)
            if v is None:
                missing += 1
            else:
                try:
                    float(v)
                except Exception:
                    missing += 1
    return missing, bad_months


def build_price_series(
    series_15m: pd.DataFrame,
    monthly_schedule: List[List[dict]] | None,
    date_rules: List[dict] | None,
    monthly_prices: List[dict] | None,
) -> tuple[pd.DataFrame, int]:
    """将 TOU 档位映射到 15 分钟点位并附上价格。

    返回：(df, missing_points)
    - df: 与 series_15m 同索引，列 `tier` 和 `price`
    - missing_points: price 为 None/NaN 的 15 分钟点位计数
    """
    if series_15m.empty:
        return pd.DataFrame(index=series_15m.index, data={"tier": [], "price": []}), 0
    if not isinstance(series_15m.index, pd.DatetimeIndex):
        s = series_15m.copy()
        s.index = pd.to_datetime(s.index, errors="coerce")
        s = s.dropna()
    else:
        s = series_15m

    # 预构造每日 24 小时档位
    # 复用 daily_ops，但保留 tou 字段
    def _extract_hour_tou(cell: dict) -> str:
        tou = (cell or {}).get("tou", "平")
        return tou if tou in ("尖", "峰", "平", "谷", "深") else "平"

    start = s.index.min().to_pydatetime()
    end = s.index.max().to_pydatetime()
    days = _date_range(start, end)
    daily_tou: Dict[str, List[str]] = {}
    for d in days:
        key = d.strftime("%Y-%m-%d")
        rule = _match_rule(d, date_rules or [])
        if rule and isinstance(rule.get("schedule"), list) and len(rule["schedule"]) >= 24:
            tiers = [
                _extract_hour_tou(rule["schedule"][h])
                for h in range(24)
            ]
        else:
            m_idx = d.month - 1
            row = (monthly_schedule[m_idx] if (monthly_schedule and 0 <= m_idx < len(monthly_schedule)) else None) or []
            tiers = [
                _extract_hour_tou(row[h] if h < len(row) else None)
                for h in range(24)
            ]
        daily_tou[key] = tiers

    # 月度价格映射
    def _price_for(month_idx: int, tier: str) -> Optional[float]:
        if not monthly_prices or not (0 <= month_idx < len(monthly_prices)):
            return None
        pm = monthly_prices[month_idx]
        try:
            v = pm.get(tier)
            return float(v) if v is not None else None
        except Exception:
            return None

    records: List[dict] = []
    missing_points = 0
    for ts in s.index:
        day_key = ts.strftime("%Y-%m-%d")
        hour = ts.hour
        tiers = daily_tou.get(day_key)
        tier = tiers[hour] if tiers and 0 <= hour < len(tiers) else "平"
        month_idx = ts.month - 1
        price = _price_for(month_idx, tier)
        if price is None or not pd.notna(price):
            missing_points += 1
        records.append({"timestamp": ts, "tier": tier, "price": price})

    df = pd.DataFrame.from_records(records).set_index("timestamp").sort_index()
    return df, int(missing_points)


# -------------------------
# 尖段放电占比（基于 TOU=尖 且 op=放）
# -------------------------

def compute_tip_discharge_summary(
    series_15m: pd.DataFrame,
    price_series: Optional[pd.DataFrame],
    daily_ops: Dict[str, List[str]],
    daily_masks: Dict[str, dict] | None,
    storage_cfg: Dict,
) -> Optional[dict]:
    """计算尖段放电占比：仅统计 TOU=尖 且运行逻辑 op=放 的 15min 点。

    公式：占比 = min(1, 尖段能量需求 / (容量 × 放电次数))
      - 能量需求 = 尖段平均负荷 × 尖段时长（小时）
      - 放电次数：对有尖段的日期，统计 c1/c2 放电窗口中与尖小时有交集的窗口数，求平均
    """
    if series_15m is None or price_series is None:
        return None
    if series_15m.empty or price_series.empty:
        logger.debug("[tip_summary] empty series or price_series")
        return None
    s = series_15m.copy()
    p = price_series.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index, errors="coerce")
    if not isinstance(p.index, pd.DatetimeIndex):
        p.index = pd.to_datetime(p.index, errors="coerce")
    s = s.dropna(subset=["load_kw"]).sort_index()
    p = p.dropna(subset=["tier"]).sort_index()
    if s.empty or p.empty:
        return None

    df = s.join(p[["tier"]], how="inner")

    def _op_for_ts(ts: pd.Timestamp) -> Optional[str]:
        day_key = ts.strftime("%Y-%m-%d")
        ops = daily_ops.get(day_key)
        if not ops:
            return None
        h = ts.hour
        return ops[h] if 0 <= h < len(ops) else None

    df["op"] = [ _op_for_ts(ts) for ts in df.index ]
    df_tip = df[(df["tier"] == "尖") & (df["op"] == "放")]
    if df_tip.empty:
        logger.info("[tip_summary] no尖放点: total_points=%s tip_points=0", len(df))
        cap = float(storage_cfg.get("capacity_kwh", 0) or 0)
        return {
          "avg_tip_load_kw": 0.0,
          "tip_hours": 0.0,
          "energy_need_kwh": 0.0,
          "discharge_count": 0.0,
          "capacity_kwh": cap,
          "ratio": 0.0,
          "tip_points": [],
          "note": "无 TOU=尖 且运行逻辑=放 的 15 分钟点，尖放电占比记为 0",
        }

    day_keys = sorted(set(df_tip.index.date))
    cap = float(storage_cfg.get("capacity_kwh", 0) or 0)

    day_stats: List[dict] = []
    for dk in day_keys:
        day_str = pd.Timestamp(dk).strftime("%Y-%m-%d")
        day_sub = df_tip.loc[df_tip.index.date == dk]
        avg_day = float(day_sub["load_kw"].mean()) if not day_sub.empty else 0.0
        tip_hours_day = float(len(day_sub) * 0.25)
        energy_day = avg_day * tip_hours_day

        tip_hour_set = set(day_sub.index.hour)
        masks = (daily_masks or {}).get(day_str, {})
        cnt = 0
        for win in ("c1", "c2"):
            hours = masks.get(win, {}).get("discharge_hours", []) or []
            if set(int(h) for h in hours) & tip_hour_set:
                cnt += 1
        discharge_count_day = float(cnt)
        if discharge_count_day <= 0 or cap <= 0 or tip_hours_day <= 0:
            ratio_day = 0.0
        else:
            ratio_day = min(1.0, energy_day / (cap * discharge_count_day))

        day_stats.append({
            "date": day_str,
            "avg_load_kw": avg_day,
            "tip_hours": tip_hours_day,
            "energy_need_kwh": energy_day,
            "discharge_count": discharge_count_day,
            "ratio": ratio_day,
        })

    # 聚合为均值口径，防止跨天累加导致占比 100%
    if not day_stats:
        avg_tip_load = 0.0
        tip_hours = 0.0
        energy_need = 0.0
        discharge_count = 0.0
        ratio = 0.0
        month_stats: List[dict] = []
    else:
        avg_tip_load = float(sum(d["avg_load_kw"] for d in day_stats) / len(day_stats))
        tip_hours = float(sum(d["tip_hours"] for d in day_stats) / len(day_stats))
        energy_need = float(sum(d["energy_need_kwh"] for d in day_stats) / len(day_stats))
        discharge_count = float(sum(d["discharge_count"] for d in day_stats) / len(day_stats))
        ratio = float(sum(d["ratio"] for d in day_stats) / len(day_stats))
        month_bucket: Dict[int, List[float]] = {}
        for d in day_stats:
            try:
                m = int(str(d.get("date", ""))[5:7])
            except Exception:
                continue
            if 1 <= m <= 12:
                month_bucket.setdefault(m, []).append(float(d["ratio"]))
        month_stats = []
        for m in range(1, 13):
            arr = month_bucket.get(m, [])
            month_stats.append({"month": m, "ratio": float(sum(arr) / len(arr)) if arr else 0.0})

    # 尖段点位列表（仅时间与负荷，避免返回过大文本）
    # 裁剪点位，避免体积过大
    tip_points = [
        {"time": ts.strftime("%Y-%m-%d %H:%M"), "load_kw": float(val) if pd.notna(val) else 0.0}
        for ts, val in df_tip["load_kw"].items()
    ][:200]

    note = (
        f"基于 TOU=尖 且运行逻辑=放 的 15 分钟点，共 {len(df_tip)} 点，{len(day_keys)} 天；"
        f"按“逐日平均”口径汇总，防止跨天累加导致占比拉满。"
    )
    logger.info(
        "[tip_summary] points=%s days=%s avg=%.3f hours=%.2f energy=%.3f dis_cnt=%.3f cap=%.3f ratio=%s",
        len(df_tip),
        len(day_keys),
        avg_tip_load,
        tip_hours,
        energy_need,
        discharge_count,
        cap,
        ratio,
    )

    return {
        "avg_tip_load_kw": avg_tip_load,
        "tip_hours": tip_hours,
        "energy_need_kwh": energy_need,
        "discharge_count": discharge_count,
        "capacity_kwh": cap,
        "ratio": ratio,
        "tip_points": tip_points,
        "note": note,
        "day_stats": day_stats,
        "month_stats": month_stats,
    }


# -------------------------
# window_avg 计算（physics 默认）
# -------------------------

def _build_hourly_average(series_15m: pd.DataFrame) -> Dict[str, List[float]]:
    """从 15 分钟序列构造每天 24 小时的平均负荷（kW）。

    返回：{ 'YYYY-MM-DD': [avg_kW_h0, ..., avg_kW_h23] }
    """
    if series_15m.empty:
        return {}
    s = series_15m.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index, errors="coerce")
    s = s.dropna(subset=["load_kw"]).sort_index()
    # 每小时平均
    hourly = s["load_kw"].resample("1H").mean()
    by_day: Dict[str, List[float]] = {}
    # 遍历小时序列并按天收集
    for ts, val in hourly.items():
        key = ts.strftime("%Y-%m-%d")
        if key not in by_day:
            by_day[key] = [0.0] * 24
        by_day[key][ts.hour] = float(val) if pd.notna(val) else 0.0
    return by_day


def _month_key_of_date_str(date_str: str) -> str:
    return date_str[:7]


def compute_window_avg_days(
    series_15m: pd.DataFrame,
    daily_masks: Dict[str, dict],
    storage_cfg: Dict,
    limit_info: Dict,
    energy_formula: str = "physics",
) -> List[dict]:
    """基于“窗口平均 × 时长”的验收口径计算（对齐参考程序）。

    要点：
    - 以 15 分钟序列为基准，按掩码窗口选择点集，窗口平均负荷 × 窗口时长（小时）得到 base（电池侧能量基数）。
    - 许可功率：
      - 充：allow_ch = max(limit_kw - reserve_charge_kw - avg_load_window, 0)
      - 放：allow_dis = max(avg_load_window - reserve_discharge_kw, 0)
    - 窗口平均法不受 Pmax（c_rate*capacity）限制。
    - 电网侧折算（physics）：
      - E_in_grid = base_ch_kWh * DOD / η
      - E_out_grid = base_dis_kWh * DOD * η
    - 满充/放率裁剪至 1；当日次数为两次循环的 min(...) 之和。
    """
    cap = float(storage_cfg.get("capacity_kwh", 0) or 0)
    c_rate = float(storage_cfg.get("c_rate", 0) or 0)
    eta = float(storage_cfg.get("single_side_efficiency", 0.9) or 0.9)
    # 保持原变量名存在以兼容旧引用，但实际使用 effective_dod
    dod = effective_dod
    reserve_ch = float(storage_cfg.get("reserve_charge_kw", 0) or 0)
    reserve_dis = float(storage_cfg.get("reserve_discharge_kw", 0) or 0)

    # 月份→最大需量映射
    month_max_map: Dict[str, float] = {it.get("year_month"): float(it.get("max_kw", 0) or 0) for it in (limit_info.get("monthly_demand_max") or [])}
    transformer_limit_kw = limit_info.get("transformer_limit_kw")
    mode = limit_info.get("limit_mode", "monthly_demand_max")

    if series_15m.empty:
        return []
    s = series_15m.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index, errors="coerce")
    s = s.dropna(subset=["load_kw"]).sort_index()
    days: List[dict] = []
    for date_str, masks in daily_masks.items():
        ym = _month_key_of_date_str(date_str)
        if mode == "transformer_capacity" and transformer_limit_kw:
            limit_kw = float(transformer_limit_kw)
        else:
            limit_kw = float(month_max_map.get(ym, 0.0))

        # 无上限或容量→无法计算 cycles
        if limit_kw <= 0 or cap <= 0:
            days.append({"date": date_str, "cycles": 0.0})
            continue

        # 当天的 15 分钟序列
        day_start = pd.to_datetime(date_str)
        day_end = day_start + pd.Timedelta(days=1)
        day_sub = s.loc[(s.index >= day_start) & (s.index < day_end)]

        c1 = masks.get("c1", {})
        c2 = masks.get("c2", {})

        def _window_energy(hour_list: List[int], is_charge: bool) -> float:
            if not hour_list:
                return 0.0
            hour_set = set(int(h) for h in hour_list)
            # 选中该窗口的 15 分钟点
            sel = day_sub.loc[day_sub.index.hour.map(lambda h: h in hour_set)]
            if sel.empty:
                return 0.0
            avg_load = float(sel["load_kw"].mean())
            hours = float(len(sel)) * 0.25
            if is_charge:
                allow = limit_kw - reserve_ch - avg_load
            else:
                allow = avg_load - reserve_dis
            allow = max(0.0, allow)
            return allow * hours

        def _cycle_contrib(cmask: dict) -> float:
            e_in_base = _window_energy(cmask.get("charge_hours", []), True)
            e_out_base = _window_energy(cmask.get("discharge_hours", []), False)

            if energy_formula == "physics":
                E_in_grid = e_in_base * dod / max(eta, 1e-9)
                E_out_grid = e_out_base * dod * eta
            else:
                E_in_grid = e_in_base / max(dod, 1e-9) * eta
                E_out_grid = e_out_base / max(dod, 1e-9) / max(eta, 1e-9)

            fc = min(E_in_grid / cap if cap > 0 else 0.0, 1.0)
            fd = min(E_out_grid / cap if cap > 0 else 0.0, 1.0)
            return min(fc, fd)

        cycles_day = _cycle_contrib(c1) + _cycle_contrib(c2)
        days.append({"date": date_str, "cycles": float(cycles_day)})

    # 按日期排序
    days.sort(key=lambda x: x["date"])
    return days


def compute_window_avg_days_with_debug(
    series_15m: pd.DataFrame,
    daily_masks: Dict[str, dict],
    storage_cfg: Dict,
    limit_info: Dict,
    energy_formula: str = "physics",
) -> tuple[List[dict], List[dict]]:
    """同 compute_window_avg_days，但额外返回“窗口汇总明细”行，用于 Excel 调试。

    返回：(
      days: [{date, cycles}],
      window_debug: [
        {date, window, kind, hour_list, points, avg_load_kw, hours, limit_kw, allow_kw, base_kwh, e_grid_kwh, full_ratio}
      ]
    )
    """

    # 复用已对齐窗口平均法的实现，增加调试行收集
    cap = float(storage_cfg.get("capacity_kwh", 0) or 0)
    eta = float(storage_cfg.get("single_side_efficiency", 0.9) or 0.9)
    dod = float(storage_cfg.get("depth_of_discharge", 1.0) or 1.0)
    reserve_ch = float(storage_cfg.get("reserve_charge_kw", 0) or 0)
    reserve_dis = float(storage_cfg.get("reserve_discharge_kw", 0) or 0)

    # 月份→最大需量映射
    month_max_map: Dict[str, float] = {it.get("year_month"): float(it.get("max_kw", 0) or 0) for it in (limit_info.get("monthly_demand_max") or [])}
    transformer_limit_kw = limit_info.get("transformer_limit_kw")
    mode = limit_info.get("limit_mode", "monthly_demand_max")

    if series_15m.empty:
        return [], []
    s = series_15m.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index, errors="coerce")
    s = s.dropna(subset=["load_kw"]).sort_index()

    def _day_limit_kw(ym: str) -> float:
        if mode == "transformer_capacity" and transformer_limit_kw:
            return float(transformer_limit_kw)
        return float(month_max_map.get(ym, 0.0))

    def _window_metrics(day_sub: pd.DataFrame, hour_list: List[int], limit_kw: float, is_charge: bool) -> tuple[dict, float]:
        hour_set = set(int(h) for h in (hour_list or []))
        sel = day_sub.loc[day_sub.index.hour.map(lambda h: h in hour_set)]
        points = int(len(sel))
        if points == 0:
            return {
                "points": 0,
                "avg_load_kw": 0.0,
                "hours": 0.0,
                "allow_kw": 0.0,
                "base_kwh": 0.0,
                "e_grid_kwh": 0.0,
                "full_ratio": 0.0,
                # 对照：逐点积分（step_15）
                "base_kwh_step15": 0.0,
                "e_grid_kwh_step15": 0.0,
                "full_ratio_step15": 0.0,
            }, 0.0
        avg_load = float(sel["load_kw"].mean())
        hours = float(points) * 0.25
        allow = max(0.0, (limit_kw - reserve_ch - avg_load) if is_charge else (avg_load - reserve_dis))
        base_kwh = allow * hours
        # 两套口径同时计算（用于对拍）：physics 与 sample
        e_grid_physics = (base_kwh * dod / max(eta, 1e-9)) if is_charge else (base_kwh * dod * eta)
        e_grid_sample  = (base_kwh / max(dod, 1e-9) * eta) if is_charge else (base_kwh / max(dod, 1e-9) / max(eta, 1e-9))
        full_ratio_physics = min(e_grid_physics / cap if cap > 0 else 0.0, 1.0)
        full_ratio_sample  = min(e_grid_sample  / cap if cap > 0 else 0.0, 1.0)

        # 维持原有字段（随 energy_formula 切换），但同时返回两套对拍列
        if energy_formula == "physics":
            e_grid = e_grid_physics
            full_ratio = full_ratio_physics
        else:
            e_grid = e_grid_sample
            full_ratio = full_ratio_sample

        # 附加对照：逐 15 分钟积分（step_15，不改变主口径，仅用于报表对拍）
        if is_charge:
            allow_series = (limit_kw - reserve_ch - sel["load_kw"]).clip(lower=0.0)
            base_step15 = float((allow_series * 0.25).sum())
            e_grid_physics_step15 = base_step15 * (dod / max(eta, 1e-9))
            e_grid_sample_step15  = base_step15 * (eta / max(dod, 1e-9))
        else:
            allow_series = (sel["load_kw"] - reserve_dis).clip(lower=0.0)
            base_step15 = float((allow_series * 0.25).sum())
            e_grid_physics_step15 = base_step15 * (dod * eta)
            e_grid_sample_step15  = base_step15 * (1.0 / max(dod * eta, 1e-9))
        full_ratio_physics_step15 = min(e_grid_physics_step15 / cap if cap > 0 else 0.0, 1.0)
        full_ratio_sample_step15  = min(e_grid_sample_step15  / cap if cap > 0 else 0.0, 1.0)

        return {
            "points": points,
            "avg_load_kw": avg_load,
            "hours": hours,
            "allow_kw": allow,
            "base_kwh": base_kwh,
            # 主口径当前值（随 energy_formula 切换）
            "e_grid_kwh": e_grid,
            "full_ratio": full_ratio,
            # physics 与 sample 两套对拍（窗口平均）
            "e_grid_kwh_physics": e_grid_physics,
            "full_ratio_physics": full_ratio_physics,
            "e_grid_kwh_sample": e_grid_sample,
            "full_ratio_sample": full_ratio_sample,
            # 逐点积分对照（step_15）
            "base_kwh_step15": base_step15,
            "e_grid_kwh_physics_step15": e_grid_physics_step15,
            "full_ratio_physics_step15": full_ratio_physics_step15,
            "e_grid_kwh_sample_step15": e_grid_sample_step15,
            "full_ratio_sample_step15": full_ratio_sample_step15,
        }, full_ratio

    days: List[dict] = []
    debug_rows: List[dict] = []
    for date_str, masks in sorted(daily_masks.items(), key=lambda kv: kv[0]):
        ym = date_str[:7]
        limit_kw = _day_limit_kw(ym)
        day_start = pd.to_datetime(date_str)
        day_end = day_start + pd.Timedelta(days=1)
        day_sub = s.loc[(s.index >= day_start) & (s.index < day_end)]

        c1 = masks.get("c1", {})
        c2 = masks.get("c2", {})

        # c1 charge/discharge
        m1c = c1.get("charge_hours", [])
        m1d = c1.get("discharge_hours", [])
        met1c, fc1 = _window_metrics(day_sub, m1c, limit_kw, True)
        met1d, fd1 = _window_metrics(day_sub, m1d, limit_kw, False)
        c1_cycles = min(fc1, fd1)

        debug_rows.append({
            "date": date_str,
            "window": "c1",
            "kind": "charge",
            "hour_list": ",".join(str(int(h)) for h in (m1c or [])),
            "limit_kw": limit_kw,
            **met1c,
        })
        debug_rows.append({
            "date": date_str,
            "window": "c1",
            "kind": "discharge",
            "hour_list": ",".join(str(int(h)) for h in (m1d or [])),
            "limit_kw": limit_kw,
            **met1d,
        })

        # c2 charge/discharge
        m2c = c2.get("charge_hours", [])
        m2d = c2.get("discharge_hours", [])
        met2c, fc2 = _window_metrics(day_sub, m2c, limit_kw, True)
        met2d, fd2 = _window_metrics(day_sub, m2d, limit_kw, False)
        c2_cycles = min(fc2, fd2)

        debug_rows.append({
            "date": date_str,
            "window": "c2",
            "kind": "charge",
            "hour_list": ",".join(str(int(h)) for h in (m2c or [])),
            "limit_kw": limit_kw,
            **met2c,
        })
        debug_rows.append({
            "date": date_str,
            "window": "c2",
            "kind": "discharge",
            "hour_list": ",".join(str(int(h)) for h in (m2d or [])),
            "limit_kw": limit_kw,
            **met2d,
        })

        days.append({"date": date_str, "cycles": float(c1_cycles + c2_cycles)})

    return days, debug_rows


def export_excel_report(
    out_dir: Path,
    source_filename: str,
    days: List[dict],
    months: List[dict],
    year: dict,
    monthly_prices: List[dict] | None,
    limit_info: Dict,
    qc_dict: Dict,
    window_debug: List[dict] | None = None,
    ops_by_hour: List[dict] | None = None,
    runs_debug: List[dict] | None = None,
    profit_summary: Dict | None = None,
    step15_df: Optional[pd.DataFrame] = None,
    energy_formula: str = "physics",
) -> tuple[Path, Path | None]:
    """导出 Excel 报表（单文件多 Sheet）。

    基础 Sheet：
    - days/months/year：次数汇总
    - tou_snapshot：12 月价格
    - qc：缺价/缺失与上限信息

    调试 Sheet（如有数据）：
    - profit_days / profit_months / profit_year：收益结构化明细
    - power_step15：逐 15 分钟功率与负荷明细（含限值）
    - window_debug / ops_by_hour / runs_debug：窗口明细与运行逻辑
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    base = os.path.splitext(os.path.basename(source_filename))[0] or "result"
    xlsx = out_dir / f"{base}_计算结果.xlsx"
    summary_csv: Path | None = None

    # 构造 DataFrame
    df_days = pd.DataFrame(days)
    df_months = pd.DataFrame(months)
    df_year = pd.DataFrame([year])
    df_prices = pd.DataFrame(monthly_prices or [])

    # QC 与上限信息
    monthly_limit = pd.DataFrame(limit_info.get("monthly_demand_max") or [])
    qc_notes = pd.DataFrame({"notes": qc_dict.get("notes", [])}) if qc_dict.get("notes") else pd.DataFrame({"notes": []})
    qc_head = pd.DataFrame({
        "missing_prices": [qc_dict.get("missing_prices", 0)],
        "merged_segments": [qc_dict.get("merged_segments", 0)],
        "limit_mode": [limit_info.get("limit_mode")],
        "transformer_limit_kw": [limit_info.get("transformer_limit_kw")],
    })

    def _build_profit_row(key_name: str, key_value: Any, entry: Dict[str, dict]) -> dict:
        """将单个 main/physics/sample 收益条目拍平成一行，便于导出调试。"""
        row: Dict[str, Any] = {key_name: key_value}
        for formula in ("main", "physics", "sample"):
            m = entry.get(formula) or {}
            prefix = f"{formula}_"
            row[prefix + "revenue"] = float(m.get("revenue", 0.0) or 0.0)
            row[prefix + "cost"] = float(m.get("cost", 0.0) or 0.0)
            row[prefix + "profit"] = float(m.get("profit", 0.0) or 0.0)
            row[prefix + "discharge_energy_kwh"] = float(m.get("discharge_energy_kwh", 0.0) or 0.0)
            row[prefix + "charge_energy_kwh"] = float(m.get("charge_energy_kwh", 0.0) or 0.0)
            row[prefix + "profit_per_kwh"] = float(m.get("profit_per_kwh", 0.0) or 0.0)
        return row

    with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
        # results
        df_days.to_excel(writer, index=False, sheet_name="days")
        df_months.to_excel(writer, index=False, sheet_name="months")
        df_year.to_excel(writer, index=False, sheet_name="year")
        # TOU
        if not df_prices.empty:
            df_prices.to_excel(writer, index=False, sheet_name="tou_snapshot")
        # QC
        qc_head.to_excel(writer, index=False, sheet_name="qc")
        # 追加上限与缺价详情
        startrow = len(qc_head) + 2
        monthly_limit.to_excel(writer, index=False, sheet_name="qc", startrow=startrow)
        startrow += len(monthly_limit) + 2
        qc_notes.to_excel(writer, index=False, sheet_name="qc", startrow=startrow)

        # Summary（关键统计一页表）
        try:
            cy_m = pd.to_numeric(df_months.get("cycles"), errors="coerce") if not df_months.empty else pd.Series([], dtype=float)
            cy_d = pd.to_numeric(df_days.get("cycles"), errors="coerce") if not df_days.empty else pd.Series([], dtype=float)
            months_sum = float(cy_m.fillna(0).sum()) if not df_months.empty else 0.0
            months_nonzero = int((cy_m > 0).sum()) if not df_months.empty else 0
            months_total = int(len(df_months)) if not df_months.empty else 0
            days_nonzero = int((cy_d > 0).sum()) if not df_days.empty else 0
            days_total = int(len(df_days)) if not df_days.empty else 0

            summary_df = pd.DataFrame([{
                "year_cycles": float(pd.to_numeric(pd.Series([year.get("cycles", 0)]), errors="coerce").fillna(0).iloc[0]) if isinstance(year, dict) else 0.0,
                "months_sum_cycles": months_sum,
                "months_nonzero": months_nonzero,
                "months_total": months_total,
                "days_nonzero": days_nonzero,
                "days_total": days_total,
                "missing_prices": int(qc_dict.get("missing_prices", 0) or 0),
                "merged_segments": int(qc_dict.get("merged_segments", 0) or 0),
                "limit_mode": limit_info.get("limit_mode"),
                "transformer_limit_kw": limit_info.get("transformer_limit_kw"),
            }])
            summary_df.to_excel(writer, index=False, sheet_name="summary")
        except Exception:
            pass

        # 收益明细（按日 / 按月 / 全年）
        if profit_summary:
            days_map = (profit_summary or {}).get("days") or {}
            months_map = (profit_summary or {}).get("months") or {}
            year_entry = (profit_summary or {}).get("year") or None

            if days_map:
                rows_days: List[dict] = []
                for dkey in sorted(days_map.keys()):
                    entry = days_map.get(dkey) or {}
                    rows_days.append(_build_profit_row("date", dkey, entry))
                pd.DataFrame(rows_days).to_excel(writer, index=False, sheet_name="profit_days")

            if months_map:
                rows_months: List[dict] = []
                for ym in sorted(months_map.keys()):
                    entry = months_map.get(ym) or {}
                    rows_months.append(_build_profit_row("year_month", ym, entry))
                pd.DataFrame(rows_months).to_excel(writer, index=False, sheet_name="profit_months")

            if isinstance(year_entry, dict) and year_entry:
                year_val = year.get("year", 0) if isinstance(year, dict) else 0
                row_year = _build_profit_row("year", year_val, year_entry)
                pd.DataFrame([row_year]).to_excel(writer, index=False, sheet_name="profit_year")

        # 逐 15 分钟功率 / 负荷明细（可选）
        if step15_df is not None and not step15_df.empty:
            df_power = step15_df.copy()
            df_power = df_power.reset_index().rename(columns={"index": "timestamp"})
            # 统一时间戳格式，便于在 Excel 中过滤
            try:
                df_power["timestamp"] = pd.to_datetime(df_power["timestamp"], errors="coerce").dt.strftime(
                    "%Y-%m-%dT%H:%M:%S"
                )
            except Exception:  # pragma: no cover - 调试容错
                pass

            # 加上“引入储能后负荷”列（physics / sample 两套）
            for suffix, col in (
                ("physics", "p_grid_effect_physics_kw"),
                ("sample", "p_grid_effect_sample_kw"),
            ):
                if col in df_power.columns:
                    df_power[f"load_with_storage_{suffix}_kw"] = df_power["load_kw"] + df_power[col]

            # 标记主口径，便于对照 StorageProfit 页
            main_col = (
                "p_grid_effect_physics_kw"
                if (energy_formula or "physics").strip() == "physics"
                else "p_grid_effect_sample_kw"
            )
            if main_col in df_power.columns:
                df_power["p_grid_effect_main_kw"] = df_power[main_col]
                df_power["load_with_storage_main_kw"] = df_power["load_kw"] + df_power["p_grid_effect_main_kw"]

            df_power.to_excel(writer, index=False, sheet_name="power_step15")

        # 窗口汇总明细（可选）
        if window_debug:
            df_win = pd.DataFrame(window_debug)
            # 统一列顺序，确保便于人工核对
            cols = [
                "date", "window", "kind", "hour_list", "points", "hours",
                "limit_kw", "avg_load_kw", "allow_kw",
                # 窗口平均法（主口径当前值）
                "base_kwh", "e_grid_kwh", "full_ratio",
                # 窗口平均法（physics 与 sample 对拍）
                "e_grid_kwh_physics", "full_ratio_physics",
                "e_grid_kwh_sample",  "full_ratio_sample",
                # 逐点积分（physics 与 sample 对拍）
                "base_kwh_step15",
                "e_grid_kwh_physics_step15", "full_ratio_physics_step15",
                "e_grid_kwh_sample_step15",  "full_ratio_sample_step15",
            ]
            for c in cols:
                if c not in df_win.columns:
                    df_win[c] = None
            df_win = df_win[cols]
            df_win.to_excel(writer, index=False, sheet_name="window_debug")

        # 每小时运行逻辑（可选）
        if ops_by_hour:
            df_ops = pd.DataFrame(ops_by_hour)
            # 确保列顺序 date,h00..h23
            cols_ops = ["date"] + [f"h{h:02d}" for h in range(24)]
            for c in cols_ops:
                if c not in df_ops.columns:
                    df_ops[c] = None
            df_ops = df_ops[cols_ops]
            df_ops.to_excel(writer, index=False, sheet_name="ops_by_hour")

        # 连段合并过程（可选）
        if runs_debug:
            df_runs = pd.DataFrame(runs_debug)
            cols_runs = [
                "date", "seq", "kind", "start_hour", "end_hour",
                "length_hours", "filtered_by_threshold", "merged_to", "wrap_across_midnight",
            ]
            for c in cols_runs:
                if c not in df_runs.columns:
                    df_runs[c] = None
            df_runs = df_runs[cols_runs]
            df_runs.to_excel(writer, index=False, sheet_name="runs_debug")

    # 生成 CSV 简表
    try:
        summary_csv = out_dir / f"{base}_summary.csv"
        if 'summary_df' in locals():
            summary_df.to_csv(summary_csv, index=False, encoding="utf-8-sig")
        else:
            pd.DataFrame([year]).to_csv(summary_csv, index=False, encoding="utf-8-sig")
    except Exception:
        summary_csv = None

    return xlsx, summary_csv


def build_step15_power_series(
    series_15m: pd.DataFrame,
    daily_ops: Dict[str, List[str]],
    limit_info: Dict,
    storage_cfg: Dict,
    price_series: Optional[pd.DataFrame] | None,
    *,
    window_debug: Optional[List[dict]] = None,
    energy_formula: str = "physics",
) -> pd.DataFrame:
    """构建 15 分钟粒度的功率 / 电量序列，供收益计算和曲线对比复用.

    返回的 DataFrame 以 DatetimeIndex 为索引，至少包含：
    - load_kw: 原始负荷
    - price: 电价（可能为 NaN）
    - tier: TOU 分段 ID
    - date_str: 'YYYY-MM-DD'
    - year_month: 'YYYY-MM'
    - op: 每小时运行逻辑（充/放/待机）
    - p_batt_kw: 电池侧功率（对电池为正充电，负为放电）
    - e_in_physics_kwh / e_out_physics_kwh
    - e_in_sample_kwh / e_out_sample_kwh
    - p_grid_effect_physics_kw / p_grid_effect_sample_kw
    """
    if series_15m is None or series_15m.empty:
        return pd.DataFrame()

    # 统一时间索引与列名
    s = series_15m.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index, errors="coerce")
    s = s.dropna(subset=["load_kw"]).sort_index()
    if "load_kw" not in s.columns:
        logger.warning("[profit_step15] series_15m 缺少 load_kw 列，无法计算收益")
        return pd.DataFrame()

    # 价格序列对齐，如果不存在则补空列
    if price_series is not None and not price_series.empty:
        p = price_series.copy()
        if not isinstance(p.index, pd.DatetimeIndex):
            p.index = pd.to_datetime(p.index, errors="coerce")
        p = p.sort_index()
        joined = s.join(p[["price", "tier"]], how="left")
    else:
        joined = s.copy()
        joined["price"] = None
        joined["tier"] = None

    joined = joined.sort_index()

    # 限值信息
    month_max_map: Dict[str, float] = {
        it.get("year_month"): float(it.get("max_kw", 0) or 0)
        for it in (limit_info.get("monthly_demand_max") or [])
    }
    transformer_limit_kw = limit_info.get("transformer_limit_kw")
    limit_mode = (limit_info.get("limit_mode") or "monthly_demand_max").strip() or "monthly_demand_max"

    def _day_limit_kw(ts: pd.Timestamp) -> float:
        ym = ts.strftime("%Y-%m")
        if limit_mode == "transformer_capacity" and transformer_limit_kw:
            try:
                return float(transformer_limit_kw)
            except Exception:  # pragma: no cover
                return 0.0
        return float(month_max_map.get(ym, 0.0))

    # 储能配置
    cap = float(storage_cfg.get("capacity_kwh", 0) or 0)
    eta = float(storage_cfg.get("single_side_efficiency", 0.9) or 0.9)
    dod_cfg = float(storage_cfg.get("depth_of_discharge", 1.0) or 1.0)
    soc_min = float(storage_cfg.get("soc_min", 0.05) or 0.05)
    soc_max = float(storage_cfg.get("soc_max", 0.95) or 0.95)
    effective_dod = max(0.0, min(dod_cfg, soc_max - soc_min))
    # 兼容遗留引用，防止 NameError
    dod = effective_dod
    reserve_ch = float(storage_cfg.get("reserve_charge_kw", 0) or 0)
    reserve_dis = float(storage_cfg.get("reserve_discharge_kw", 0) or 0)
    dt_hours = 0.25
    main_formula = (energy_formula or "physics").strip()
    main_formula = main_formula if main_formula in ("physics", "sample") else "physics"

    # 运行逻辑编码（与前端 / _extract_hour_ops 保持一致）
    OP_STANDBY = "待机"
    OP_CHARGE = "充"
    OP_DISCHARGE = "放"

    def _op_for_ts(ts: pd.Timestamp) -> Optional[str]:
        day_key = ts.strftime("%Y-%m-%d")
        ops = daily_ops.get(day_key) or []
        h = ts.hour
        return ops[h] if 0 <= h < len(ops) else None

    # 构造窗口目标（基于 window_debug 的 step15 full_ratio）
    window_targets: Dict[tuple[str, str], dict] = {}
    if window_debug:
        for row in window_debug:
            try:
                date_str = str(row.get("date") or "")
                window = str(row.get("window") or "").lower()
                kind = str(row.get("kind") or "").lower()
                hours_raw = str(row.get("hour_list") or "").split(",")
                hours_set = {int(h) for h in hours_raw if str(h).strip() != ""}
                full_main = None
                key_step = f"full_ratio_{main_formula}_step15"
                key_plain = f"full_ratio_{main_formula}"
                if key_step in row and row.get(key_step) is not None:
                    full_main = float(row.get(key_step) or 0.0)
                elif key_plain in row and row.get(key_plain) is not None:
                    full_main = float(row.get(key_plain) or 0.0)
                if full_main is None:
                    full_main = 1.0
                if not date_str or window not in ("c1", "c2"):
                    continue
                tgt = window_targets.setdefault((date_str, window), {
                    "charge_hours": set(),
                    "discharge_hours": set(),
                    "full_ratio_main": full_main,
                })
                # full_ratio 取同窗口内的最大值，保守
                prev_full = tgt.get("full_ratio_main")
                if prev_full is None:
                    tgt["full_ratio_main"] = full_main
                else:
                    tgt["full_ratio_main"] = min(prev_full, full_main)
                if kind == "charge":
                    tgt["charge_hours"].update(hours_set)
                elif kind == "discharge":
                    tgt["discharge_hours"].update(hours_set)
            except Exception:
                continue

    def _window_key(ts: pd.Timestamp, op: Optional[str]) -> Optional[tuple[str, str]]:
        date_str = ts.strftime("%Y-%m-%d")
        h = ts.hour
        # 仅在 window_targets 提供信息时使用
        if not window_targets:
            return None
        candidates = []
        for (d, w), info in window_targets.items():
            if d != date_str:
                continue
            if op == OP_CHARGE and h in info.get("charge_hours", set()):
                candidates.append((d, w))
            elif op == OP_DISCHARGE and h in info.get("discharge_hours", set()):
                candidates.append((d, w))
        return candidates[0] if candidates else None

    # 窗口累计状态：charged/discharged（电网侧）
    window_state: Dict[tuple[str, str], dict] = {}

    records: List[dict] = []
    for ts, row in joined.iterrows():
        try:
            load_kw = float(row.get("load_kw", 0.0) or 0.0)
        except Exception:  # pragma: no cover
            load_kw = 0.0

        price_val = row.get("price")
        try:
            price = float(price_val) if price_val is not None and pd.notna(price_val) else None
        except Exception:  # pragma: no cover
            price = None

        tier = row.get("tier")
        op = _op_for_ts(ts)
        limit_kw = _day_limit_kw(ts)
        win_key = _window_key(ts, op)

        # 电池侧功率：对电池为正充电，负为放电
        p_batt = 0.0
        if op == OP_CHARGE:
            p_batt = max(limit_kw - reserve_ch - load_kw, 0.0)
        elif op == OP_DISCHARGE:
            p_batt = -max(load_kw - reserve_dis, 0.0)
        else:
            p_batt = 0.0

        # 分别在 physics / sample 口径下计算电网侧能量
        e_in_phys = 0.0
        e_out_phys = 0.0
        e_in_sample = 0.0
        e_out_sample = 0.0

        if p_batt > 0:  # 充电
            e_batt = p_batt * dt_hours
            # physics: E_in_grid = base_kwh * DOD / η
            e_in_phys = e_batt * (effective_dod / max(eta, 1e-9))
            # sample: E_in_grid = base_kwh / DOD * η
            e_in_sample = e_batt * (eta / max(effective_dod, 1e-9))
        elif p_batt < 0:  # 放电
            e_batt = -p_batt * dt_hours
            # physics: E_out_grid = base_kwh * DOD * η
            e_out_phys = e_batt * (effective_dod * eta)
            # sample: E_out_grid = base_kwh / DOD / η
            e_out_sample = e_batt * (1.0 / max(effective_dod * eta, 1e-9))

        # 对电网视角的等效功率（正：从电网取电，负：向电网送电）
        p_grid_phys = (e_in_phys - e_out_phys) / dt_hours if dt_hours > 0 else 0.0
        p_grid_sample = (e_in_sample - e_out_sample) / dt_hours if dt_hours > 0 else 0.0

        # 在变压器容量口径下，确保“引入储能后的负荷”不会在充电段进一步突破上限
        # 注意：原始负荷本身若已超过上限，这里不会强行截断，只保证储能本身不会再向上推高。
        if limit_mode == "transformer_capacity" and limit_kw and load_kw < limit_kw:
            max_p_grid_charge = max(p_grid_phys, p_grid_sample, 0.0)
            if max_p_grid_charge > 0:
                load_with_max = load_kw + max_p_grid_charge
                if load_with_max > limit_kw + 1e-6:
                    # 允许的电网侧“额外功率”
                    allowed_extra = max(limit_kw - load_kw, 0.0)
                    if allowed_extra <= 0:
                        scale_cap = 0.0
                    else:
                        scale_cap = allowed_extra / max_p_grid_charge
                    if scale_cap < 0:
                        scale_cap = 0.0
                    if scale_cap < 1.0:
                        # 按比例缩放所有与电池相关的量，保持 physics / sample 两个口径一致
                        p_batt *= scale_cap
                        e_in_phys *= scale_cap
                        e_out_phys *= scale_cap
                        e_in_sample *= scale_cap
                        e_out_sample *= scale_cap
                        p_grid_phys *= scale_cap
                        p_grid_sample *= scale_cap

        # 禁止“余电上网”：不允许引入储能后的负荷变为负值
        # 注意：这里是针对电网视角的总负荷（原始负荷 + 储能影响），与计费口径无关。
        if load_kw > 0:
            max_discharge = max(-p_grid_phys, -p_grid_sample, 0.0)
            if max_discharge > 0:
                allowed_discharge = load_kw  # 最多只能把负荷削到 0
                if max_discharge > allowed_discharge + 1e-6:
                    scale_dis = allowed_discharge / max_discharge if allowed_discharge > 0 else 0.0
                    if scale_dis < 0:
                        scale_dis = 0.0
                    if scale_dis < 1.0:
                        p_batt *= scale_dis
                        e_in_phys *= scale_dis
                        e_out_phys *= scale_dis
                        e_in_sample *= scale_dis
                        e_out_sample *= scale_dis
                        p_grid_phys *= scale_dis
                        p_grid_sample *= scale_dis

        # 窗口充放能量目标（对称约束）
        cum_charge = None
        cum_discharge = None
        charge_target = None
        discharge_target = None
        if win_key and cap > 0 and effective_dod > 0:
            state = window_state.setdefault(win_key, {
                "charged": 0.0,
                "discharged": 0.0,
                "charge_target": None,
                "discharge_target": None,
            })
            if state["charge_target"] is None or state["discharge_target"] is None:
                info = window_targets.get(win_key, {})
                full_main = float(info.get("full_ratio_main", 1.0) or 1.0)
                usable_batt = cap * full_main
                usable_batt_dod = usable_batt * effective_dod
                charge_target = usable_batt_dod / max(eta, 1e-9)
                discharge_target = usable_batt_dod * eta
                state["charge_target"] = charge_target
                state["discharge_target"] = discharge_target
            charge_target = state["charge_target"]
            discharge_target = state["discharge_target"]
            # 按主口径能量判断超额
            e_in_main = e_in_phys if main_formula == "physics" else e_in_sample
            e_out_main = e_out_phys if main_formula == "physics" else e_out_sample
            if op == OP_CHARGE and charge_target:
                allowed = max(charge_target - state["charged"], 0.0)
                if e_in_main > allowed + 1e-9:
                    scale_win = allowed / max(e_in_main, 1e-9)
                    # 缩放所有能量/功率
                    p_batt *= scale_win
                    e_in_phys *= scale_win
                    e_out_phys *= scale_win
                    e_in_sample *= scale_win
                    e_out_sample *= scale_win
                    p_grid_phys *= scale_win
                    p_grid_sample *= scale_win
                    e_in_main = e_in_phys if main_formula == "physics" else e_in_sample
            elif op == OP_DISCHARGE and discharge_target:
                allowed = max(discharge_target - state["discharged"], 0.0)
                if e_out_main > allowed + 1e-9:
                    scale_win = allowed / max(e_out_main, 1e-9)
                    p_batt *= scale_win
                    e_in_phys *= scale_win
                    e_out_phys *= scale_win
                    e_in_sample *= scale_win
                    e_out_sample *= scale_win
                    p_grid_phys *= scale_win
                    p_grid_sample *= scale_win
                    e_out_main = e_out_phys if main_formula == "physics" else e_out_sample
            # 更新累计
            state["charged"] += e_in_main
            state["discharged"] += e_out_main
            cum_charge = state["charged"]
            cum_discharge = state["discharged"]
        else:
            cum_charge = None
            cum_discharge = None
            charge_target = None
            discharge_target = None

        records.append(
            {
                "timestamp": ts,
                "load_kw": load_kw,
                "price": price,
                "tier": tier,
                "date_str": ts.strftime("%Y-%m-%d"),
                "year_month": ts.strftime("%Y-%m"),
                "op": op or OP_STANDBY,
                "limit_kw": float(limit_kw) if limit_kw is not None else None,
                "p_batt_kw": p_batt,
                "e_in_physics_kwh": e_in_phys,
                "e_out_physics_kwh": e_out_phys,
                "e_in_sample_kwh": e_in_sample,
                "e_out_sample_kwh": e_out_sample,
                "p_grid_effect_physics_kw": p_grid_phys,
                "p_grid_effect_sample_kw": p_grid_sample,
                "cum_charge_grid_main": cum_charge,
                "cum_discharge_grid_main": cum_discharge,
                "charge_target_grid_main": charge_target,
                "discharge_target_grid_main": discharge_target,
            }
        )

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame.from_records(records).set_index("timestamp").sort_index()
    return df


def compute_profit_summary_step15(
    series_15m: pd.DataFrame,
    daily_ops: Dict[str, List[str]],
    limit_info: Dict,
    storage_cfg: Dict,
    price_series: Optional[pd.DataFrame] | None,
    energy_formula: str = "physics",
    window_debug: Optional[List[dict]] = None,
) -> dict:
    """基于 step_15min 逐点积分的收益计算.

    返回结构：
    {
      "days":   { "YYYY-MM-DD": { "main": {...}, "physics": {...}, "sample": {...} } },
      "months": { "YYYY-MM":    { "main": {...}, "physics": {...}, "sample": {...} } },
      "year":   { "main": {...}, "physics": {...}, "sample": {...} } | None,
    }
    其中 {...} 对应 StorageProfit 的字段字典。
    """
    if series_15m is None or series_15m.empty:
        return {"days": {}, "months": {}, "year": None}

    df = build_step15_power_series(
        series_15m,
        daily_ops,
        limit_info,
        storage_cfg,
        price_series,
        window_debug=window_debug,
        energy_formula=energy_formula,
    )
    if df.empty:
        return {"days": {}, "months": {}, "year": None}

    main_formula = (energy_formula or "physics").strip() or "physics"
    if main_formula not in ("physics", "sample"):
        main_formula = "physics"

    formulas = ("physics", "sample")

    # 调试：记录缺价点数量，便于定位收益为 0 的原因
    try:
        missing_price_points = int(df["price"].isna().sum())
        if missing_price_points > 0:
            logger.debug(
                "profit step15: missing price points=%s/%s",
                missing_price_points,
                len(df),
            )
    except Exception:  # pragma: no cover - 调试容错
        missing_price_points = 0

    # 按日聚合
    day_metrics: Dict[str, Dict[str, dict]] = {f: {} for f in formulas}

    for formula in formulas:
        e_in_col = f"e_in_{formula}_kwh"
        e_out_col = f"e_out_{formula}_kwh"

        for date_str, sub in df.groupby("date_str"):
            e_in = float(sub[e_in_col].sum())
            e_out = float(sub[e_out_col].sum())

            price_series_day = sub["price"].fillna(0.0)
            cost = float((sub[e_in_col] * price_series_day).sum())
            revenue = float((sub[e_out_col] * price_series_day).sum())
            profit = revenue - cost

            metrics = {
                "revenue": revenue,
                "cost": cost,
                "profit": profit,
                "discharge_energy_kwh": e_out,
                "charge_energy_kwh": e_in,
            }
            if e_out > 0:
                metrics["profit_per_kwh"] = profit / e_out
            else:
                metrics["profit_per_kwh"] = 0.0

            day_metrics[formula][date_str] = metrics

    # 按月与年度聚合（基于日结果累加，避免重复计算）
    month_metrics: Dict[str, Dict[str, dict]] = {f: {} for f in formulas}
    year_metrics: Dict[str, dict] = {
        f: {"revenue": 0.0, "cost": 0.0, "profit": 0.0, "discharge_energy_kwh": 0.0, "charge_energy_kwh": 0.0}
        for f in formulas
    }

    for formula in formulas:
        for date_str, m in day_metrics[formula].items():
            ym = date_str[:7]
            bucket = month_metrics[formula].setdefault(
                ym,
                {"revenue": 0.0, "cost": 0.0, "profit": 0.0, "discharge_energy_kwh": 0.0, "charge_energy_kwh": 0.0},
            )
            for k in ("revenue", "cost", "profit", "discharge_energy_kwh", "charge_energy_kwh"):
                bucket[k] += float(m.get(k, 0.0) or 0.0)
                year_metrics[formula][k] += float(m.get(k, 0.0) or 0.0)

        # 计算月度单位收益
        for ym, m in month_metrics[formula].items():
            e_out = m["discharge_energy_kwh"]
            if e_out > 0:
                m["profit_per_kwh"] = m["profit"] / e_out
            else:
                m["profit_per_kwh"] = 0.0

        # 年度单位收益
        e_out_year = year_metrics[formula]["discharge_energy_kwh"]
        if e_out_year > 0:
            year_metrics[formula]["profit_per_kwh"] = year_metrics[formula]["profit"] / e_out_year
        else:
            year_metrics[formula]["profit_per_kwh"] = 0.0

    def _to_profit_dict(src: dict) -> dict:
        return {
            "revenue": float(src.get("revenue", 0.0) or 0.0),
            "cost": float(src.get("cost", 0.0) or 0.0),
            "profit": float(src.get("profit", 0.0) or 0.0),
            "discharge_energy_kwh": float(src.get("discharge_energy_kwh", 0.0) or 0.0),
            "charge_energy_kwh": float(src.get("charge_energy_kwh", 0.0) or 0.0),
            "profit_per_kwh": float(src.get("profit_per_kwh", 0.0) or 0.0),
        }

    # 组装返回结构
    days_result: Dict[str, Dict[str, dict]] = {}
    for date_str in sorted(set(df["date_str"].unique())):
        entry: Dict[str, dict] = {}
        for formula in formulas:
            m = day_metrics[formula].get(date_str)
            if m:
                entry[formula] = _to_profit_dict(m)
        if entry:
            if main_formula in entry:
                entry["main"] = entry[main_formula]
            days_result[date_str] = entry

    months_result: Dict[str, Dict[str, dict]] = {}
    all_months = set()
    for formula in formulas:
        all_months.update(month_metrics[formula].keys())
    for ym in sorted(all_months):
        entry: Dict[str, dict] = {}
        for formula in formulas:
            m = month_metrics[formula].get(ym)
            if m:
                entry[formula] = _to_profit_dict(m)
        if entry:
            if main_formula in entry:
                entry["main"] = entry[main_formula]
            months_result[ym] = entry

    year_entry: Dict[str, dict] = {}
    for formula in formulas:
        m = year_metrics[formula]
        # 如果全年完全为 0，可以认为缺少有效数据，依然返回 0 结构，便于前端展示
        year_entry[formula] = _to_profit_dict(m)
    if year_entry:
        if main_formula in year_entry:
            year_entry["main"] = year_entry[main_formula]
        year_result: Optional[dict] = year_entry
    else:
        year_result = None

    return {
        "days": days_result,
        "months": months_result,
        "year": year_result,
    }
