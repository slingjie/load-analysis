#!/usr/bin/env python3
"""
直接调用后端模块进行清洗报告功能测试
（不通过HTTP，直接加载文件并执行清洗）
"""
import sys
import json
from pathlib import Path

# 添加后端模块到路径
sys.path.insert(0, r'd:\Desktop\ai\1028负荷展示和tou配置')

from backend.services import loader, cleaner, quality

TEST_FILE = r"d:\Desktop\ai\1028负荷展示和tou配置\宁国津龙 负荷整理.csv"

def test_cleaner_direct():
    """直接调用模块测试清洗功能"""
    print("=" * 80)
    print("数据清洗报告功能测试（直接调用模块）")
    print("=" * 80)
    print(f"\n【文件信息】")
    print(f"测试文件: {TEST_FILE}")
    
    try:
        # 步骤1: 加载文件
        print(f"\n【步骤1】加载CSV文件...")
        with open(TEST_FILE, 'rb') as f:
            file_bytes = f.read()
        print(f"  文件大小: {len(file_bytes)} 字节")
        
        # 步骤2: 解析文件
        print(f"\n【步骤2】解析文件...")
        raw_df = loader.load_dataframe(file_bytes)
        print(f"✅ 解析成功")
        print(f"  原始记录数: {len(raw_df)} 条")
        print(f"  列名: {list(raw_df.columns)}")
        print(f"  前5行:")
        for idx, row in raw_df.head().iterrows():
            print(f"    {row['timestamp']} → {row['load']}")
        
        # 步骤3: 清洗与聚合
        print(f"\n【步骤3】清洗与小时级聚合...")
        clean_result = cleaner.clean_and_aggregate(raw_df)
        print(f"✅ 清洗成功")
        print(f"  推断采样间隔: {clean_result.interval_minutes} 分钟")
        print(f"  清洗后小时级数据点: {len(clean_result.hourly_energy)} 条")
        print(f"  时间范围: {clean_result.hourly_energy.index.min()} 至 {clean_result.hourly_energy.index.max()}")
        
        # 步骤4: 生成质量报告
        print(f"\n【步骤4】生成数据质量报告...")
        report_dict, meta_dict = quality.build_quality_report(raw_df, clean_result)
        print(f"✅ 报告生成成功")
        
        # 输出基础信息
        print(f"\n  📋 基础信息:")
        print(f"    • 原始记录数: {meta_dict.get('total_records')}")
        print(f"    • 推断采样间隔: {meta_dict.get('source_interval_minutes')} 分钟")
        print(f"    • 时间范围: {meta_dict.get('start')} 至 {meta_dict.get('end')}")
        
        # 输出缺失分析
        print(f"\n  📊 缺失情况分析:")
        missing = report_dict.get('missing', {})
        missing_days = missing.get('missing_days', [])
        missing_hours = missing.get('missing_hours', [])
        
        print(f"    • 缺失日期: {len(missing_days)} 天")
        if missing_days:
            print(f"      示例日期: {missing_days[:5]}")
            if len(missing_days) > 5:
                print(f"      ... 还有 {len(missing_days) - 5} 天")
        else:
            print(f"      ✓ 无缺失日期")
        
        missing_hour_count = sum(len(h.get('hours', [])) for h in missing_hours)
        print(f"    • 缺失小时: {missing_hour_count} 小时")
        if missing_hours:
            print(f"      示例缺失日期:")
            for item in missing_hours[:3]:
                print(f"        {item['date']} 缺失: {item['hours']}")
            if len(missing_hours) > 3:
                print(f"        ... 还有 {len(missing_hours) - 3} 天")
        else:
            print(f"      ✓ 无缺失小时")
        
        # 输出异常值统计
        print(f"\n  ⚠️  异常值统计:")
        anomalies = report_dict.get('anomalies', [])
        
        anomaly_labels = {
            'null': '空值(Null/NaN)',
            'zero': '零值(Zero)',
            'negative': '负值(Negative)'
        }
        
        for anomaly in anomalies:
            kind = anomaly.get('kind')
            count = anomaly.get('count')
            ratio = anomaly.get('ratio', 0)
            samples = anomaly.get('samples', [])
            
            label = anomaly_labels.get(kind, kind)
            print(f"    • {label}:")
            print(f"      数量: {count} 条")
            print(f"      占比: {ratio * 100:.4f}%")
            if samples:
                print(f"      示例: {samples[:2]}")
        
        # 输出连续零值时段
        print(f"\n  🔴 连续零值时段:")
        zero_spans = report_dict.get('continuous_zero_spans', [])
        print(f"    共检测到 {len(zero_spans)} 个连续零值时段")
        if zero_spans:
            for i, span in enumerate(zero_spans[:5], 1):
                start_time = span.get('start')
                end_time = span.get('end')
                hours = span.get('length_hours')
                print(f"    {i}. {start_time[:16]} ~ {end_time[:16]}, 共 {hours} 小时")
            if len(zero_spans) > 5:
                print(f"    ... 还有 {len(zero_spans) - 5} 个时段")
        else:
            print(f"    ✓ 无连续零值时段")
        
        # 总体评估
        print(f"\n【步骤5】总体评估")
        total_records = meta_dict.get('total_records', 0)
        total_anomalies = sum(a.get('count', 0) for a in anomalies)
        anomaly_ratio = (total_anomalies / total_records * 100) if total_records else 0
        
        print(f"  ✓ 数据完整性:")
        print(f"    - 缺失日期: {len(missing_days)} 天")
        print(f"    - 缺失小时: {missing_hour_count} 小时")
        
        print(f"  ✓ 数据质量:")
        print(f"    - 异常记录: {total_anomalies} 条 ({anomaly_ratio:.4f}%)")
        print(f"    - 零值时段: {len(zero_spans)} 个")
        
        print(f"  ✓ 清洗效率:")
        print(f"    - 原始记录: {total_records} 条")
        print(f"    - 清洗后: {len(clean_result.hourly_energy)} 条小时级数据")
        efficiency = (len(clean_result.hourly_energy) / total_records * 100) if total_records else 0
        print(f"    - 转换效率: {efficiency:.2f}%")
        
        # 完整JSON输出
        print(f"\n【步骤6】完整JSON报告")
        print(f"\n{json.dumps(report_dict, indent=2, ensure_ascii=False)}")
        
        print(f"\n【测试结论】✅ 清洗报告功能测试通过")
        print("=" * 80)
        
        return True
        
    except FileNotFoundError as e:
        print(f"❌ 文件未找到: {e}")
        return False
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_cleaner_direct()
    sys.exit(0 if success else 1)
