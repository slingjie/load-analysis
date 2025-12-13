"""测试完整 API 流程"""
import sys
sys.path.append('.')

from fastapi.testclient import TestClient
from backend.app import app
import json

client = TestClient(app)

# 模拟一个简单的请求
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
        'monthlySchedule': [],
        'dateRules': []
    },
    'monthlyTouPrices': {},
    'points': [
        {'timestamp': '2025-01-01T00:00:00', 'load_kwh': 100},
        {'timestamp': '2025-01-01T00:15:00', 'load_kwh': 120}
    ]
}

print("=" * 80)
print("测试1: 不带导出")
print("=" * 80)
try:
    resp = client.post('/api/storage/cycles', data={'payload': json.dumps(payload)})
    print('状态码:', resp.status_code)
    if resp.status_code == 200:
        data = resp.json()
        print('✓ excel_path:', data.get('excel_path'))
        print('✓ qc notes:', data.get('qc', {}).get('notes'))
    else:
        print('✗ 错误:', resp.text)
except Exception as e:
    print('✗ 异常:', str(e))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("测试2: 带导出（调试报表）")
print("=" * 80)
try:
    resp2 = client.post('/api/storage/cycles', data={
        'payload': json.dumps(payload),
        'export_excel': 'true'
    })
    print('状态码:', resp2.status_code)
    if resp2.status_code == 200:
        data2 = resp2.json()
        print('✓ excel_path:', data2.get('excel_path'))
        print('✓ qc notes:', data2.get('qc', {}).get('notes'))
    else:
        print('✗ 错误:', resp2.text)
except Exception as e:
    print('✗ 异常:', str(e))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("测试3: 业务报表导出")
print("=" * 80)
try:
    resp3 = client.post('/api/storage/cycles', data={
        'payload': json.dumps(payload),
        'export_excel': 'true',
        'export_mode': 'business'
    })
    print('状态码:', resp3.status_code)
    if resp3.status_code == 200:
        data3 = resp3.json()
        print('✓ excel_path:', data3.get('excel_path'))
        print('✓ qc notes:', data3.get('qc', {}).get('notes'))
        if data3.get('excel_path'):
            print('✓ 报表下载地址已生成')
        else:
            print('✗ 报表下载地址为空')
    else:
        print('✗ 错误:', resp3.text)
except Exception as e:
    print('✗ 异常:', str(e))
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
