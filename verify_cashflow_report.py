"""验证业务报表中的年度现金流明细"""
import sys
sys.path.append('.')

from fastapi.testclient import TestClient
from backend.app import app
import json
import zipfile
import pandas as pd
import io
from pathlib import Path

client = TestClient(app)

# 创建一个有完整数据的测试负荷
payload = {
    'storage': {
        'capacity_kwh': 1000,
        'c_rate': 0.5,
        'single_side_efficiency': 0.95,
        'depth_of_discharge': 0.9,
        'metering_mode': 'monthly_demand_max',
        'energy_formula': 'physics'
    },
    'strategySource': {
        'monthlySchedule': [
            # 1月配置：简单的充放策略
            [
                {'tou': '谷', 'op': '充'}, {'tou': '谷', 'op': '充'}, {'tou': '谷', 'op': '充'}, {'tou': '谷', 'op': '充'},
                {'tou': '谷', 'op': '充'}, {'tou': '谷', 'op': '充'}, {'tou': '谷', 'op': '充'}, {'tou': '平', 'op': '待机'},
                {'tou': '平', 'op': '待机'}, {'tou': '峰', 'op': '放'}, {'tou': '峰', 'op': '放'}, {'tou': '峰', 'op': '放'},
                {'tou': '平', 'op': '待机'}, {'tou': '平', 'op': '待机'}, {'tou': '平', 'op': '待机'}, {'tou': '平', 'op': '待机'},
                {'tou': '平', 'op': '待机'}, {'tou': '平', 'op': '待机'}, {'tou': '峰', 'op': '放'}, {'tou': '峰', 'op': '放'},
                {'tou': '峰', 'op': '放'}, {'tou': '平', 'op': '待机'}, {'tou': '平', 'op': '待机'}, {'tou': '谷', 'op': '充'}
            ]
        ] * 12,  # 所有月份使用相同配置
        'dateRules': []
    },
    'monthlyTouPrices': {
        '2025-01': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-02': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-03': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-04': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-05': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-06': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-07': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-08': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-09': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-10': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-11': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
        '2025-12': {'谷': 0.3, '平': 0.6, '峰': 1.0, '尖': 1.2, '深': 0.2},
    },
    'points': []
}

# 生成一年的测试数据（每15分钟一个点）
from datetime import datetime, timedelta
start_date = datetime(2025, 1, 1, 0, 0, 0)
for i in range(365 * 96):  # 365天 × 96个点/天
    timestamp = start_date + timedelta(minutes=15*i)
    # 模拟负荷曲线：白天高，夜晚低
    hour = timestamp.hour
    if 8 <= hour < 22:
        load = 500 + (hour - 8) * 20  # 白天负荷较高
    else:
        load = 200 + hour * 10  # 夜晚负荷较低
    payload['points'].append({
        'timestamp': timestamp.strftime('%Y-%m-%dT%H:%M:%S'),
        'load_kwh': load
    })

print("=" * 80)
print("测试：业务报表导出（包含年度现金流明细）")
print("=" * 80)
print(f"负荷点数: {len(payload['points'])} 个")
print(f"时间范围: {payload['points'][0]['timestamp']} ~ {payload['points'][-1]['timestamp']}")
print()

# 导出业务报表
print("正在导出业务报表...")
resp = client.post('/api/storage/cycles', data={
    'payload': json.dumps(payload),
    'export_excel': 'true',
    'export_mode': 'business'
})

if resp.status_code != 200:
    print(f"✗ API 调用失败: {resp.status_code}")
    print(resp.text)
    sys.exit(1)

result = resp.json()
excel_path = result.get('excel_path')

if not excel_path:
    print("✗ 未返回报表下载地址")
    sys.exit(1)

print(f"✓ 报表下载地址: {excel_path}")
print()

# 查看生成的报表文件
outputs_dir = Path("outputs")
# 从 excel_path 中提取实际路径
relative_path = excel_path.replace('/outputs/', '')
report_path = outputs_dir / relative_path

if not report_path.exists():
    print(f"✗ 报表文件不存在: {report_path}")
    sys.exit(1)

print(f"✓ 报表文件存在: {report_path}")
print(f"✓ 文件大小: {report_path.stat().st_size / 1024:.2f} KB")
print()

# 解压并查看内容
with zipfile.ZipFile(report_path, 'r') as zf:
    files = zf.namelist()
    print("✓ ZIP 内包含的文件:")
    for f in files:
        print(f"  - {f}")
    print()
    
    # 查找年度现金流明细文件
    cashflow_files = [f for f in files if '年度现金流明细' in f]
    if not cashflow_files:
        print("✗ 未找到年度现金流明细文件")
        sys.exit(1)
    
    print("=" * 80)
    print(f"✓ 找到年度现金流明细文件: {cashflow_files[0]}")
    print("=" * 80)
    
    # 读取并显示内容
    with zf.open(cashflow_files[0]) as cf:
        df = pd.read_csv(io.TextIOWrapper(cf, encoding='utf-8-sig'))
        print()
        print("年度现金流明细内容:")
        print("-" * 80)
        print(df.to_string(index=False))
        print("-" * 80)
        print()
        print("数据统计:")
        print(f"  - 年份: {df['年份'].iloc[0]}")
        print(f"  - 主口径净利润: {df['主口径_净利润(元)'].iloc[0]:.2f} 元")
        print(f"  - Physics净利润: {df['Physics_净利润(元)'].iloc[0]:.2f} 元")
        print(f"  - Sample净利润: {df['Sample_净利润(元)'].iloc[0]:.2f} 元")
        print(f"  - 主口径充电量: {df['主口径_充电量(kWh)'].iloc[0]:.2f} kWh")
        print(f"  - 主口径放电量: {df['主口径_放电量(kWh)'].iloc[0]:.2f} kWh")
        
print()
print("=" * 80)
print("✓ 验证完成！年度现金流明细报表已成功生成")
print("=" * 80)
