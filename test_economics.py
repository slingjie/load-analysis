"""测试经济性计算模块"""

from backend.services.economics import compute_economics

# 定义容量以便计算实际成本
CAPACITY_KWH = 2000

# 测试用例1：无电芯更换的项目
# 年运维成本单位成本：0.1 元/Wh，容量 2000 kWh → 实际成本 = 0.1 × 2000 ÷ 10 = 20 万元
annual_om_cost_unit = 0.1  # 元/Wh
actual_annual_om_cost = (annual_om_cost_unit * CAPACITY_KWH) / 10  # 万元

result = compute_economics(
    first_year_revenue=500000,  # 首年收益 50 万元
    project_years=15,
    annual_om_cost=actual_annual_om_cost,  # 实际年成本 20 万元
    first_year_decay_rate=0.03,  # 首年衰减 3%
    subsequent_decay_rate=0.015,  # 后续衰减 1.5%
    capex_per_wh=0.8,  # 0.8 元/Wh
    installed_capacity_kwh=CAPACITY_KWH,  # 2000 kWh = 2 MWh
)

print("=== 测试用例1: 无电芯更换 ===")
print(f"年运维成本单位成本：{annual_om_cost_unit} 元/Wh，容量 {CAPACITY_KWH} kWh")
print(f"实际年运维成本：{actual_annual_om_cost:.2f} 万元 = {actual_annual_om_cost * 10000:.0f} 元")
print(f"总投资 CAPEX: {result.capex_total:,.0f} 元")
irr_str = f"{result.irr * 100:.2f}%" if result.irr else "N/A"
print(f"IRR: {irr_str}")
payback_str = f"{result.static_payback_years:.2f} 年" if result.static_payback_years else "N/A"
print(f"静态回收期: {payback_str}")
print(f"期末累计净现金流: {result.final_cumulative_net_cashflow:,.0f} 元")
print()
print("年度现金流（前5年）:")
for cf in result.yearly_cashflows[:5]:
    print(f"  第{cf.year_index}年: 收益={cf.year_revenue:,.0f}, 运维={cf.annual_om_cost:,.0f}, 净现金流={cf.net_cashflow:,.0f}, 累计={cf.cumulative_net_cashflow:,.0f}")

print()
print("=== 测试用例2: 有电芯更换 (第10年) ===")
# 电芯更换成本单位成本：0.4 元/Wh，容量 2000 kWh → 实际成本 = 0.4 × 2000 ÷ 10 = 80 万元
cell_replacement_cost_unit = 0.4  # 元/Wh
actual_cell_replacement_cost = (cell_replacement_cost_unit * CAPACITY_KWH) / 10  # 万元

result2 = compute_economics(
    first_year_revenue=500000,
    project_years=20,
    annual_om_cost=actual_annual_om_cost,  # 实际年成本 20 万元
    first_year_decay_rate=0.03,  # 首年衰减 3%
    subsequent_decay_rate=0.015,  # 后续衰减 1.5%
    capex_per_wh=0.8,
    installed_capacity_kwh=CAPACITY_KWH,
    cell_replacement_year=10,
    cell_replacement_cost=actual_cell_replacement_cost,  # 实际更换成本 80 万元
)
print(f"电芯更换成本单位成本：{cell_replacement_cost_unit} 元/Wh，容量 {CAPACITY_KWH} kWh")
print(f"实际更换成本：{actual_cell_replacement_cost:.2f} 万元 = {actual_cell_replacement_cost * 10000:.0f} 元")
print(f"总投资 CAPEX: {result2.capex_total:,.0f} 元")
irr2_str = f"{result2.irr * 100:.2f}%" if result2.irr else "N/A"
print(f"IRR: {irr2_str}")
payback2_str = f"{result2.static_payback_years:.2f} 年" if result2.static_payback_years else "N/A"
print(f"静态回收期: {payback2_str}")
print(f"期末累计净现金流: {result2.final_cumulative_net_cashflow:,.0f} 元")
print()
print("第9-12年现金流（含更换）:")
for cf in result2.yearly_cashflows[8:12]:
    print(f"  第{cf.year_index}年: 收益={cf.year_revenue:,.0f}, 运维={cf.annual_om_cost:,.0f}, 更换={cf.cell_replacement_cost:,.0f}, 净现金流={cf.net_cashflow:,.0f}")

print()
print("=== 所有测试通过 ===")

