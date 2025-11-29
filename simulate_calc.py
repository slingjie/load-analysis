"""模拟 build_step15_power_series 的计算流程"""
import sys
sys.path.insert(0, r'd:\Desktop\ai\1028负荷展示和tou配置\backend')

import pandas as pd
from services import cycles as cycles_svc

# 构造测试数据
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

# 打印参数解析结果
print("=== 参数解析 ===")
cap = float(storage_cfg.get("capacity_kwh", 0) or 0)
c_rate = float(storage_cfg.get("c_rate", 0.5) or 0.5)
p_max = cap * c_rate if cap > 0 and c_rate > 0 else 0.0

print(f"capacity_kwh: {cap}")
print(f"c_rate: {c_rate}")
print(f"p_max = cap * c_rate = {p_max} kW")

eta = float(storage_cfg.get("single_side_efficiency", 0.9) or 0.9)
dod_cfg = float(storage_cfg.get("depth_of_discharge", 1.0) or 1.0)
soc_min = float(storage_cfg.get("soc_min", 0.05) or 0.05)
soc_max = float(storage_cfg.get("soc_max", 0.95) or 0.95)
effective_dod = max(0.0, min(dod_cfg, soc_max - soc_min))
dod = effective_dod
reserve_ch = float(storage_cfg.get("reserve_charge_kw", 0) or 0)
reserve_dis = float(storage_cfg.get("reserve_discharge_kw", 0) or 0)

print(f"eta: {eta}")
print(f"effective_dod: {effective_dod}")
print(f"reserve_charge_kw: {reserve_ch}")
print(f"reserve_discharge_kw: {reserve_dis}")

# 模拟 00:00 时刻的计算
print("\n=== 模拟 00:00 时刻计算 ===")
limit_kw = 5000
load_kw = 104
op = "充"
dt_hours = 0.25

print(f"limit_kw: {limit_kw}")
print(f"load_kw: {load_kw}")
print(f"op: {op}")

# 充电功率计算
p_batt_raw = max(limit_kw - reserve_ch - load_kw, 0.0)
print(f"\np_batt_raw = max({limit_kw} - {reserve_ch} - {load_kw}, 0) = {p_batt_raw} kW")

# 应用 p_max 限制
print(f"p_max = {p_max} kW")
print(f"p_max > 0: {p_max > 0}")

if p_max > 0:
    p_batt = min(p_batt_raw, p_max)
    print(f"p_batt = min({p_batt_raw}, {p_max}) = {p_batt} kW")
else:
    p_batt = p_batt_raw
    print(f"p_batt = p_batt_raw = {p_batt} kW (p_max 限制未生效！)")

# 能量计算
e_batt = p_batt * dt_hours
e_in_sample = e_batt * (eta / max(effective_dod, 1e-9))
p_grid_sample = e_in_sample / dt_hours

print(f"\ne_batt = {p_batt} * {dt_hours} = {e_batt} kWh")
print(f"e_in_sample = {e_batt} * ({eta} / {effective_dod}) = {e_in_sample:.4f} kWh")
print(f"p_grid_sample = {e_in_sample:.4f} / {dt_hours} = {p_grid_sample:.4f} kW")
print(f"load_with_storage_sample = {load_kw} + {p_grid_sample:.4f} = {load_kw + p_grid_sample:.4f} kW")

print("\n=== 与报表对比 ===")
print("报表值:")
print("  p_batt_kw: 882.801619")
print("  e_in_sample_kwh: 226.0953035")
print("  p_grid_effect_sample_kw: 904.3812141")
print("  load_with_storage_sample_kw: 1008.381214")

print(f"\n模拟值:")
print(f"  p_batt_kw: {p_batt}")
print(f"  e_in_sample_kwh: {e_in_sample:.4f}")
print(f"  p_grid_effect_sample_kw: {p_grid_sample:.4f}")
print(f"  load_with_storage_sample_kw: {load_kw + p_grid_sample:.4f}")

if abs(p_batt - 882.801619) < 0.1:
    print("\n⚠️ 模拟值与报表一致，说明 p_max 限制确实没有生效！")
elif abs(p_batt - 250) < 0.1:
    print(f"\n✓ 模拟值正确 (p_batt = {p_batt})，说明代码逻辑正确")
    print("但报表中的值不同，可能是报表生成时使用的是旧代码")
else:
    print(f"\n❓ 模拟值 ({p_batt}) 既不等于 250 也不等于 882.80，需要进一步分析")
