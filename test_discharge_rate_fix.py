"""
验证满放率计算修正逻辑

测试场景：
- 额定容量 = 100 kWh
- 第一次充电量 = 60 kWh，满充率 = 60%
- 第一次放电量 = 50 kWh

预期结果：
旧逻辑：满放率 = 50 / 100 = 50%  ❌（错误：放电率 < 充电率是合理的，但不应该基于额定容量）
新逻辑：满放率 = (50 × 0.6) / 100 = 30%  ✅（正确：基于实际充入的电量）

另一种理解：
- 实际充入电量 = 100 × 0.6 = 60 kWh
- 实际放出电量 = 50 kWh
- 放电占充电的比例 = 50 / 60 = 83.33%
- 满放率 = 83.33% × 60% = 50%（相对于额定容量的百分比）

等等，公式需要再确认...
根据用户提供的公式：满放率 = (可放电量 × 满充率) / 额定容量
= (50 × 0.6) / 100 = 0.3 = 30%

这个公式的含义是什么？让我重新理解...
"""

def calculate_discharge_rate_old(discharge_energy: float, rated_capacity: float) -> float:
    """旧逻辑：直接用额定容量计算"""
    return discharge_energy / rated_capacity if rated_capacity > 0 else 0.0


def calculate_discharge_rate_new(discharge_energy: float, charge_rate: float, rated_capacity: float) -> float:
    """新逻辑：基于实际充入电量计算"""
    if discharge_energy < 0:
        return 0.0
    if charge_rate == 0:
        return 0.0
    
    # 实际充入电量
    actual_charge = rated_capacity * charge_rate
    
    if discharge_energy > actual_charge:
        # 放电量超过充电量，满放率上限为满充率
        return charge_rate
    else:
        # 正常情况：满放率 = (放电量 × 满充率) / 额定容量
        return (discharge_energy * charge_rate) / rated_capacity


# 测试案例
rated_cap = 100.0  # kWh
charge_energy = 60.0  # kWh
charge_rate = charge_energy / rated_cap  # 0.6 = 60%
discharge_energy = 50.0  # kWh

print("=" * 60)
print("测试场景：")
print(f"  额定容量: {rated_cap} kWh")
print(f"  充电量: {charge_energy} kWh → 满充率 = {charge_rate * 100:.2f}%")
print(f"  放电量: {discharge_energy} kWh")
print()

old_rate = calculate_discharge_rate_old(discharge_energy, rated_cap)
print(f"旧逻辑：满放率 = {discharge_energy} / {rated_cap} = {old_rate * 100:.2f}%")

new_rate = calculate_discharge_rate_new(discharge_energy, charge_rate, rated_cap)
print(f"新逻辑：满放率 = ({discharge_energy} × {charge_rate}) / {rated_cap} = {new_rate * 100:.2f}%")
print()

# 另一种理解方式
actual_discharge_ratio = discharge_energy / charge_energy if charge_energy > 0 else 0
print(f"放电效率：{discharge_energy} / {charge_energy} = {actual_discharge_ratio * 100:.2f}%")
print(f"相对于额定容量：{actual_discharge_ratio * 100:.2f}% × {charge_rate * 100:.2f}% = {actual_discharge_ratio * charge_rate * 100:.2f}%")
print()

print("验证结果：")
print(f"  新逻辑结果 = {new_rate * 100:.2f}%")
print(f"  放电效率 × 满充率 = {actual_discharge_ratio * charge_rate * 100:.2f}%")
print(f"  两者{'一致 ✅' if abs(new_rate - actual_discharge_ratio * charge_rate) < 0.001 else '不一致 ❌'}")
print("=" * 60)
