from __future__ import annotations

import json
import logging
from typing import List

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from .schemas import (
    CleanedPoint,
    LoadAnalysisResponse,
    MetaInfo,
    QualityReport,
    StorageCyclesDay,
    StorageCyclesMonth,
    StorageCyclesResponse,
    StorageCyclesYear,
    StorageQC,
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
    """Upload file -> parse -> quality report + raw points."""
    filename = file.filename or "<uploaded>"
    try:
        file_bytes = await file.read()
    except Exception as exc:  # pragma: no cover
        logger.exception("read file failed: %s", filename)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="failed to read upload file") from exc

    logger.debug("received upload: name=%s size=%s bytes content_type=%s", filename, len(file_bytes), getattr(file, "content_type", None))

    try:
        raw_df = loader.load_dataframe(file_bytes)
    except loader.LoaderError as exc:
        logger.exception("parse file failed: %s", filename)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # Quality stats (no cleaning)
    report_dict, meta_dict = quality.build_quality_report(raw_df)

    # Raw points passthrough (timestamp, load -> load_kwh)
    cleaned_points: List[CleanedPoint] = []
    if "timestamp" in raw_df.columns and "load" in raw_df.columns:
        raw_df_copy = raw_df.copy()
        raw_df_copy["timestamp"] = pd.to_datetime(raw_df_copy["timestamp"], errors="coerce")
        raw_df_copy["load"] = pd.to_numeric(raw_df_copy["load"], errors="coerce")
        for _, row in raw_df_copy.iterrows():
            ts: pd.Timestamp = row["timestamp"]  # type: ignore
            load: float = row["load"]  # type: ignore
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
    return {"status": "ok"}


@app.post("/api/storage/cycles", response_model=StorageCyclesResponse)
async def compute_storage_cycles(
    file: UploadFile | None = File(None),
    payload: str = Form(...),
) -> StorageCyclesResponse:
    """Storage cycles (window_avg). Supports payload.points interop with Load Analysis page."""
    filename: str | None = None
    file_bytes: bytes | None = None

    if file is not None:
        try:
            filename = file.filename or "<uploaded>"
            file_bytes = await file.read()
        except Exception as exc:  # pragma: no cover
            logger.exception("read file failed: %s", filename)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="failed to read upload file") from exc

    # parse payload
    try:
        payload_obj = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(payload_obj, dict):
            raise ValueError("payload must be a JSON object string")
    except Exception as exc:
        logger.exception("payload parse failed: %s", payload[:200] if isinstance(payload, str) else type(payload))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload is not a valid JSON object string") from exc

    # build 15min series: prefer points, fallback to upload file
    points = payload_obj.get("points") if isinstance(payload_obj, dict) else None
    if isinstance(points, list) and points:
        try:
            series_15m = cycles_svc.parse_points_series(points)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"points parse failed: {exc}") from exc
    else:
        if not file_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no upload file or points provided")
        try:
            series_15m = cycles_svc.parse_load_series(file_bytes)
        except Exception as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # storage config
    storage_cfg = payload_obj.get("storage") if isinstance(payload_obj, dict) else None
    if not isinstance(storage_cfg, dict):
        storage_cfg = {}
    metering_mode = storage_cfg.get("metering_mode", "monthly_demand_max")
    transformer_capacity_kva = storage_cfg.get("transformer_capacity_kva")
    transformer_power_factor = storage_cfg.get("transformer_power_factor")
    merge_threshold_minutes = storage_cfg.get("merge_threshold_minutes", 30)

    # limit info
    limit_info = cycles_svc.compute_limit_info(
        series_15m,
        metering_mode=metering_mode,
        transformer_capacity_kva=transformer_capacity_kva,
        transformer_power_factor=transformer_power_factor,
    )

    # strategy -> masks
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
        extra_notes = ["strategy build failed: " + str(exc)]
    else:
        extra_notes = []

    # TOU mapping (for QC)
    monthly_prices = payload_obj.get("monthlyTouPrices") if isinstance(payload_obj, dict) else None
    try:
        _price_series, missing_points_cnt = cycles_svc.build_price_series(
            series_15m,
            monthly_schedule=monthly_schedule,
            date_rules=date_rules,
            monthly_prices=monthly_prices,
        )
    except Exception as exc:
        logger.exception("TOU map failed: %s", exc)
        missing_points_cnt = 0
        extra_notes.append("TOU map failed: " + str(exc))

    # compute (window_avg)
    energy_formula = storage_cfg.get("energy_formula", "physics") or "physics"
    try:
        days_raw, window_debug = cycles_svc.compute_window_avg_days_with_debug(
            series_15m,
            daily_masks=daily_masks if 'daily_masks' in locals() else {},
            storage_cfg=storage_cfg,
            limit_info=limit_info,
            energy_formula=energy_formula,
        )
    except Exception as exc:
        logger.exception("window_avg compute failed: %s", exc)
        days_raw, window_debug = [], []

    # response
    days: list[StorageCyclesDay] = [StorageCyclesDay(date=d["date"], cycles=float(d["cycles"])) for d in days_raw]
    month_map: dict[str, float] = {}
    year_set: set[int] = set()
    for d in days_raw:
        ym = d["date"][:7]
        month_map[ym] = month_map.get(ym, 0.0) + float(d["cycles"])
        try:
            year_set.add(int(d["date"][:4]))
        except Exception:
            pass
    months: list[StorageCyclesMonth] = [StorageCyclesMonth(year_month=ym, cycles=float(cyc)) for ym, cyc in sorted(month_map.items())]
    total_cycles = sum(float(m.cycles) for m in months)
    year_val = list(year_set)[0] if len(year_set) == 1 else 0
    year_summary = StorageCyclesYear(year=year_val, cycles=float(total_cycles))
    qc = StorageQC(
        notes=(limit_info.get("notes", []) + extra_notes),
        limit_mode=limit_info.get("limit_mode"),
        transformer_limit_kw=limit_info.get("transformer_limit_kw"),
        monthly_demand_max=limit_info.get("monthly_demand_max", []),
        merged_segments=int(merged_cnt) if 'merged_cnt' in locals() else 0,
        missing_prices=int(missing_points_cnt),
    )

    logger.info("/api/storage/cycles: source=%s points=%s", filename, isinstance(points, list) and len(points))
    logger.info("/api/storage/cycles done: days=%s months=%s year_cycles=%s", len(days), len(months), total_cycles)

    # export excel
    from datetime import datetime as _dt
    from pathlib import Path as _Path
    ts_dir = _dt.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _Path("outputs") / ts_dir
    try:
        ops_rows = []
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
        )
        excel_rel = str(xlsx_path.as_posix())
        # 将 summary CSV 路径写入备注，便于前端查看
        if summary_csv_path:
            try:
                qc.notes.append(f"summary csv: {summary_csv_path.as_posix()}")
            except Exception:
                pass
    except Exception as exc:
        logger.exception("export excel failed: %s", exc)
        excel_rel = None
        qc.notes.append("export excel failed: " + str(exc))

    return StorageCyclesResponse(
        year=year_summary,
        months=months,
        days=days,
        qc=qc,
        excel_path=excel_rel,
    )
