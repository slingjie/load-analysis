from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pandas as pd
from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    CleanedPoint,
    LoadAnalysisResponse,
    MetaInfo,
    ProjectSummaryRequest,
    ProjectSummaryResponse,
    QualityReport,
    StorageCyclesDay,
    StorageCyclesMonth,
    StorageCyclesResponse,
    StorageCyclesYear,
    StorageCurvesPoint,
    StorageCurvesResponse,
    StorageCurvesSummary,
    StorageProfit,
    StorageProfitWithFormulas,
    StorageQC,
    StorageWindowMonthSummary,
)
from .services import loader, quality
from .services import cycles as cycles_svc


logger = logging.getLogger("load-analysis")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
logger.setLevel(logging.DEBUG)
logger.propagate = False


app = FastAPI(title="Load Data Analysis", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/load/analyze", response_model=LoadAnalysisResponse)
async def analyze_load(file: UploadFile = File(...)) -> LoadAnalysisResponse:
    """上传文件 -> 解析 -> 质量报告 + 原始点位（供前端复用）"""

    filename = file.filename or "<uploaded>"
    try:
        file_bytes = await file.read()
    except Exception as exc:  # pragma: no cover
        logger.exception("read file failed: %s", filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="failed to read upload file",
        ) from exc

    logger.debug(
        "received upload: name=%s size=%s bytes content_type=%s",
        filename,
        len(file_bytes),
        getattr(file, "content_type", None),
    )

    try:
        raw_df = loader.load_dataframe(file_bytes)
    except loader.LoaderError as exc:
        logger.exception("parse file failed: %s", filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # 质量统计
    report_dict, meta_dict = quality.build_quality_report(raw_df)

    # 透传原始点（timestamp, load -> load_kwh）
    cleaned_points: List[CleanedPoint] = []
    if "timestamp" in raw_df.columns and "load" in raw_df.columns:
        raw_df_copy = raw_df.copy()
        raw_df_copy["timestamp"] = pd.to_datetime(raw_df_copy["timestamp"], errors="coerce")
        raw_df_copy["load"] = pd.to_numeric(raw_df_copy["load"], errors="coerce")
        for _, row in raw_df_copy.iterrows():
            ts: pd.Timestamp = row["timestamp"]  # type: ignore[assignment]
            load: float = row["load"]  # type: ignore[assignment]
            if not pd.isna(ts):
                load_val: float = float(load) if not pd.isna(load) else 0.0
                cleaned_points.append(
                    CleanedPoint(
                        timestamp=ts.to_pydatetime().isoformat(),
                        load_kwh=round(load_val, 6),
                    )
                )

    response = LoadAnalysisResponse(
        cleaned_points=cleaned_points,
        report=QualityReport.model_validate(report_dict),
        meta=MetaInfo.model_validate(meta_dict),
    )

    logger.info("file %s analyzed: records=%s", filename, meta_dict.get("total_records"))
    return response


@app.get("/health")
async def health_check() -> dict[str, str]:
    """简单健康检查"""

    return {"status": "ok"}


def _parse_payload(payload: str | Dict[str, Any]) -> Dict[str, Any]:
    """解析前端 FormData 中的 payload 字段"""

    try:
        obj = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(obj, dict):
            raise ValueError("payload must be an object")
        return obj
    except Exception as exc:  # pragma: no cover - 防御性兜底
        logger.exception(
            "payload parse failed: %s",
            payload[:200] if isinstance(payload, str) else type(payload),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payload is not a valid JSON object string",
        ) from exc


def _build_series_15m_from_payload(
    payload_obj: Dict[str, Any],
    file_bytes: bytes | None,
) -> pd.DataFrame:
    """根据 payload.points 或上传文件构建 15min 负荷序列"""

    points = payload_obj.get("points")
    if isinstance(points, list) and points:
        try:
            return cycles_svc.parse_points_series(points)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"points parse failed: {exc}",
            ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="no upload file or points provided",
        )
    try:
        return cycles_svc.parse_load_series(file_bytes)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@app.post("/api/storage/cycles", response_model=StorageCyclesResponse)
async def compute_storage_cycles(
    file: UploadFile | None = File(None),
    payload: str = Form(...),
) -> StorageCyclesResponse:
    """储能等效满充满放次数 + 收益 + 质量指标"""

    filename: str | None = None
    file_bytes: bytes | None = None

    if file is not None:
        try:
            filename = file.filename or "<uploaded>"
            file_bytes = await file.read()
        except Exception as exc:  # pragma: no cover
            logger.exception("read file failed: %s", filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="failed to read upload file",
            ) from exc

    payload_obj = _parse_payload(payload)

    # 15min 负荷序列
    series_15m = _build_series_15m_from_payload(payload_obj, file_bytes)

    # 储能配置
    storage_cfg = payload_obj.get("storage") if isinstance(payload_obj, dict) else None
    if not isinstance(storage_cfg, dict):
        storage_cfg = {}
    metering_mode = storage_cfg.get("metering_mode", "monthly_demand_max")
    transformer_capacity_kva = storage_cfg.get("transformer_capacity_kva")
    transformer_power_factor = storage_cfg.get("transformer_power_factor")
    merge_threshold_minutes = storage_cfg.get("merge_threshold_minutes", 30)

    # 限值信息
    limit_info = cycles_svc.compute_limit_info(
        series_15m,
        metering_mode=metering_mode,
        transformer_capacity_kva=transformer_capacity_kva,
        transformer_power_factor=transformer_power_factor,
    )

    # 策略 -> daily_ops / daily_masks
    strategy_src = payload_obj.get("strategySource") if isinstance(payload_obj, dict) else None
    if not isinstance(strategy_src, dict):
        strategy_src = {}
    monthly_schedule = strategy_src.get("monthlySchedule")
    date_rules = strategy_src.get("dateRules")

    try:
        daily_ops = cycles_svc.build_daily_ops(series_15m, monthly_schedule, date_rules)
        daily_masks, merged_cnt, runs_debug = cycles_svc.build_daily_cycles_masks(
            daily_ops,
            merge_threshold_minutes=merge_threshold_minutes,
            wrap_across_midnight=True,
        )
    except Exception as exc:
        logger.exception("strategy build failed: %s", exc)
        daily_ops = {}
        daily_masks = {}
        merged_cnt = 0
        runs_debug = []
        extra_notes: List[str] = ["strategy build failed: " + str(exc)]
    else:
        extra_notes = []

    # TOU 映射（用于价格与 QC）
    monthly_prices = payload_obj.get("monthlyTouPrices") if isinstance(payload_obj, dict) else None
    try:
        price_series, missing_points_cnt = cycles_svc.build_price_series(
            series_15m,
            monthly_schedule=monthly_schedule,
            date_rules=date_rules,
            monthly_prices=monthly_prices,
        )
    except Exception as exc:
        logger.exception("TOU map failed: %s", exc)
        price_series = pd.DataFrame(index=series_15m.index, data={"tier": [], "price": []})
        missing_points_cnt = 0
        extra_notes.append("TOU map failed: " + str(exc))
    else:
        if missing_points_cnt > 0:
            extra_notes.append(
                f"TOU 价格缺失 {missing_points_cnt} 个 15 分钟点，收益按 0 处理并记录到 missing_prices。"
            )

    # 核心 window_avg 计算
    energy_formula = storage_cfg.get("energy_formula", "physics") or "physics"
    try:
        days_raw, window_debug = cycles_svc.compute_window_avg_days_with_debug(
            series_15m,
            daily_masks=daily_masks,
            storage_cfg=storage_cfg,
            limit_info=limit_info,
            energy_formula=energy_formula,
        )
    except Exception as exc:
        logger.exception("window_avg compute failed: %s", exc)
        days_raw, window_debug = [], []

    # 基于 step_15min 的收益汇总
    try:
        if daily_ops and not price_series.empty:
            profit_summary = cycles_svc.compute_profit_summary_step15(
                series_15m,
                daily_ops=daily_ops,
                limit_info=limit_info,
                storage_cfg=storage_cfg,
                price_series=price_series,
                energy_formula=energy_formula,
                window_debug=window_debug,
            )
        else:
            profit_summary = {"days": {}, "months": {}, "year": None}
    except Exception as exc:
        logger.exception("profit compute failed: %s", exc)
        extra_notes.append("profit compute failed: " + str(exc))
        profit_summary = {"days": {}, "months": {}, "year": None}

    profit_days = (profit_summary or {}).get("days") or {}
    profit_months = (profit_summary or {}).get("months") or {}
    profit_year = (profit_summary or {}).get("year") or None

    # 日 / 月 / 年 cycles + profit 映射
    days: List[StorageCyclesDay] = []
    month_map: Dict[str, float] = {}
    year_set: set[int] = set()
    for d in days_raw:
        date_str = str(d.get("date"))
        cycles_val = float(d.get("cycles", 0.0) or 0.0)
        ym = date_str[:7]
        month_map[ym] = month_map.get(ym, 0.0) + cycles_val
        try:
            year_set.add(int(date_str[:4]))
        except Exception:
            pass

        profit_payload = profit_days.get(date_str) or {}
        day_profit_obj: StorageProfitWithFormulas | None = None
        if profit_payload:
            day_profit_obj = StorageProfitWithFormulas(
                main=StorageProfit(**profit_payload["main"]) if profit_payload.get("main") else None,
                physics=StorageProfit(**profit_payload["physics"]) if profit_payload.get("physics") else None,
                sample=StorageProfit(**profit_payload["sample"]) if profit_payload.get("sample") else None,
            )
        days.append(
            StorageCyclesDay(
                date=date_str,
                cycles=cycles_val,
                profit=day_profit_obj,
            )
        )

    months: List[StorageCyclesMonth] = []
    for ym, cyc in sorted(month_map.items()):
        profit_payload = profit_months.get(ym) or {}
        month_profit_obj: StorageProfitWithFormulas | None = None
        if profit_payload:
            month_profit_obj = StorageProfitWithFormulas(
                main=StorageProfit(**profit_payload["main"]) if profit_payload.get("main") else None,
                physics=StorageProfit(**profit_payload["physics"]) if profit_payload.get("physics") else None,
                sample=StorageProfit(**profit_payload["sample"]) if profit_payload.get("sample") else None,
            )
        months.append(
            StorageCyclesMonth(
                year_month=ym,
                cycles=float(cyc),
                profit=month_profit_obj,
            )
        )

    total_cycles = sum(float(m.cycles) for m in months)
    year_val = list(year_set)[0] if len(year_set) == 1 else 0
    year_profit_obj: StorageProfitWithFormulas | None = None
    if isinstance(profit_year, dict) and profit_year:
        year_profit_obj = StorageProfitWithFormulas(
            main=StorageProfit(**profit_year["main"]) if profit_year.get("main") else None,
            physics=StorageProfit(**profit_year["physics"]) if profit_year.get("physics") else None,
            sample=StorageProfit(**profit_year["sample"]) if profit_year.get("sample") else None,
        )
    year_summary = StorageCyclesYear(year=year_val, cycles=float(total_cycles), profit=year_profit_obj)

    qc = StorageQC(
        notes=(limit_info.get("notes", []) + extra_notes),
        limit_mode=limit_info.get("limit_mode"),
        transformer_limit_kw=limit_info.get("transformer_limit_kw"),
        monthly_demand_max=limit_info.get("monthly_demand_max", []),
        merged_segments=int(merged_cnt) if "merged_cnt" in locals() else 0,
        missing_prices=int(missing_points_cnt),
    )

    # 尖段放电占比
    try:
        tip_summary_dict = (
            cycles_svc.compute_tip_discharge_summary(
                series_15m,
                price_series,
                daily_ops=daily_ops,
                daily_masks=daily_masks,
                storage_cfg=storage_cfg,
            )
            if not price_series.empty
            else None
        )
    except Exception as exc:  # pragma: no cover
        tip_summary_dict = None
        qc.notes.append(f"tip summary failed: {exc}")

    # Window_debug -> WindowMonthSummary
    window_month_summary: List[StorageWindowMonthSummary] = []
    if window_debug:
        agg: Dict[str, Dict[str, float]] = {}
        for row in window_debug:
            try:
                date_str = str(row.get("date") or "")
                if len(date_str) < 7:
                    continue
                ym = date_str[:7]
                win = str(row.get("window") or "").lower()
                kind = str(row.get("kind") or "").lower()
                if energy_formula == "physics":
                    ratio = float(row.get("full_ratio_physics", 0.0) or 0.0)
                else:
                    ratio = float(row.get("full_ratio_sample", 0.0) or 0.0)
                if ratio == 0.0:
                    continue
                bucket = agg.setdefault(
                    ym,
                    {
                        "first_charge_cycles": 0.0,
                        "first_discharge_cycles": 0.0,
                        "second_charge_cycles": 0.0,
                        "second_discharge_cycles": 0.0,
                    },
                )
                if win == "c1" and kind == "charge":
                    bucket["first_charge_cycles"] += ratio
                elif win == "c1" and kind == "discharge":
                    bucket["first_discharge_cycles"] += ratio
                elif win == "c2" and kind == "charge":
                    bucket["second_charge_cycles"] += ratio
                elif win == "c2" and kind == "discharge":
                    bucket["second_discharge_cycles"] += ratio
            except Exception:
                # 单行异常不影响整体
                continue

        for ym, vals in sorted(agg.items()):
            window_month_summary.append(
                StorageWindowMonthSummary(
                    year_month=ym,
                    first_charge_cycles=float(vals.get("first_charge_cycles", 0.0) or 0.0),
                    first_discharge_cycles=float(vals.get("first_discharge_cycles", 0.0) or 0.0),
                    second_charge_cycles=float(vals.get("second_charge_cycles", 0.0) or 0.0),
                    second_discharge_cycles=float(vals.get("second_discharge_cycles", 0.0) or 0.0),
                )
            )

    logger.info("/api/storage/cycles: source=%s points=%s", filename, isinstance(payload_obj.get("points"), list) and len(payload_obj.get("points") or []))
    logger.info(
        "/api/storage/cycles done: days=%s months=%s year_cycles=%s window_months=%s",
        len(days),
        len(months),
        total_cycles,
        len(window_month_summary),
    )

    # 导出 Excel 报表（尽量不影响接口主流程）
    from datetime import datetime as _dt  # noqa: WPS433
    from pathlib import Path as _Path  # noqa: WPS433

    ts_dir = _dt.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _Path("outputs") / ts_dir
    try:
        # 生成逐 15 分钟功率 / 负荷序列，供导出调试
        try:
            step15_df = cycles_svc.build_step15_power_series(
                series_15m,
                daily_ops=daily_ops,
                limit_info=limit_info,
                storage_cfg=storage_cfg,
                price_series=price_series,
                window_debug=window_debug,
                energy_formula=energy_formula,
            )
        except Exception as exc:  # pragma: no cover - 调试容错
            logger.exception("build_step15_power_series failed during export: %s", exc)
            step15_df = pd.DataFrame()

        ops_rows: List[Dict[str, Any]] = []
        for dkey, ops in sorted(daily_ops.items(), key=lambda kv: kv[0]):
            row = {"date": dkey}
            for h in range(24):
                keyh = f"h{h:02d}"
                row[keyh] = ops[h] if h < len(ops) else None
            ops_rows.append(row)

        xlsx_path, summary_csv_path = cycles_svc.export_excel_report(
            out_dir,
            source_filename=filename or "points_payload",
            days=[d.model_dump() for d in days],
            months=[{"year_month": m.year_month, "cycles": m.cycles} for m in months],
            year={"year": year_summary.year, "cycles": year_summary.cycles},
            monthly_prices=monthly_prices if isinstance(monthly_prices, list) else None,
            limit_info=limit_info,
            qc_dict=qc.model_dump(),
            window_debug=window_debug,
            ops_by_hour=ops_rows,
            runs_debug=runs_debug,
            profit_summary=profit_summary,
            step15_df=step15_df,
            energy_formula=energy_formula,
        )
        excel_rel = str(xlsx_path.as_posix())
        if summary_csv_path:
            try:
                qc.notes.append(f"summary csv: {summary_csv_path.as_posix()}")
            except Exception:
                pass
    except Exception as exc:  # pragma: no cover
        logger.exception("export excel failed: %s", exc)
        excel_rel = None
        qc.notes.append("export excel failed: " + str(exc))

    return StorageCyclesResponse(
        year=year_summary,
        months=months,
        days=days,
        qc=qc,
        excel_path=excel_rel,
        window_month_summary=window_month_summary or None,
        tip_discharge_summary=tip_summary_dict,
    )


@app.post("/api/storage/cycles/curves", response_model=StorageCurvesResponse)
async def compute_storage_curves(
    body: Dict[str, Any] = Body(..., description="payload + date"),
) -> StorageCurvesResponse:
    """根据与 /cycles 相同的 payload + 指定 date，返回原始负荷与储能后的对比曲线."""

    if not isinstance(body, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="body must be an object")

    payload_obj = body.get("payload")
    date_str = body.get("date")
    if not isinstance(payload_obj, (dict, str)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload is required")
    if not isinstance(date_str, str) or len(date_str) != 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date must be YYYY-MM-DD")

    # 为了避免与 /cycles 行为不一致，这里仅支持 points 模式，不再处理上传文件
    payload_dict = _parse_payload(payload_obj)
    series_15m = _build_series_15m_from_payload(payload_dict, file_bytes=None)

    # 储能配置与策略
    storage_cfg = payload_dict.get("storage") if isinstance(payload_dict, dict) else None
    if not isinstance(storage_cfg, dict):
        storage_cfg = {}

    strategy_src = payload_dict.get("strategySource") if isinstance(payload_dict, dict) else None
    if not isinstance(strategy_src, dict):
        strategy_src = {}
    monthly_schedule = strategy_src.get("monthlySchedule")
    date_rules = strategy_src.get("dateRules")

    try:
        daily_ops = cycles_svc.build_daily_ops(series_15m, monthly_schedule, date_rules)
    except Exception as exc:
        logger.exception("strategy build failed (curves): %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"strategy build failed: {exc}") from exc

    # TOU 价格
    monthly_prices = payload_dict.get("monthlyTouPrices") if isinstance(payload_dict, dict) else None
    try:
        price_series, _ = cycles_svc.build_price_series(
            series_15m,
            monthly_schedule=monthly_schedule,
            date_rules=date_rules,
            monthly_prices=monthly_prices,
        )
    except Exception as exc:
        logger.exception("TOU map failed (curves): %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"TOU map failed: {exc}") from exc

    # 限值信息（与 /cycles 保持一致）
    metering_mode = storage_cfg.get("metering_mode", "monthly_demand_max")
    transformer_capacity_kva = storage_cfg.get("transformer_capacity_kva")
    transformer_power_factor = storage_cfg.get("transformer_power_factor")
    limit_info = cycles_svc.compute_limit_info(
        series_15m,
        metering_mode=metering_mode,
        transformer_capacity_kva=transformer_capacity_kva,
        transformer_power_factor=transformer_power_factor,
    )

    energy_formula = storage_cfg.get("energy_formula", "physics") or "physics"

    # 为了与 /api/storage/cycles 行为保持一致，这里也构造 daily_masks 和 window_debug，
    # 使 step15 功率/能量计算与次数计算使用同一套窗口约束。
    merge_threshold_minutes = storage_cfg.get("merge_threshold_minutes", 30)
    try:
        daily_masks, _, window_debug = cycles_svc.build_daily_cycles_masks(
            daily_ops,
            merge_threshold_minutes=merge_threshold_minutes,
            wrap_across_midnight=True,
        )
        _, window_debug = cycles_svc.compute_window_avg_days_with_debug(
            series_15m,
            daily_masks=daily_masks,
            storage_cfg=storage_cfg,
            limit_info=limit_info,
            energy_formula=energy_formula,
        )
    except Exception as exc:  # pragma: no cover - 降级为无窗口目标的行为
        logger.exception("window_debug build failed (curves): %s", exc)
        daily_masks = {}
        window_debug = None

    # 重用 step15 功率/电量序列
    df = cycles_svc.build_step15_power_series(
        series_15m,
        daily_ops=daily_ops,
        limit_info=limit_info,
        storage_cfg=storage_cfg,
        price_series=price_series,
        window_debug=window_debug,
        energy_formula=energy_formula,
    )
    if df.empty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no data points after preprocessing")

    # 过滤到指定日期
    try:
        df_day = df[df["date_str"] == date_str]
    except Exception:
        df_day = pd.DataFrame()
    if df_day.empty:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"no data for date={date_str}")

    # 原始负荷与储能后的负荷
    dt_hours = 0.25
    if energy_formula == "physics":
        p_grid_effect = df_day["p_grid_effect_physics_kw"]
    else:
        p_grid_effect = df_day["p_grid_effect_sample_kw"]

    load_original = df_day["load_kw"]
    load_with_storage = load_original + p_grid_effect

    points_original: List[StorageCurvesPoint] = []
    points_with_storage: List[StorageCurvesPoint] = []
    for ts, row in df_day.iterrows():
        ts_iso = pd.to_datetime(ts).to_pydatetime().isoformat()
        points_original.append(
            StorageCurvesPoint(timestamp=ts_iso, load_kw=float(row["load_kw"] or 0.0)),
        )
        points_with_storage.append(
            StorageCurvesPoint(timestamp=ts_iso, load_kw=float(row["load_kw"] + p_grid_effect.loc[ts])),
        )

    # 关键指标汇总
    max_demand_original_kw = float(load_original.max() or 0.0)
    max_demand_new_kw = float(load_with_storage.max() or 0.0)
    max_demand_reduction_kw = max_demand_original_kw - max_demand_new_kw
    max_demand_reduction_ratio = (
        max_demand_reduction_kw / max_demand_original_kw if max_demand_original_kw > 0 else 0.0
    )

    # 分 TOU 分段的电量与电费
    energy_by_tier_original: Dict[str, float] = {}
    energy_by_tier_new: Dict[str, float] = {}
    bill_by_tier_original: Dict[str, float] = {}
    bill_by_tier_new: Dict[str, float] = {}

    for _, row in df_day.iterrows():
        tier = str(row.get("tier") or "")
        if not tier:
            continue
        load_orig = float(row["load_kw"] or 0.0)
        load_new = float(load_orig + p_grid_effect.loc[row.name])
        e_orig = load_orig * dt_hours
        e_new = load_new * dt_hours
        price = row.get("price")
        try:
            price_val = float(price) if price is not None and pd.notna(price) else 0.0
        except Exception:
            price_val = 0.0

        energy_by_tier_original[tier] = energy_by_tier_original.get(tier, 0.0) + e_orig
        energy_by_tier_new[tier] = energy_by_tier_new.get(tier, 0.0) + e_new
        bill_by_tier_original[tier] = bill_by_tier_original.get(tier, 0.0) + e_orig * price_val
        bill_by_tier_new[tier] = bill_by_tier_new.get(tier, 0.0) + e_new * price_val

    # 使用已实现的收益汇总，提取该日主口径收益
    profit_day_main: StorageProfit | None = None
    try:
        if energy_formula == "physics":
            e_in_col = "e_in_physics_kwh"
            e_out_col = "e_out_physics_kwh"
        else:
            e_in_col = "e_in_sample_kwh"
            e_out_col = "e_out_sample_kwh"

        e_in = float(df_day[e_in_col].sum())
        e_out = float(df_day[e_out_col].sum())
        price_series_day = df_day["price"].fillna(0.0)
        cost = float((df_day[e_in_col] * price_series_day).sum())
        revenue = float((df_day[e_out_col] * price_series_day).sum())
        profit_val = revenue - cost
        profit_day_main = StorageProfit(
            revenue=revenue,
            cost=cost,
            profit=profit_val,
            discharge_energy_kwh=e_out,
            charge_energy_kwh=e_in,
            profit_per_kwh=(profit_val / e_out) if e_out > 0 else 0.0,
        )
    except Exception:
        profit_day_main = None

    summary = StorageCurvesSummary(
        max_demand_original_kw=max_demand_original_kw,
        max_demand_new_kw=max_demand_new_kw,
        max_demand_reduction_kw=max_demand_reduction_kw,
        max_demand_reduction_ratio=max_demand_reduction_ratio,
        energy_by_tier_original=energy_by_tier_original,
        energy_by_tier_new=energy_by_tier_new,
        bill_by_tier_original=bill_by_tier_original,
        bill_by_tier_new=bill_by_tier_new,
        profit_day_main=profit_day_main,
    )

    return StorageCurvesResponse(
        date=date_str,
        points_original=points_original,
        points_with_storage=points_with_storage,
        summary=summary,
    )


@app.post("/api/deepseek/project-summary", response_model=ProjectSummaryResponse)
async def generate_project_summary_endpoint(
    request: ProjectSummaryRequest,
) -> ProjectSummaryResponse:
    """
    生成项目评估报告（基于 DeepSeek）。
    
    前端传入项目基本信息与各模块可选数据，后端调用 DeepSeek API 生成 Markdown 报告。
    """
    from datetime import datetime, timezone
    from .services.deepseek_summary import generate_project_summary, DeepSeekError
    
    # 构建项目信息
    project_info = {
        "name": request.project_name,
        "location": request.project_location,
        "periodStart": request.period_start,
        "periodEnd": request.period_end,
        "periodDescription": f"{request.period_start} 至 {request.period_end}",
        "loadDataSource": "用户提供的 CSV 数据",
        "touSource": "当前 TOU 配置",
        "simulationVersion": "v1.0",
        "reportDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    
    try:
        markdown_report = await generate_project_summary(
            project_info=project_info,
            load_profile=request.load_profile,
            tou_config=request.tou_config,
            storage_config=request.storage_config,
            storage_results=request.storage_results,
            quality_report=request.quality_report,
        )
    except DeepSeekError as exc:
        logger.exception("生成项目评估报告失败")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成报告失败: {str(exc)}",
        ) from exc
    
    # 生成报告 ID
    report_id = f"report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    
    # 从 storage_results 提取关键摘要（如有）
    summary_dict = {}
    if request.storage_results:
        summary_dict = {
            "firstYearRevenue": request.storage_results.get("firstYearRevenueDetail", ""),
            "dailyCycles": request.storage_results.get("dailyCycles", ""),
            "utilizationHoursRange": request.storage_results.get("utilizationHoursRangeDetail", ""),
            "loadDataCompleteness": request.quality_report.get("loadMissingRateDescription", "") if request.quality_report else "",
            "overallConclusion": "请参考报告正文",
        }
    
    return ProjectSummaryResponse(
        report_id=report_id,
        project_name=request.project_name,
        period_start=request.period_start,
        period_end=request.period_end,
        generated_at=datetime.now(timezone.utc).isoformat(),
        markdown=markdown_report,
        summary=summary_dict,
    )
