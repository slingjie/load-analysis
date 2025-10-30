#!/usr/bin/env python3
"""
测试数据清洗报告功能
"""
import requests
import json
import sys

# 后端API地址
API_URL = "http://127.0.0.1:8000/api/load/analyze"

# 测试文件路径
TEST_FILE = r"d:\Desktop\ai\1028负荷展示和tou配置\宁国津龙 负荷整理.csv"

def test_cleaner():
    """上传文件并获取清洗报告"""
    print("=" * 80)
    print("数据清洗报告功能测试")
    print("=" * 80)
    print(f"\n【文件信息】")
    print(f"测试文件: {TEST_FILE}")
    print(f"API端点: {API_URL}")
    
    try:
        # 上传文件
        print(f"\n【步骤1】上传文件...")
        with open(TEST_FILE, 'rb') as f:
            files = {'file': f}
            response = requests.post(API_URL, files=files, timeout=60)
        
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code != 200:
            print(f"❌ 请求失败: {response.text}")
            return False
        
        # 解析响应
        data = response.json()
        print("✅ 请求成功")
        
        # 输出元数据
        print(f"\n【步骤2】基础信息统计")
        meta = data.get('meta', {})
        print(f"  原始记录数: {meta.get('total_records')} 条")
        print(f"  推断采样间隔: {meta.get('source_interval_minutes')} 分钟")
        print(f"  时间范围: {meta.get('start')} 至 {meta.get('end')}")
        
        # 清洗后数据点
        cleaned_points = data.get('cleaned_points', [])
        print(f"  清洗后数据点: {len(cleaned_points)} 条")
        
        # 输出质量报告
        print(f"\n【步骤3】数据质量分析报告")
        report = data.get('report', {})
        
        # 缺失分析
        print(f"\n  📊 缺失情况分析:")
        missing = report.get('missing', {})
        missing_days = missing.get('missing_days', [])
        missing_hours = missing.get('missing_hours', [])
        
        print(f"    • 缺失日期: {len(missing_days)} 天")
        if missing_days:
            print(f"      示例: {missing_days[:5]}")
            if len(missing_days) > 5:
                print(f"      ... 还有 {len(missing_days) - 5} 天")
        
        missing_hour_count = sum(len(h.get('hours', [])) for h in missing_hours)
        print(f"    • 缺失小时: {missing_hour_count} 小时")
        if missing_hours:
            print(f"      示例: {missing_hours[:3]}")
            if len(missing_hours) > 3:
                print(f"      ... 还有 {len(missing_hours) - 3} 天的缺失")
        
        # 异常值分析
        print(f"\n  ⚠️  异常值统计:")
        anomalies = report.get('anomalies', [])
        
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
                print(f"      示例时间戳: {samples[:3]}")
        
        # 连续零值时段
        print(f"\n  🔴 连续零值时段:")
        zero_spans = report.get('continuous_zero_spans', [])
        print(f"    共检测到 {len(zero_spans)} 个连续零值时段")
        if zero_spans:
            for i, span in enumerate(zero_spans[:5], 1):
                print(f"    {i}. {span.get('start')} 至 {span.get('end')}, 共 {span.get('length_hours')} 小时")
            if len(zero_spans) > 5:
                print(f"    ... 还有 {len(zero_spans) - 5} 个时段")
        
        # 总体评估
        print(f"\n【步骤4】总体评估")
        total_points = len(cleaned_points)
        if total_points > 0:
            # 计算异常占比
            total_anomalies = sum(a.get('count', 0) for a in anomalies)
            anomaly_ratio = (total_anomalies / meta.get('total_records', 1)) * 100 if meta.get('total_records') else 0
            
            print(f"  ✓ 数据完整性: {len(missing_days)} 天缺失 + {missing_hour_count} 小时缺失")
            print(f"  ✓ 数据异常率: {anomaly_ratio:.4f}% ({total_anomalies}/{meta.get('total_records')})")
            print(f"  ✓ 清洗效率: 原始记录 {meta.get('total_records')} → 清洗后 {total_points} 小时级数据")
        
        print(f"\n【测试结论】✅ 清洗报告功能测试通过")
        print("=" * 80)
        
        return True
        
    except FileNotFoundError:
        print(f"❌ 文件未找到: {TEST_FILE}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ 无法连接到后端: {API_URL}")
        print("   请确保后端服务器已启动")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ 请求超时")
        return False
    except Exception as e:
        print(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = test_cleaner()
    sys.exit(0 if success else 1)
