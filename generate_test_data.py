"""
测试数据生成器：生成包含明显价格差异的负荷数据

用途：用于验证尖段优先放电策略的有效性
特点：
- 包含全年数据（365天）
- 每天96个15分钟点
- 分时电价有明显差异（尖1.5元、峰1.2元、平0.8元、谷0.5元）
- 放电窗口包含尖段和平段，确保策略差异明显
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_test_load_data(
    start_date="2024-01-01",
    days=365,
    base_load_kw=500,
    peak_load_kw=1000,
    output_file="test_load_with_price_diff.csv"
):
    """
    生成测试负荷数据
    
    参数：
        start_date: 起始日期
        days: 生成天数
        base_load_kw: 基础负荷（kW）
        peak_load_kw: 峰值负荷（kW）
        output_file: 输出文件名
    """
    
    # 生成时间序列（15分钟间隔）
    start = pd.to_datetime(start_date)
    timestamps = pd.date_range(start, periods=days*96, freq='15min')
    
    # 生成负荷数据
    loads = []
    for ts in timestamps:
        hour = ts.hour
        
        # 模拟日负荷曲线（早高峰、晚高峰）
        if 6 <= hour < 9:  # 早高峰
            load = base_load_kw + (peak_load_kw - base_load_kw) * 0.7
        elif 10 <= hour < 15:  # 午间高峰
            load = base_load_kw + (peak_load_kw - base_load_kw) * 0.9
        elif 18 <= hour < 22:  # 晚高峰（最高）
            load = base_load_kw + (peak_load_kw - base_load_kw) * 1.0
        elif 0 <= hour < 6:  # 深夜低谷
            load = base_load_kw * 0.3
        else:  # 其他时段
            load = base_load_kw * 0.6
        
        # 添加随机波动（±5%）
        load = load * (1 + np.random.uniform(-0.05, 0.05))
        loads.append(load)
    
    # 创建 DataFrame
    df = pd.DataFrame({
        'timestamp': timestamps,
        'load_kw': loads
    })
    
    # 格式化时间戳为 ISO8601 字符串
    df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
    
    # 保存为 CSV
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"✅ 已生成测试数据: {output_file}")
    print(f"📊 数据统计:")
    print(f"  - 时间范围: {df['timestamp'].iloc[0]} 至 {df['timestamp'].iloc[-1]}")
    print(f"  - 数据点数: {len(df)} 个（{days} 天 × 96 点/天）")
    print(f"  - 负荷范围: {df['load_kw'].min():.1f} - {df['load_kw'].max():.1f} kW")
    print(f"  - 平均负荷: {df['load_kw'].mean():.1f} kW")
    
    return df

def print_tou_schedule_recommendation():
    """打印推荐的分时电价配置"""
    print("\n" + "="*60)
    print("📋 推荐的分时电价配置（确保放电窗口有价格差异）")
    print("="*60)
    
    print("\n【时段划分建议】（适用于全年）")
    print("  深谷: 00:00-06:00  →  谷电价 0.50 元/kWh  →  充电时段 ✅")
    print("  平段: 06:00-08:00  →  平电价 0.80 元/kWh  →  待机")
    print("  峰段: 08:00-11:00  →  峰电价 1.20 元/kWh  →  放电 ⚡")
    print("  尖段: 11:00-13:00  →  尖电价 1.50 元/kWh  →  放电 🔥 （优先目标）")
    print("  峰段: 13:00-17:00  →  峰电价 1.20 元/kWh  →  放电 ⚡")
    print("  平段: 17:00-18:00  →  平电价 0.80 元/kWh  →  待机")
    print("  尖段: 18:00-21:00  →  尖电价 1.50 元/kWh  →  放电 🔥 （优先目标）")
    print("  峰段: 21:00-22:00  →  峰电价 1.20 元/kWh  →  放电 ⚡")
    print("  平段: 22:00-24:00  →  平电价 0.80 元/kWh  →  待机")
    
    print("\n【关键设置】")
    print("  ✅ 放电窗口必须包含：尖段(1.5元) + 峰段(1.2元) + 平段(0.8元)")
    print("  ✅ 这样才能验证尖段优先策略的效果（优先向1.5元时段分配能量）")
    print("  ⚠️  如果放电窗口内价格都一样，两种策略结果将完全相同！")
    
    print("\n【验证方法】")
    print("  1. 使用生成的测试数据上传到 Load Analysis 页")
    print("  2. 在 Price Editor 页配置上述分时电价")
    print("  3. 在 Strategy Comparison 页运行对比分析")
    print("  4. 观察浏览器控制台（F12）的详细日志")
    print("  5. 查看对比结果，尖段优先策略应有 5-15% 的收益提升")
    
    print("\n【预期差异】")
    print("  时序放电: 按时间顺序分配，尖/峰/平段平均分配能量")
    print("  尖段优先: 优先向尖段分配，尖段分配满后才分配峰段和平段")
    print("  收益提升: 因为更多能量在高价时段放电，预期提升 10-15%")
    print("="*60 + "\n")

if __name__ == "__main__":
    # 生成测试数据
    df = generate_test_load_data(
        start_date="2024-01-01",
        days=365,
        base_load_kw=500,
        peak_load_kw=1000,
        output_file="负荷测试数据/test_load_price_diff.csv"
    )
    
    # 打印配置建议
    print_tou_schedule_recommendation()
    
    print("\n🎯 下一步操作:")
    print("  1. 将生成的 CSV 文件上传到系统")
    print("  2. 按照上述推荐配置分时电价")
    print("  3. 进入 Strategy Comparison 页运行对比")
    print("  4. 查看控制台日志和对比结果")
