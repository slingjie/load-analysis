"""验证时序放电 vs 尖段优先在负荷变化时的差异"""

# 假设场景：9月某天
# 充电：8小时×250kW×0.25h = 500 kWh
# 可放电（考虑效率和DoD）：500 × 0.9 × 0.92 = 414 kWh

# 放电时段：7小时×4个15分钟点 = 28个点
# 每个点价格相同：1.11923元/kWh

# 但每个点的负荷不同（示例数据）
import random
random.seed(42)

# 模拟28个放电点的负荷（kW）
loads = [random.uniform(100, 400) for _ in range(28)]

print("="*80)
print("时序放电 vs 尖段优先 - 负荷变化影响分析")
print("="*80)

battery_power = 250  # kW
reserve = 30  # kW
available_energy = 414  # kWh
price = 1.11923  # 元/kWh

print(f"\n参数:")
print(f"  电池功率: {battery_power} kW")
print(f"  放电余量: {reserve} kW")
print(f"  可用能量: {available_energy} kWh")
print(f"  放电价格: {price} 元/kWh (所有时段相同)")
print(f"  放电点数: {len(loads)}")

# 时序放电：逐点分配
print(f"\n{'='*80}")
print("【时序放电策略】")
print(f"{'='*80}")

sequential_energy = 0
sequential_revenue = 0
unused_count = 0

for i, load in enumerate(loads):
    # 该点最大放电功率（受负荷约束）
    max_discharge_power = min(battery_power, max(load - reserve, 0))
    # 15分钟的能量（kWh）
    point_energy = max_discharge_power * 0.25
    
    sequential_energy += point_energy
    sequential_revenue += point_energy * price
    
    if i < 3:  # 打印前3个点
        print(f"  点{i+1}: 负荷={load:.1f}kW, 最大放电={max_discharge_power:.1f}kW, 能量={point_energy:.2f}kWh")
    
    if max_discharge_power < battery_power - 1:
        unused_count += 1

print(f"  ...")
print(f"\n  受限点数: {unused_count}/{len(loads)} (负荷不足导致电池功率未满发)")
print(f"  总放电量: {sequential_energy:.2f} kWh / {available_energy:.2f} kWh (利用率: {sequential_energy/available_energy*100:.1f}%)")
print(f"  总收入: {sequential_revenue:.2f} 元")

# 尖段优先：按价格排序后分配（价格相同，按时间顺序）
print(f"\n{'='*80}")
print("【尖段优先策略】")
print(f"{'='*80}")

# 价格相同时，按时间顺序分配（保持原序）
remaining = available_energy
price_priority_energy = 0
price_priority_revenue = 0
constrained_count = 0

for i, load in enumerate(loads):
    if remaining <= 0:
        break
    
    # 该点最大放电功率
    max_discharge_power = min(battery_power, max(load - reserve, 0))
    # 15分钟的能量
    max_point_energy = max_discharge_power * 0.25
    
    # 实际分配（不超过剩余能量）
    allocated = min(max_point_energy, remaining)
    price_priority_energy += allocated
    price_priority_revenue += allocated * price
    remaining -= allocated
    
    if i < 3:
        print(f"  点{i+1}: 负荷={load:.1f}kW, 分配={allocated:.2f}kWh (剩余={remaining:.2f}kWh)")
    
    if allocated < max_point_energy - 0.01:
        constrained_count += 1

print(f"  ...")
print(f"\n  受限点数: {constrained_count}/{len(loads)}")
print(f"  总放电量: {price_priority_energy:.2f} kWh / {available_energy:.2f} kWh (利用率: {price_priority_energy/available_energy*100:.1f}%)")
print(f"  总收入: {price_priority_revenue:.2f} 元")

# 对比
print(f"\n{'='*80}")
print("【策略对比】")
print(f"{'='*80}")
print(f"  放电量差异: {price_priority_energy - sequential_energy:+.2f} kWh ({(price_priority_energy/sequential_energy-1)*100:+.1f}%)")
print(f"  收入差异: {price_priority_revenue - sequential_revenue:+.2f} 元 ({(price_priority_revenue/sequential_revenue-1)*100:+.1f}%)")

if abs(price_priority_revenue - sequential_revenue) > 1:
    print(f"\n⚠️ 结论：即使价格相同，由于能量分配策略不同，两种策略的收益也可能不同！")
    print(f"         关键差异：尖段优先策略更充分地利用了可用能量")
else:
    print(f"\n✓ 结论：两种策略收益相同")
