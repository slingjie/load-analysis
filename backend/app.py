from __future__ import annotations

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
    filename = file.filename or "<uploaded>"
    try:
        file_bytes = await file.read()
    except Exception as exc:  # pragma: no cover - IO 异常极少见
        logger.exception("读取文件失败: %s", filename)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="读取上传文件失败。") from exc

    logger.debug("收到上传文件：name=%s size=%s bytes content_type=%s", filename, len(file_bytes), getattr(file, "content_type", None))

    try:
        raw_df = loader.load_dataframe(file_bytes)
    except loader.LoaderError as exc:
        logger.exception("文件解析失败：%s", filename)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # 直接对原始数据进行完整性分析，不进行数据清洗
    report_dict, meta_dict = quality.build_quality_report(raw_df)

    # 返回原始数据点（不经过清洗）
    cleaned_points: List[CleanedPoint] = []
    if "timestamp" in raw_df.columns and "load" in raw_df.columns:
        raw_df_copy = raw_df.copy()
        raw_df_copy["timestamp"] = pd.to_datetime(raw_df_copy["timestamp"], errors="coerce")
        raw_df_copy["load"] = pd.to_numeric(raw_df_copy["load"], errors="coerce")
        
        for idx, row in raw_df_copy.iterrows():
            ts: pd.Timestamp = row["timestamp"]  # type: ignore
            load: float = row["load"]  # type: ignore
            
            if not pd.isna(ts):  # type: ignore
                load_val: float = float(load) if not pd.isna(load) else 0.0  # type: ignore
                cleaned_points.append(
                    CleanedPoint(
                        timestamp=ts.to_pydatetime().isoformat(),
                        load_kwh=round(load_val, 6)
                    )
                )

    response = LoadAnalysisResponse(
        cleaned_points=cleaned_points,
        report=QualityReport.model_validate(report_dict),
        meta=MetaInfo.model_validate(meta_dict),
    )

    logger.info(
        "文件 %s 分析完成: records=%s",
        filename,
        meta_dict.get("total_records"),
    )

    return response


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


# ---- Storage cycles MVP skeleton ----
@app.post("/api/storage/cycles", response_model=StorageCyclesResponse)
async def compute_storage_cycles(
    file: UploadFile = File(...),
    payload: str = Form(...),
) -> StorageCyclesResponse:
    """储能充放次数测算接口占位版本（MVP 骨架）

    - 接收 multipart：`file` + `payload`（JSON 字符串）
    - 目前仅校验入参与基本可读性，返回占位结构，便于前后端联调
    """
    import json

    filename = file.filename or "<uploaded>"

    # 读取文件
    try:
        file_bytes = await file.read()
    except Exception as exc:  # pragma: no cover
        logger.exception("读取文件失败: %s", filename)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="读取上传文件失败。") from exc

    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空或不可读。")

    # 解析 payload（JSON 字符串）
    try:
        payload_obj = json.loads(payload) if isinstance(payload, str) else payload
        if not isinstance(payload_obj, dict):
            raise ValueError("payload 必须是 JSON 对象字符串")
    except Exception as exc:
        logger.exception("payload 解析失败: %s", payload[:200] if isinstance(payload, str) else type(payload))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="payload 不是合法的 JSON 对象字符串。") from exc

    # 占位返回（后续任务将补全实际计算逻辑与报表）
    # 基础解析与重采样（校验文件可读、形状合理）
    try:
        _series = cycles_svc.parse_load_series(file_bytes)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # 解析计费上限口径
    storage_cfg = payload_obj.get("storage") if isinstance(payload_obj, dict) else None
    if not isinstance(storage_cfg, dict):
        storage_cfg = {}
    metering_mode = storage_cfg.get("metering_mode", "monthly_demand_max")
    transformer_capacity_kva = storage_cfg.get("transformer_capacity_kva")
    transformer_power_factor = storage_cfg.get("transformer_power_factor")
    merge_threshold_minutes = storage_cfg.get("merge_threshold_minutes", 30)

    limit_info = cycles_svc.compute_limit_info(
        _series,
        metering_mode=metering_mode,
        transformer_capacity_kva=transformer_capacity_kva,
        transformer_power_factor=transformer_power_factor,
    )

    # 策略 → 日度逻辑与两次循环掩码（仅构造与统计，不参与计算占位）
    strategy_src = payload_obj.get("strategySource") if isinstance(payload_obj, dict) else None
    if not isinstance(strategy_src, dict):
        strategy_src = {}
    monthly_schedule = strategy_src.get("monthlySchedule")
    date_rules = strategy_src.get("dateRules")

    try:
        daily_ops = cycles_svc.build_daily_ops(_series, monthly_schedule, date_rules)
        daily_masks, merged_cnt, runs_debug = cycles_svc.build_daily_cycles_masks(
            daily_ops,
            merge_threshold_minutes=merge_threshold_minutes,
            wrap_across_midnight=True,
        )
    except Exception as exc:
        logger.exception("策略解析失败：%s", exc)
        # 不中断，只在 QC 提示
        extra_notes = ["策略解析失败，已忽略：" + str(exc)]
    else:
        extra_notes = []

    # TOU 段价映射到 15 分钟点位，并统计缺价点（任务5 完整实现）
    monthly_prices = payload_obj.get("monthlyTouPrices") if isinstance(payload_obj, dict) else None
    try:
        _price_series, missing_points_cnt = cycles_svc.build_price_series(
            _series,
            monthly_schedule=monthly_schedule,
            date_rules=date_rules,
            monthly_prices=monthly_prices,
        )
    except Exception as exc:
        logger.exception("TOU 段价映射失败：%s", exc)
        missing_points_cnt = 0
        extra_notes.append("TOU 段价映射失败，已忽略：" + str(exc))

    # window_avg 计算（日/月/年）
    energy_formula = storage_cfg.get("energy_formula", "physics") or "physics"
    try:
        days_raw, window_debug = cycles_svc.compute_window_avg_days_with_debug(
            _series,
            daily_masks=daily_masks if 'daily_masks' in locals() else {},
            storage_cfg=storage_cfg,
            limit_info=limit_info,
            energy_formula=energy_formula,
        )
    except Exception as exc:
        logger.exception("window_avg 计算失败：%s", exc)
        days_raw, window_debug = [], []

    # 构造响应对象
    days: list[StorageCyclesDay] = [StorageCyclesDay(date=d["date"], cycles=float(d["cycles"])) for d in days_raw]
    # 月度聚合
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
    # 年累计（若跨年则 year=0）
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

    logger.info("/api/storage/cycles 接口调用（占位返回）：file=%s size=%s bytes", filename, len(file_bytes))

    logger.info("/api/storage/cycles 计算完成：days=%s months=%s year_cycles=%s", len(days), len(months), total_cycles)

    # Excel 报表导出（静态目录 outputs/<ts>）
    from datetime import datetime as _dt
    from pathlib import Path as _Path
    ts_dir = _dt.now().strftime("%Y%m%d_%H%M%S")
    out_dir = _Path("outputs") / ts_dir
    try:
        # 构造 ops_by_hour（每小时最终运行逻辑）
        ops_rows = []
        for dkey, ops in sorted(daily_ops.items(), key=lambda kv: kv[0]):
            row = {"date": dkey}
            for h in range(24):
                keyh = f"h{h:02d}"
                row[keyh] = ops[h] if h < len(ops) else None
            ops_rows.append(row)

        xlsx_path = cycles_svc.export_excel_report(
            out_dir,
            source_filename=filename,
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
    except Exception as exc:
        logger.exception("导出 Excel 失败：%s", exc)
        excel_rel = None
        qc.notes.append("导出 Excel 失败: " + str(exc))

    return StorageCyclesResponse(
        year=year_summary,
        months=months,
        days=days,
        qc=qc,
        excel_path=excel_rel,
    )
