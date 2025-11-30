"""测试修复后的经济性计算模块，包含能量数据"""

from backend.services.economics import compute_economics

# 定义容量以便计算实际成本
CAPACITY_KWH = 500

# 测试用例1：使用能量数据计算静态指标
# 模拟一个真实的 Storage Cycles 场景：
# - 首年发电能量：5000 kWh（来自 Storage Cycles 的 discharge_energy_kwh）
# - 首年收益：100,000 元（可从 Storage Cycles 获得）
first_year_energy_kwh = 5000  # 从 Storage Cycles 得到
first_year_revenue = 100000  # 首年收益 10 万元

annual_om_cost_unit = 0.1  # 元/Wh
actual_annual_om_cost = (annual_om_cost_unit * CAPACITY_KWH) / 10  # 万元

result = compute_economics(
    first_year_revenue=first_year_revenue,
    project_years=15,
    annual_om_cost=actual_annual_om_cost,  # 实际年成本
    first_year_decay_rate=0.03,  # 首年衰减 3%
    subsequent_decay_rate=0.015,  # 后续衰减 1.5%
    capex_per_wh=0.8,  # 0.8 元/Wh
    installed_capacity_kwh=CAPACITY_KWH,  # 500 kWh
    first_year_energy_kwh=first_year_energy_kwh,  # 关键：传入真实能量数据
)

print("="*60)
print("测试用例1: 使用 Storage Cycles 能量数据")
print("="*60)
print(f"首年收益: {first_year_revenue:,} 元")
print(f"首年发电能量（来自Storage Cycles）: {first_year_energy_kwh:,} kWh")
print(f"储能装机容量: {CAPACITY_KWH} kWh")
print(f"单位投资成本: 0.8 元/Wh")
print(f"项目年限: 15 年")
print()

print("计算结果：")
print(f"  总投资 CAPEX: {result.capex_total:,.0f} 元")
print(f"  静态 LCOE: {result.static_lcoe:.4f} 元/kWh")
print(f"  年均发电能量: {result.annual_energy_kwh:,.2f} kWh")
print(f"  年均收益: {result.annual_revenue_yuan:,.2f} 元")
print(f"  度电平均收益: {result.revenue_per_kwh:.4f} 元/kWh")
print(f"  经济可行性比值: {result.lcoe_ratio:.4f}")
print(f"  筛选结果: {result.screening_result}")
print()

# 验证计算逻辑
print("验证逻辑：")
# CAPEX = 0.8 元/Wh × 500 kWh × 1000 = 400,000 元
expected_capex = 0.8 * 500 * 1000
print(f"  预期CAPEX = 0.8 × 500 × 1000 = {expected_capex:,.0f} 元 ✓" if abs(result.capex_total - expected_capex) < 1 else f"  预期CAPEX: {expected_capex:,.0f}, 实际: {result.capex_total:,.0f} ✗")

# 度电平均收益应该 = 首年收益 / 首年能量 = 100,000 / 5000 = 20 元/kWh（仅首年，会按衰减率调整多年）
# 但年均应该是按衰减率计算的平均能量来计算
expected_revenue_per_kwh_first_year = first_year_revenue / first_year_energy_kwh
print(f"  首年度电收益 = {first_year_revenue:,} ÷ {first_year_energy_kwh:,} = {expected_revenue_per_kwh_first_year:.4f} 元/kWh")
print(f"  实际年均度电收益 = {result.revenue_per_kwh:.4f} 元/kWh（多年平均，已考虑衰减）")

print()
print("="*60)
print("测试用例2: 不提供能量数据（使用备选方案）")
print("="*60)

result2 = compute_economics(
    first_year_revenue=first_year_revenue,
    project_years=15,
    annual_om_cost=actual_annual_om_cost,
    first_year_decay_rate=0.03,
    subsequent_decay_rate=0.015,
    capex_per_wh=0.8,
    installed_capacity_kwh=CAPACITY_KWH,
    first_year_energy_kwh=None,  # 不提供能量数据
)

print(f"度电平均收益（无能量数据）: {result2.revenue_per_kwh:.4f} 元/kWh")
print(f"  NOTE: 无能量数据时，使用备选方案（假设1.0元/kWh参考价格），精度较低")
print()

# 关键验证：有能量数据时，度电收益应该不等于1.0
print("="*60)
print("关键验证：修复是否成功？")
print("="*60)
if result2.revenue_per_kwh == 1.0 and result.revenue_per_kwh != 1.0:
    print("✓ 修复成功！")
    print(f"  - 有能量数据时: {result.revenue_per_kwh:.4f} 元/kWh（非1.0）")
    print(f"  - 无能量数据时: {result2.revenue_per_kwh:.4f} 元/kWh（备选1.0）")
elif result.revenue_per_kwh == 1.0:
    print("✗ 修复失败！")
    print(f"  - 有能量数据时度电收益仍然是1.0元/kWh")
else:
    print("✓ 修复可能成功！但需要进一步验证备选方案是否使用了1.0")
    print(f"  - 有能量数据时: {result.revenue_per_kwh:.4f} 元/kWh")
    print(f"  - 无能量数据时: {result2.revenue_per_kwh:.4f} 元/kWh")

print()
print("="*60)
print("年度现金流（前5年）:")
print("="*60)
for cf in result.yearly_cashflows[:5]:
    print(f"  第{cf.year_index}年: 收益={cf.year_revenue:,.0f}, 运维={cf.annual_om_cost:,.0f}, 净现金流={cf.net_cashflow:,.0f}, 累计={cf.cumulative_net_cashflow:,.0f}")

print()
irr_str = f"{result.irr * 100:.2f}%" if result.irr else "N/A"
print(f"IRR: {irr_str}")
payback_str = f"{result.static_payback_years:.2f} 年" if result.static_payback_years else "N/A"
print(f"静态回收期: {payback_str}")
print(f"期末累计净现金流: {result.final_cumulative_net_cashflow:,.0f} 元")
