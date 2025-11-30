#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
质量报告对比测试脚本
直接调用后端质量分析模块，生成完整报告并与前端结果对比
"""

import sys
import os
import json
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd
from backend.services.cleaner import load_and_clean
from backend.services.quality import build_quality_report


def test_quality_report():
    """运行完整质量报告测试"""
    
    # 文件路径
    csv_file = Path(__file__).parent / "宁国津龙 负荷整理.csv"
    
    if not csv_file.exists():
        print(f"❌ 文件不存在: {csv_file}")
        return
    
    print("=" * 80)
    print("📊 负荷数据质量报告测试")
    print("=" * 80)
    print(f"📁 文件: {csv_file.name}")
    print(f"📏 文件大小: {csv_file.stat().st_size:,} 字节")
    
    # 1. 加载原始数据
    print("\n[步骤1] 加载原始数据...")
    try:
        raw_df = pd.read_csv(csv_file, encoding='gbk')
        print(f"✅ 成功读取 {len(raw_df)} 条记录")
        print(f"📋 列名: {list(raw_df.columns)}")
        print(f"📊 数据类型:\n{raw_df.dtypes}")
        print(f"\n前5行数据:")
        print(raw_df.head())
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return
    
    # 2. 数据清洗与聚合
    print("\n[步骤2] 数据清洗与聚合...")
    try:
        result = load_and_clean(raw_df)
        print(f"✅ 清洗完成")
        print(f"📊 原始数据: {len(raw_df)} 条 (15分钟间隔)")
        print(f"📊 清洗后: {len(result.hourly_energy)} 条 (1小时间隔)")
        print(f"⏱️  缺失小时数: {result.missing_hours.sum()}")
        print(f"📈 时间范围: {result.hourly_energy.index.min()} ~ {result.hourly_energy.index.max()}")
    except Exception as e:
        print(f"❌ 清洗失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 3. 生成质量报告
    print("\n[步骤3] 生成质量报告...")
    try:
        report, meta = build_quality_report(raw_df)
        print(f"✅ 报告生成完成")
    except Exception as e:
        print(f"❌ 报告生成失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 4. 输出详细分析结果
    print("\n" + "=" * 80)
    print("📋 缺失情况分析")
    print("=" * 80)
    
    missing_info = report["missing"]
    missing_days = missing_info.get("missing_days", [])
    missing_hours_by_month = missing_info.get("missing_hours_by_month", [])
    summary = missing_info.get("summary", {})
    
    print(f"缺失天数: {summary.get('total_missing_days', 0)} 天")
    print(f"缺失小时数: {summary.get('total_missing_hours', 0)} 小时")
    
    if missing_days:
        print(f"\n缺失的日期:")
        for day in missing_days:
            print(f"  • {day}")
    else:
        print(f"\n缺失的日期: 无")
    
    if missing_hours_by_month:
        print(f"\n按月缺失统计:")
        for month_info in missing_hours_by_month:
            month = month_info.get("month", "未知")
            missing_days_cnt = month_info.get("missing_days", 0)
            missing_hours_cnt = month_info.get("missing_hours", 0)
            print(f"  • {month}: {missing_days_cnt} 天 ({missing_hours_cnt} 小时)")
    
    # 5. 异常值分析
    print("\n" + "=" * 80)
    print("⚠️ 异常值分析")
    print("=" * 80)
    
    anomalies = report.get("anomalies", [])
    for anomaly in anomalies:
        kind = anomaly.get("kind", "未知")
        count = anomaly.get("count", 0)
        ratio = anomaly.get("ratio", 0)
        samples = anomaly.get("samples", [])
        
        kind_cn = {"null": "空值", "zero": "零值", "negative": "负值"}.get(kind, kind)
        print(f"\n{kind_cn}:")
        print(f"  数量: {count} 条")
        print(f"  占比: {ratio * 100:.4f}%")
        
        if samples:
            print(f"  示例时间戳:")
            for sample in samples[:5]:
                print(f"    • {sample}")
            if len(samples) > 5:
                print(f"    ... 还有 {len(samples) - 5} 个")
        else:
            print(f"  示例: 无")
    
    # 6. 连续零值时段
    print("\n" + "=" * 80)
    print("🔴 连续零值时段")
    print("=" * 80)
    
    zero_spans = report.get("continuous_zero_spans", [])
    if zero_spans:
        print(f"检测到 {len(zero_spans)} 个连续零值时段:")
        for span in zero_spans:
            start = span.get("start", "未知")
            end = span.get("end", "未知")
            length = span.get("length_hours", 0)
            print(f"  • {start} ~ {end} ({length} 小时)")
    else:
        print("无连续零值时段")
    
    # 7. 元数据
    print("\n" + "=" * 80)
    print("📊 元数据")
    print("=" * 80)
    
    print(f"原始数据采样间隔: {meta.get('source_interval_minutes', 0)} 分钟")
    print(f"总记录数: {meta.get('total_records', 0)}")
    print(f"时间范围: {meta.get('start', '未知')} ~ {meta.get('end', '未知')}")
    
    # 8. 输出完整JSON报告
    print("\n" + "=" * 80)
    print("💾 完整JSON报告")
    print("=" * 80)
    
    full_report = {
        "report": report,
        "meta": meta
    }
    
    json_str = json.dumps(full_report, indent=2, ensure_ascii=False)
    print(json_str)
    
    # 保存到文件
    output_file = Path(__file__).parent / "test" / "quality_report_output.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 完整报告已保存到: {output_file}")
    
    # 9. 生成对比总结
    print("\n" + "=" * 80)
    print("📋 测试对比总结")
    print("=" * 80)
    
    print(f"""
关键指标对比:
  • 缺失日期数: {summary.get('total_missing_days', 0)} 天
  • 缺失小时数: {summary.get('total_missing_hours', 0)} 小时
  
异常值统计:
  • 空值: {[a['count'] for a in anomalies if a['kind']=='null'][0] if any(a['kind']=='null' for a in anomalies) else 0} 条
  • 零值: {[a['count'] for a in anomalies if a['kind']=='zero'][0] if any(a['kind']=='zero' for a in anomalies) else 0} 条
  • 负值: {[a['count'] for a in anomalies if a['kind']=='negative'][0] if any(a['kind']=='negative' for a in anomalies) else 0} 条
  
数据质量:
  ✅ 文件成功解析
  ✅ 数据完成清洗聚合
  ✅ 质量报告生成完毕
    """)


if __name__ == "__main__":
    test_quality_report()
