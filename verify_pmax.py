"""验证 p_max 限制是否被正确应用"""

# 用户的配置
cap = 500  # kWh
c_rate = 0.5
p_max = cap * c_rate  # = 250 kW

# 00:00 时刻的数据
limit_kw = 5000
reserve_ch = 500
load_kw = 104

print("=== 用户配置 ===")
print(f"capacity_kwh: {cap}")
print(f"c_rate: {c_rate}")
print(f"p_max = cap * c_rate = {p_max} kW")

print("\n=== 00:00 时刻的计算 ===")
print(f"limit_kw: {limit_kw}")
print(f"reserve_charge_kw: {reserve_ch}")
print(f"load_kw: {load_kw}")

# 根据代码逻辑
p_batt_raw = max(limit_kw - reserve_ch - load_kw, 0.0)
print(f"\np_batt_raw = max(limit_kw - reserve_ch - load_kw, 0) = max({limit_kw} - {reserve_ch} - {load_kw}, 0) = {p_batt_raw} kW")

# 应用 p_max 限制
p_batt = min(p_batt_raw, p_max) if p_max > 0 else p_batt_raw
print(f"p_batt = min(p_batt_raw, p_max) = min({p_batt_raw}, {p_max}) = {p_batt} kW")

print(f"\n=== 预期 vs 实际 ===")
print(f"预期 p_batt: {p_batt} kW (限制在 p_max)")
print(f"实际 p_batt (报表): 882.80 kW")

if p_batt != 882.80:
    print(f"\n⚠️ 报表中的 p_batt (882.80) 不等于预期值 ({p_batt})！")
    print("说明 p_max 限制没有被应用，可能的原因：")
    print("  1. storage_cfg 中没有正确传递 c_rate")
    print("  2. c_rate 被解析为 0 或 None")
    print("  3. 代码路径没有执行到 p_max 限制")
    
# 检查报表中的 p_batt 是否等于 p_batt_raw
print(f"\n=== 验证 ===")
print(f"p_batt_raw (无 p_max 限制): {p_batt_raw} kW")
if abs(p_batt_raw - 882.80) < 100:
    print("❌ 报表中的值接近 p_batt_raw，说明 p_max 限制确实没有被应用！")
else:
    # 反推 reserve_ch
    # p_batt_raw = limit_kw - reserve_ch - load_kw
    # 882.80 = 5000 - reserve_ch - 104
    reverse_reserve_ch = 5000 - 104 - 882.80
    print(f"如果 p_batt = 882.80，反推 reserve_ch = {reverse_reserve_ch} kW")
    
# 验证能量计算
eta = 0.922
dod = 0.9
dt_hours = 0.25

print("\n=== 验证能量计算 (sample 公式) ===")
e_batt = 882.80 * dt_hours  # = 220.70 kWh
e_in_sample = e_batt * (eta / dod)  # sample 公式
p_grid_sample = e_in_sample / dt_hours

print(f"如果 p_batt = 882.80 kW:")
print(f"  e_batt = p_batt * dt_hours = 882.80 * 0.25 = {e_batt:.4f} kWh")
print(f"  e_in_sample = e_batt * (eta / dod) = {e_batt:.4f} * ({eta} / {dod}) = {e_in_sample:.4f} kWh")
print(f"  p_grid_sample = e_in_sample / dt_hours = {e_in_sample:.4f} / 0.25 = {p_grid_sample:.4f} kW")
print(f"  load_with_storage_sample = load_kw + p_grid_sample = {load_kw} + {p_grid_sample:.4f} = {load_kw + p_grid_sample:.4f} kW")

print(f"\n报表中的值:")
print(f"  p_batt_kw: 882.801619")
print(f"  e_in_sample_kwh: 226.095 (接近 {e_in_sample:.3f})")
print(f"  p_grid_effect_sample_kw: 904.381 (接近 {p_grid_sample:.3f})")
print(f"  load_with_storage_sample_kw: 1008.381")

# 反推实际使用的 reserve_ch
actual_reserve = 5000 - 104 - 882.801619
print(f"\n=== 关键发现 ===")
print(f"从 p_batt = 882.80 反推:")
print(f"  实际使用的 reserve_ch = 5000 - 104 - 882.80 = {actual_reserve:.2f} kW")
print(f"  但用户配置的 reserve_charge_kw = 500 kW")
print(f"\n这说明 reserve_ch 可能被正确读取了，但 p_max 限制没有生效！")
print(f"因为 5000 - 500 - 104 = 4396 kW (这才是 p_batt_raw)")
print(f"而报表中 p_batt = 882.80，不等于 4396，说明有其他限制在起作用")

# 继续分析...窗口能量目标？
print("\n=== 检查窗口能量目标约束 ===")
full_ratio = 226.0953035 / 500  # cum_charge_grid_main / capacity
print(f"从 cum_charge_grid_main = 226.0953 推算:")
print(f"  单点充电能量 = 226.0953 kWh (第一个点就达到了目标)")
print(f"  full_ratio ≈ {full_ratio:.4f}")

# 检查 charge_target 计算
usable_batt = cap * full_ratio
usable_batt_dod = usable_batt * dod
charge_target = usable_batt_dod / eta
print(f"\n如果 full_ratio = {full_ratio:.4f}:")
print(f"  usable_batt = cap * full_ratio = {cap} * {full_ratio:.4f} = {usable_batt:.2f} kWh")
print(f"  usable_batt_dod = usable_batt * dod = {usable_batt:.2f} * {dod} = {usable_batt_dod:.2f} kWh")
print(f"  charge_target = usable_batt_dod / eta = {usable_batt_dod:.2f} / {eta} = {charge_target:.2f} kWh")

print(f"\n但报表显示 charge_target_grid_main = 192.2 kWh")
print("这说明 full_ratio 不是 0.452，而是...")
fr_actual = (192.2 * eta) / (dod * cap)
print(f"  反推 full_ratio = (charge_target * eta) / (dod * cap) = (192.2 * {eta}) / ({dod} * {cap}) = {fr_actual:.4f}")
