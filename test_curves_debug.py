"""快速测试 /api/storage/cycles/curves 端点的调试脚本"""
import requests
import json

# 测试配置
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
    "energy_formula": "sample",
    "merge_threshold_minutes": 30
}

# 计算预期的 p_max
p_max = storage_cfg["capacity_kwh"] * storage_cfg["c_rate"]
print(f"预期最大功率 p_max = {p_max} kW")

# 简单测试：直接导入后端模块进行调试
import sys
sys.path.insert(0, r'd:\Desktop\ai\1028负荷展示和tou配置\backend')

from services import cycles as cycles_svc

# 模拟一个简单的测试
print("\n测试 build_step15_power_series 中的 p_max 计算：")
print(f"  capacity_kwh: {storage_cfg['capacity_kwh']}")
print(f"  c_rate: {storage_cfg['c_rate']}")
print(f"  计算的 p_max: {storage_cfg['capacity_kwh'] * storage_cfg['c_rate']} kW")

# 检查代码中是否正确读取了 c_rate
import inspect
source = inspect.getsource(cycles_svc.build_step15_power_series)
if "c_rate" in source:
    print("\n✓ build_step15_power_series 函数中包含 c_rate")
    # 找到 p_max 相关的代码
    for i, line in enumerate(source.split('\n')):
        if 'p_max' in line or 'c_rate' in line:
            print(f"  行 {i}: {line.strip()}")
else:
    print("\n✗ build_step15_power_series 函数中没有 c_rate！这是问题所在！")
