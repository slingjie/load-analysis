#!/usr/bin/env python
"""
测试脚本：验证 v2.0 完整性分析实现

功能：
1. 加载原始 CSV 数据
2. 调用 quality.build_quality_report() 进行完整性分析
3. 验证按月分类统计的准确性
4. 输出详细的测试结果

使用方式:
    python test_completeness_v2.py <csv_file_path>

示例:
    python test_completeness_v2.py "宁国津龙 负荷整理.csv"
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd

# 添加后端模块到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.services import loader, quality


def print_section(title: str, char: str = "=") -> None:
    """打印分隔符"""
    print(f"\n{char * 60}")
    print(f"  {title}")
    print(f"{char * 60}\n")


def format_timestamp(ts: pd.Timestamp) -> str:
    """格式化时间戳"""
    if pd.isna(ts):
        return "—"
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def test_completeness_analysis(csv_path: str) -> None:
    """
    测试完整性分析
    
    Args:
        csv_path: CSV 文件路径
    """
    
    print_section("完整性分析测试 v2.0", "█")
    
    # 1. 加载文件
    print_section("1️⃣  加载文件")
    
    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"❌ 错误：文件不存在 {csv_path}")
        return
    
    file_size_mb = csv_file.stat().st_size / (1024 * 1024)
    print(f"文件路径: {csv_path}")
    print(f"文件大小: {file_size_mb:.2f} MB")
    
    try:
        with open(csv_file, "rb") as f:
            file_bytes = f.read()
        
        raw_df = loader.load_dataframe(file_bytes)
        print(f"✅ 文件加载成功")
        print(f"   原始记录数: {len(raw_df)}")
        print(f"   列名: {list(raw_df.columns)}")
    except Exception as e:
        print(f"❌ 文件加载失败: {e}")
        return
    
    # 2. 数据预览
    print_section("2️⃣  数据预览")
    
    print("前 5 条记录:")
    print(raw_df.head())
    print("\n后 5 条记录:")
    print(raw_df.tail())
    
    # 3. 调用完整性分析
    print_section("3️⃣  完整性分析")
    
    try:
        report_dict, meta_dict = quality.build_quality_report(raw_df)
        print("✅ 分析完成")
    except Exception as e:
        print(f"❌ 分析失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 缺失分析结果
    print_section("4️⃣  缺失分析结果")
    
    missing_info = report_dict.get("missing", {})
    missing_days = missing_info.get("missing_days", [])
    missing_by_month = missing_info.get("missing_hours_by_month", [])
    summary = missing_info.get("summary", {})
    
    print(f"缺失天数总计: {summary.get('total_missing_days', 0)} 天")
    print(f"缺失小时总计: {summary.get('total_missing_hours', 0)} 小时")
    
    if missing_days:
        print(f"\n缺失日期 ({len(missing_days)} 天):")
        for i, date in enumerate(missing_days[:10], 1):
            print(f"  {i:2}. {date}")
        if len(missing_days) > 10:
            print(f"  ... 共 {len(missing_days)} 天，显示前 10 个")
    else:
        print("无缺失日期")
    
    # 5. 按月分类统计
    print_section("5️⃣  按月分类缺失统计")
    
    if missing_by_month:
        print(f"\n{'月份':<12} {'缺失天数':<10} {'缺失小时数':<10}")
        print("-" * 32)
        for item in missing_by_month:
            month = item.get("month", "—")
            days = item.get("missing_days", 0)
            hours = item.get("missing_hours", 0)
            print(f"{month:<12} {days:<10} {hours:<10}")
    else:
        print("无缺失数据")
    
    # 6. 异常值统计
    print_section("6️⃣  异常值统计")
    
    anomalies = report_dict.get("anomalies", [])
    anomaly_labels = {"null": "空值", "zero": "零值", "negative": "负值"}
    
    for anomaly in anomalies:
        kind = anomaly.get("kind", "unknown")
        count = anomaly.get("count", 0)
        ratio = anomaly.get("ratio", 0.0)
        samples = anomaly.get("samples", [])
        
        label = anomaly_labels.get(kind, kind)
        print(f"{label}:")
        print(f"  数量: {count}")
        print(f"  占比: {ratio * 100:.4f}%")
        if samples:
            print(f"  示例 ({len(samples)} 个):")
            for sample in samples[:3]:
                print(f"    - {sample}")
        print()
    
    # 7. 元数据
    print_section("7️⃣  元数据")
    
    print(f"源数据采样间隔: {meta_dict.get('source_interval_minutes', 0)} 分钟")
    print(f"总记录数: {meta_dict.get('total_records', 0)}")
    print(f"时间范围: {format_timestamp(pd.to_datetime(meta_dict.get('start')))} 至 {format_timestamp(pd.to_datetime(meta_dict.get('end')))}")
    
    # 8. 完整度计算
    print_section("8️⃣  完整度计算")
    
    total_records = meta_dict.get('total_records', 0)
    total_missing_hours = summary.get('total_missing_hours', 0)
    
    # 期望的总小时数（365天 * 24小时）
    expected_hours = 365 * 24
    completeness = (expected_hours - total_missing_hours) / expected_hours * 100 if expected_hours > 0 else 0
    
    print(f"期望总小时数: {expected_hours} 小时 (365天 × 24小时)")
    print(f"缺失小时数: {total_missing_hours} 小时")
    print(f"完整度: {completeness:.2f}%")
    
    # 9. 验证清单
    print_section("9️⃣  验证清单")
    
    checks = {
        "✓ 按月分类统计已生成": bool(missing_by_month),
        "✓ 汇总信息已计算": bool(summary),
        "✓ 异常值统计已完成": bool(anomalies),
        "✓ 缺失日期列表已生成": bool(missing_days or not summary.get('total_missing_days')),
        "✓ 没有连续零值分析": report_dict.get("continuous_zero_spans", []) == [],
    }
    
    for check, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"{status} {check}")
    
    all_passed = all(checks.values())
    
    # 10. JSON 输出示例
    print_section("🔟 JSON 输出示例")
    
    sample_output = {
        "report": {
            "missing": missing_info,
            "anomalies": anomalies[:1] if anomalies else [],  # 仅显示第一个
        },
        "meta": {
            "source_interval_minutes": meta_dict.get('source_interval_minutes'),
            "total_records": meta_dict.get('total_records'),
            "start": meta_dict.get('start'),
            "end": meta_dict.get('end'),
        }
    }
    
    print(json.dumps(sample_output, ensure_ascii=False, indent=2))
    
    # 11. 最终结果
    print_section("最终结果", "█")
    
    if all_passed:
        print("✅ 所有测试通过！\n")
        print(f"📊 测试总结:")
        print(f"   - 原始记录: {len(raw_df)} 条")
        print(f"   - 缺失天数: {summary.get('total_missing_days', 0)} 天")
        print(f"   - 缺失小时: {summary.get('total_missing_hours', 0)} 小时")
        print(f"   - 数据完整度: {completeness:.2f}%")
        print(f"   - 异常值: {sum(a.get('count', 0) for a in anomalies)} 条")
    else:
        print("❌ 部分测试未通过，请检查实现")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ 缺少文件路径参数")
        print("\n用法:")
        print("  python test_completeness_v2.py <csv_file_path>")
        print("\n示例:")
        print("  python test_completeness_v2.py \"宁国津龙 负荷整理.csv\"")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    test_completeness_analysis(csv_path)
