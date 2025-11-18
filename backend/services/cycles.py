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
    dod = float(storage_cfg.get("depth_of_discharge", 1.0) or 1.0)
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
) -> tuple[Path, Path | None]:
    """导出 Excel 报表（单文件多 Sheet）。

    - Sheet1: results（日、月、年）
    - Sheet2: tou_snapshot（12 月价格）
    - Sheet3: qc（缺价/缺失与合并说明、上限统计）
    返回：生成的文件路径
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
