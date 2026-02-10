from __future__ import annotations

from backend.services.loader import load_dataframe


def test_load_dataframe_parses_gbk_csv_with_cn_headers() -> None:
    # 常见现场导出：GBK/ANSI 编码，表头为「数据日期,时间,功率(KW)」
    csv_text = "\n".join(
        [
            "数据日期,时间,功率(KW)",
            "9/1/2024,0:00,1815.32",
            "9/1/2024,1:00,2135.32",
            "9/1/2024,2:00,2135.32",
        ]
    )
    file_bytes = csv_text.encode("gbk")

    df = load_dataframe(file_bytes)

    assert list(df.columns) == ["timestamp", "load"]
    assert len(df) == 3
    assert df["timestamp"].notna().all()
    assert df["load"].notna().all()
    assert float(df["load"].iloc[0]) == 1815.32

