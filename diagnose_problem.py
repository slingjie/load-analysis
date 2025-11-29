"""
诊断脚本：理解"引入储能后负荷曲线"的计算逻辑

问题描述：
- 用户配置 capacity_kwh=500, c_rate=0.5
- 计算得出 p_max = 250 kW（储能最大功率）
- 用户报告曲线显示 2181 kW，认为这超过了 250 kW 限制

分析目标：
1. 理解 load_with_storage 的含义
2. 验证 p_grid_effect 是否被正确限制
"""

print("=" * 60)
print("储能功率限制逻辑分析")
print("=" * 60)

# 用户配置
cap = 500  # kWh
c_rate = 0.5
p_max = cap * c_rate  # = 250 kW

# 其他参数
eta = 0.922
dod = 0.9
dt_hours = 0.25

print(f"\n【储能配置】")
print(f"  capacity_kwh: {cap}")
print(f"  c_rate: {c_rate}")
print(f"  p_max = capacity × c_rate = {p_max} kW")

print(f"\n【关键理解】")
print(f"  p_max ({p_max} kW) 是储能的最大充/放电功率，")
print(f"  不是负荷曲线的上限！")

print(f"\n【load_with_storage 的含义】")
print(f"  load_with_storage = load_original + p_grid_effect")
print(f"  其中：")
print(f"    - load_original: 原始负荷（客户实际用电功率）")
print(f"    - p_grid_effect: 储能对电网的影响")
print(f"      充电时 > 0（额外从电网取电）")
print(f"      放电时 < 0（向电网送电/削峰）")
print(f"      待机时 = 0（无影响）")

print(f"\n【场景模拟】")

# 场景 1：原始负荷高峰（待机状态）
load_peak = 2181
print(f"\n场景 1：负荷高峰期，储能待机")
print(f"  load_original = {load_peak} kW")
print(f"  p_grid_effect = 0（待机）")
print(f"  load_with_storage = {load_peak} + 0 = {load_peak} kW")
print(f"  → 这是正常的！因为储能没有动作。")

# 场景 2：谷电期充电
load_valley = 1000
limit_kw = 5000
reserve_ch = 500
print(f"\n场景 2：谷电期，储能充电")
print(f"  load_original = {load_valley} kW")
print(f"  limit_kw = {limit_kw}（变压器容量）")
print(f"  reserve_charge_kw = {reserve_ch}")

p_batt_raw = max(limit_kw - reserve_ch - load_valley, 0)
p_batt = min(p_batt_raw, p_max)
print(f"  p_batt_raw = limit - reserve - load = {p_batt_raw} kW")
print(f"  p_batt = min(p_batt_raw, p_max) = min({p_batt_raw}, {p_max}) = {p_batt} kW")

# physics 口径
e_batt = p_batt * dt_hours
e_in_grid = e_batt * (dod / eta)
p_grid = e_in_grid / dt_hours

print(f"  p_grid_effect (physics) = {p_grid:.2f} kW")
print(f"  load_with_storage = {load_valley} + {p_grid:.2f} = {load_valley + p_grid:.2f} kW")

# 场景 3：峰电期放电
load_peak2 = 2000
reserve_dis = 100
print(f"\n场景 3：峰电期，储能放电")
print(f"  load_original = {load_peak2} kW")
print(f"  reserve_discharge_kw = {reserve_dis}")

p_batt_raw_dis = max(load_peak2 - reserve_dis, 0)
p_batt_dis = -min(p_batt_raw_dis, p_max)
print(f"  p_batt_raw = load - reserve = {p_batt_raw_dis} kW")
print(f"  p_batt = -min(p_batt_raw, p_max) = -min({p_batt_raw_dis}, {p_max}) = {p_batt_dis} kW")

# physics 口径
e_batt_dis = -p_batt_dis * dt_hours
e_out_grid = e_batt_dis * (dod * eta)
p_grid_dis = -e_out_grid / dt_hours

print(f"  p_grid_effect (physics) = {p_grid_dis:.2f} kW")
print(f"  load_with_storage = {load_peak2} + ({p_grid_dis:.2f}) = {load_peak2 + p_grid_dis:.2f} kW")
print(f"  → 削峰效果：负荷从 {load_peak2} kW 降到 {load_peak2 + p_grid_dis:.2f} kW")

print("\n【结论】")
print("  1. 如果原始负荷峰值是 2181 kW，且该时刻储能是待机状态，")
print("     则 load_with_storage = 2181 kW 是正常的。")
print("")
print("  2. 如果问题是引入储能后的负荷曲线在充电期间超过了变压器容量，")
print("     这可能是另一个问题，需要检查 limit_mode 和 limit_kw 的配置。")
print("")
print(f"  3. p_max ({p_max} kW) 限制的是储能本身的功率，不是总负荷！")

print(f"\n【建议验证】")
print(f"  1. 查看曲线上 2181 kW 出现在什么时间点")
print(f"  2. 确认该时间点的运行逻辑（充/放/待机）")
print(f"  3. 如果是待机状态，2181 kW 就是原始负荷，符合预期")
print(f"  4. 如果是充电状态，检查 p_grid_effect 的值")
