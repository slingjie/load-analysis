"""分析9月的TOU配置和schedule"""
import sys
sys.path.insert(0, 'd:\\Desktop\\ai\\1028负荷展示和tou配置')

# 模拟9月的schedule配置
sep_schedule = [
    {"tou": "谷", "op": "充"},  # 0
    {"tou": "谷", "op": "充"},  # 1
    {"tou": "谷", "op": "充"},  # 2
    {"tou": "谷", "op": "充"},  # 3
    {"tou": "谷", "op": "充"},  # 4
    {"tou": "谷", "op": "充"},  # 5
    {"tou": "谷", "op": "充"},  # 6
    {"tou": "谷", "op": "充"},  # 7
    {"tou": "平", "op": "待机"},  # 8
    {"tou": "平", "op": "待机"},  # 9
    {"tou": "平", "op": "待机"},  # 10
    {"tou": "平", "op": "待机"},  # 11
    {"tou": "平", "op": "待机"},  # 12
    {"tou": "平", "op": "待机"},  # 13
    {"tou": "平", "op": "待机"},  # 14
    {"tou": "平", "op": "待机"},  # 15
    {"tou": "峰", "op": "放"},  # 16
    {"tou": "峰", "op": "放"},  # 17
    {"tou": "峰", "op": "放"},  # 18
    {"tou": "峰", "op": "放"},  # 19
    {"tou": "峰", "op": "放"},  # 20
    {"tou": "峰", "op": "放"},  # 21
    {"tou": "峰", "op": "放"},  # 22
    {"tou": "平", "op": "待机"}   # 23
]

# 9月价格
sep_prices = {
    "尖": 0,  # 无尖电价
    "峰": 1.11923,
    "平": 0.6499,
    "谷": 0.30583,
    "深": 0.30583
}

print("="*80)
print("9月配置分析")
print("="*80)

charge_hours = [i for i, s in enumerate(sep_schedule) if s["op"] == "充"]
discharge_hours = [i for i, s in enumerate(sep_schedule) if s["op"] == "放"]

print(f"\n充电时段: {charge_hours}")
print(f"充电档位: {[sep_schedule[h]['tou'] for h in charge_hours]}")
print(f"充电价格: {[sep_prices[sep_schedule[h]['tou']] for h in charge_hours]}")
print(f"平均充电价格: {sum(sep_prices[sep_schedule[h]['tou']] for h in charge_hours) / len(charge_hours):.4f} 元/kWh")

print(f"\n放电时段: {discharge_hours}")
print(f"放电档位: {[sep_schedule[h]['tou'] for h in discharge_hours]}")
discharge_prices = [sep_prices[sep_schedule[h]['tou']] for h in discharge_hours]
print(f"放电价格: {discharge_prices}")
print(f"平均放电价格: {sum(discharge_prices) / len(discharge_prices):.4f} 元/kWh")
print(f"最高放电价格: {max(discharge_prices):.4f} 元/kWh")
print(f"最低放电价格: {min(discharge_prices):.4f} 元/kWh")

print(f"\n价格档位数: {len(set(discharge_prices))}")
print(f"唯一价格列表: {sorted(set(discharge_prices), reverse=True)}")

if len(set(discharge_prices)) == 1:
    print("\n⚠️ 结论：所有放电时段价格相同！两种策略结果应该一致！")
else:
    print(f"\n✓ 结论：放电时段有 {len(set(discharge_prices))} 个不同价格，价格优先策略可以优化")
    print(f"  价格差异: {max(discharge_prices) - min(discharge_prices):.4f} 元/kWh")
    print(f"  最大优化空间: {(max(discharge_prices) / sum(discharge_prices) * len(discharge_prices) - 1) * 100:.2f}%")
