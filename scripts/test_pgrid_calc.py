"""测试 p_grid_effect 计算逻辑"""
import sys
sys.path.insert(0, r'd:\Desktop\ai\1028负荷展示和tou配置\backend')

# 模拟参数
cap = 500  # capacity_kwh
c_rate = 0.5
p_max = cap * c_rate  # = 250 kW
eta = 0.922  # single_side_efficiency
dod_cfg = 0.9  # depth_of_discharge
soc_min = 0.05
soc_max = 0.95
effective_dod = max(0.0, min(dod_cfg, soc_max - soc_min))  # = 0.9
dt_hours = 0.25  # 15分钟

print("=== 储能参数 ===")
print(f"capacity_kwh: {cap}")
print(f"c_rate: {c_rate}")
print(f"p_max = cap * c_rate = {p_max} kW")
print(f"effective_dod: {effective_dod}")
print(f"eta: {eta}")

# 模拟一个充电场景
# 假设 limit_kw = 5000, reserve_ch = 500, load_kw = 2000
limit_kw = 5000
reserve_ch = 500
load_kw = 2000

print("\n=== 充电场景 ===")
print(f"limit_kw: {limit_kw}")
print(f"reserve_charge_kw: {reserve_ch}")
print(f"load_kw: {load_kw}")

# 根据修复后的代码
p_batt_raw = max(limit_kw - reserve_ch - load_kw, 0.0)  # = 5000 - 500 - 2000 = 2500
p_batt = min(p_batt_raw, p_max) if p_max > 0 else p_batt_raw  # = min(2500, 250) = 250

print(f"\np_batt_raw = limit_kw - reserve_ch - load_kw = {p_batt_raw} kW")
print(f"p_batt = min(p_batt_raw, p_max) = min({p_batt_raw}, {p_max}) = {p_batt} kW")

# 计算电网侧功率
e_batt = p_batt * dt_hours  # = 250 * 0.25 = 62.5 kWh
print(f"\ne_batt = p_batt * dt_hours = {p_batt} * {dt_hours} = {e_batt} kWh")

# physics 口径
e_in_phys = e_batt * (effective_dod / max(eta, 1e-9))
p_grid_phys = e_in_phys / dt_hours

print(f"\n=== Physics 口径 ===")
print(f"e_in_phys = e_batt * (dod / eta) = {e_batt} * ({effective_dod} / {eta}) = {e_in_phys:.4f} kWh")
print(f"p_grid_phys = e_in_phys / dt_hours = {e_in_phys:.4f} / {dt_hours} = {p_grid_phys:.4f} kW")
print(f"load_with_storage_physics = load_kw + p_grid_phys = {load_kw} + {p_grid_phys:.4f} = {load_kw + p_grid_phys:.4f} kW")

# sample 口径
e_in_sample = e_batt * (eta / max(effective_dod, 1e-9))
p_grid_sample = e_in_sample / dt_hours

print(f"\n=== Sample 口径 ===")
print(f"e_in_sample = e_batt * (eta / dod) = {e_batt} * ({eta} / {effective_dod}) = {e_in_sample:.4f} kWh")
print(f"p_grid_sample = e_in_sample / dt_hours = {e_in_sample:.4f} / {dt_hours} = {p_grid_sample:.4f} kW")
print(f"load_with_storage_sample = load_kw + p_grid_sample = {load_kw} + {p_grid_sample:.4f} = {load_kw + p_grid_sample:.4f} kW")

print("\n=== 结论 ===")
print(f"✓ p_batt 已经被正确限制为 {p_max} kW (p_max)")
print(f"  - Physics: load_with_storage = {load_kw + p_grid_phys:.2f} kW")
print(f"  - Sample:  load_with_storage = {load_kw + p_grid_sample:.2f} kW")

# 检查曲线上的问题 - 可能是放电场景
print("\n" + "="*60)
print("=== 检查放电场景 ===")
# 放电时负荷可能被削减
load_kw_high = 2181  # 用户看到的最大值

# 假设用户配置的是 sample 公式
# 放电时：
# e_out_sample = e_batt * (1.0 / (dod * eta))
# p_grid_sample < 0（向电网送电，但这被禁止了）

# 问题可能是：界面上显示的是原始负荷，而不是储能后的负荷？
print("如果曲线显示的是原始负荷而非储能后的负荷，那可能是前端数据绑定问题")

# 或者问题在 API 返回的数据
print("\n请检查 API 返回的数据中 load_with_storage_kw 字段的值")
