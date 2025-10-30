from __future__ import annotations

import logging
from typing import List

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from .schemas import CleanedPoint, LoadAnalysisResponse, MetaInfo, QualityReport
from .services import loader, quality


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
