"""直接测试 /api/storage/cycles/curves API"""
import requests
import json

# 简单测试 - 构造一个最小的请求
# 首先需要有 points 数据

# 模拟一些负荷数据点
test_points = []
from datetime import datetime, timedelta
base_time = datetime(2024, 1, 1, 0, 0, 0)
for i in range(96):  # 一天 96 个 15 分钟
    ts = base_time + timedelta(minutes=15*i)
    # 模拟典型负荷曲线
    hour = ts.hour
    if 8 <= hour <= 11 or 14 <= hour <= 17:  # 高峰
        load = 3000 + (i % 10) * 50
    elif 6 <= hour < 8 or 12 <= hour < 14:  # 平时
        load = 2000 + (i % 10) * 30
    else:  # 低谷
        load = 1500 + (i % 10) * 20
    test_points.append({
        "timestamp": ts.isoformat(),
        "load_kw": load,
        "load_kwh": load * 0.25  # 15分钟能量
    })

# 构造 storage 配置
storage_cfg = {
    "capacity_kwh": 500,
    "c_rate": 0.5,
    "single_side_efficiency": 0.922,
    "depth_of_discharge": 0.9,
    "soc_min": 0.05,
    "soc_max": 0.95,
    "reserve_charge_kw": 500,
    "reserve_discharge_kw": 100,
    "metering_mode": "transformer_capacity",
    "transformer_capacity_kva": 5000,
    "transformer_power_factor": 1,
    "calc_style": "window_avg",
    "energy_formula": "physics",
    "merge_threshold_minutes": 30
}

# 构造 strategySource
# 简化：充放时间
# 00-06: 充电, 06-12: 待机, 12-18: 放电, 18-24: 待机
monthly_schedule = {
    "0_3": {  # 代表所有月份
        "hours": ["充", "充", "充", "充", "充", "充",  # 0-5
                  "待机", "待机", "待机", "待机", "待机", "待机",  # 6-11
                  "放", "放", "放", "放", "放", "放",  # 12-17
                  "待机", "待机", "待机", "待机", "待机", "待机"]  # 18-23
    }
}

# 构造完整 payload
payload = {
    "points": test_points,
    "storage": storage_cfg,
    "strategySource": {
        "monthlySchedule": monthly_schedule,
        "dateRules": []
    },
    "monthlyTouPrices": None
}

# 测试 curves API
body = {
    "payload": payload,
    "date": "2024-01-01"
}

print("发送测试请求到 /api/storage/cycles/curves ...")
print(f"storage 配置: capacity_kwh={storage_cfg['capacity_kwh']}, c_rate={storage_cfg['c_rate']}")
print(f"预期 p_max = {storage_cfg['capacity_kwh'] * storage_cfg['c_rate']} kW")
print()

try:
    resp = requests.post("http://127.0.0.1:8000/api/storage/cycles/curves", json=body)
    if resp.status_code == 200:
        data = resp.json()
        print("✓ 请求成功！")
        
        # 分析返回数据
        original = data.get("load_original", [])
        with_storage = data.get("load_with_storage", [])
        
        if original and with_storage:
            orig_loads = [p["load_kw"] for p in original]
            stor_loads = [p["load_kw"] for p in with_storage]
            
            print(f"\n原始负荷: max={max(orig_loads):.2f}, min={min(orig_loads):.2f}")
            print(f"储能后负荷: max={max(stor_loads):.2f}, min={min(stor_loads):.2f}")
            
            # 找出差异最大的点
            max_increase = 0
            max_increase_idx = 0
            for i in range(len(orig_loads)):
                diff = stor_loads[i] - orig_loads[i]
                if diff > max_increase:
                    max_increase = diff
                    max_increase_idx = i
            
            print(f"\n最大增量: {max_increase:.2f} kW (索引 {max_increase_idx})")
            print(f"  - 原始: {orig_loads[max_increase_idx]:.2f} kW")
            print(f"  - 储能后: {stor_loads[max_increase_idx]:.2f} kW")
            print(f"  - 时间: {original[max_increase_idx]['timestamp']}")
            
            # 检查是否超过 p_max
            p_max = storage_cfg['capacity_kwh'] * storage_cfg['c_rate']
            if max_increase > p_max * 1.1:  # 允许 10% 误差
                print(f"\n⚠️  警告：最大增量 {max_increase:.2f} kW 超过 p_max {p_max:.2f} kW！")
            else:
                print(f"\n✓ 最大增量 {max_increase:.2f} kW 未超过 p_max {p_max:.2f} kW")
    else:
        print(f"✗ 请求失败: {resp.status_code}")
        print(resp.text)
except Exception as e:
    print(f"✗ 请求异常: {e}")

print("\n请查看后端日志以获取调试信息。")
