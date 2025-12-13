"""
测试前端API调用 - 模拟浏览器请求
"""
import requests
import json

BASE_URL = "http://localhost:8002"

# 模拟前端发送的请求体（从StorageEconomicsPage.tsx构造的input）
request_body = {
    "first_year_revenue": 100000,
    "first_year_energy_kwh": 50000,
    "project_years": 15,
    "annual_om_cost": 0.2,
    "first_year_decay_rate": 0.03,
    "subsequent_decay_rate": 0.02,
    "capex_per_wh": 1.0,
    "installed_capacity_kwh": 100,
    "cell_replacement_cost": 0.3,
    "cell_replacement_year": 8,
    "user_share_percent": 30.0,  # 用户分成比例
}

print("=" * 60)
print("测试前端API调用")
print("=" * 60)
print(f"\n请求URL: {BASE_URL}/api/storage/economics/export")
print(f"请求体: {json.dumps(request_body, indent=2, ensure_ascii=False)}")

try:
    response = requests.post(
        f"{BASE_URL}/api/storage/economics/export",
        json=request_body,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"\n响应状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n✓ 成功!")
        print(f"报表路径: {result.get('excel_path')}")
        print(f"消息: {result.get('message')}")
    else:
        print(f"\n✗ 失败!")
        print(f"响应内容: {response.text}")
        
        # 尝试解析JSON错误详情
        try:
            error_detail = response.json()
            print(f"\n错误详情:")
            if isinstance(error_detail.get('detail'), list):
                # FastAPI验证错误
                for err in error_detail['detail']:
                    print(f"  - 字段: {'.'.join(str(x) for x in err.get('loc', []))}")
                    print(f"    错误: {err.get('msg')}")
                    print(f"    类型: {err.get('type')}")
            else:
                print(f"  {error_detail.get('detail')}")
        except:
            pass

except requests.exceptions.ConnectionError:
    print("\n✗ 无法连接到后端服务器")
    print("请确保后端服务正在运行: python -m uvicorn backend.app:app --reload --port 8002")
except Exception as e:
    print(f"\n✗ 请求失败: {str(e)}")
    import traceback
    traceback.print_exc()
