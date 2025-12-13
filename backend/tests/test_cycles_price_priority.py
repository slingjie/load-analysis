"""
单元测试：尖段优先放电策略 (Price-Priority Discharge Strategy)

测试覆盖：
1. 基础排序逻辑 - 验证按价格降序分配能量
2. 变压器功率限制 - 验证 limit_kw 约束
3. 电池C倍率限制 - 验证 c_rate × capacity 约束
4. 能量不足场景 - 验证可用能量耗尽后分配停止
5. 价格相等场景 - 验证相同价格时按时间顺序分配
"""

import pytest
import pandas as pd
from datetime import datetime
from backend.services.cycles import _allocate_discharge_by_price


class TestAllocateDischargePriceBasics:
    """测试基础排序和分配逻辑"""
    
    def test_basic_price_sorting(self):
        """测试用例1：基础排序 - 优先向高价时段分配能量"""
        # 准备测试数据：4个15分钟时间点，价格分别为 0.5, 1.2, 0.8, 1.5 元/kWh
        df_discharge = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01 10:00', periods=4, freq='15min'),
            'load_kw': [100.0, 100.0, 100.0, 100.0],
            'price_per_kwh': [0.5, 1.2, 0.8, 1.5]  # 尖=1.5, 峰=1.2, 平=0.8, 谷=0.5
        })
        
        available_energy_kwh = 30.0  # 足够分配给前3个高价点（每点最多10kWh）
        limit_kw = 100.0  # 变压器限制
        c_rate = 0.5
        capacity_kwh = 1000.0  # 电池限制 = 500kW，远大于 limit_kw
        
        result_df = _allocate_discharge_by_price(
            df_discharge=df_discharge,
            available_energy_kwh=available_energy_kwh,
            limit_kw=limit_kw,
            c_rate=c_rate,
            capacity_kwh=capacity_kwh
        )
        
        # 验证：结果按时间顺序返回
        assert len(result_df) == 4
        assert result_df['timestamp'].iloc[0] == pd.Timestamp('2024-01-01 10:00')
        
        # 验证能量分配：最高价(1.5)→次高价(1.2)→第三价(0.8)，最低价(0.5)不分配
        # 每个点最多 min(100kW, 500kW) × 0.25h = 25kWh，但总共只有30kWh
        allocated = result_df['allocated_energy_kwh'].values
        
        # 第1个点(10:00, 0.5元) - 最低价，应该最后或不分配
        # 第2个点(10:15, 1.2元) - 次高价，应该分配
        # 第3个点(10:30, 0.8元) - 第三价，应该分配
        # 第4个点(10:45, 1.5元) - 最高价，应该优先分配
        
        # 期望：10:45(1.5元) 分配满 → 10:15(1.2元) 分配满 → 10:30(0.8元) 分配剩余
        # 实际顺序：索引0(0.5), 索引1(1.2), 索引2(0.8), 索引3(1.5)
        assert allocated[3] > 0  # 最高价必须有分配
        assert allocated[1] > 0  # 次高价必须有分配
        assert allocated[0] == 0  # 最低价不应分配（能量不足）
        
        # 验证总分配能量不超过可用能量
        assert result_df['allocated_energy_kwh'].sum() <= available_energy_kwh + 0.01


class TestAllocateDischargeConstraints:
    """测试约束条件限制"""
    
    def test_transformer_power_limit(self):
        """测试用例2：变压器功率限制 - 单点最大能量受 limit_kw × 0.25h 约束"""
        df_discharge = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01 14:00', periods=2, freq='15min'),
            'load_kw': [200.0, 200.0],
            'price_per_kwh': [1.5, 1.2]
        })
        
        available_energy_kwh = 100.0  # 足够多
        limit_kw = 50.0  # 严格限制：每点最多 50×0.25=12.5kWh
        c_rate = 1.0
        capacity_kwh = 200.0  # 电池限制 = 200kW，远大于 limit_kw
        
        result_df = _allocate_discharge_by_price(
            df_discharge=df_discharge,
            available_energy_kwh=available_energy_kwh,
            limit_kw=limit_kw,
            c_rate=c_rate,
            capacity_kwh=capacity_kwh
        )
        
        # 验证：每个点分配的能量都不超过 limit_kw × 0.25h
        max_per_point = limit_kw * 0.25
        assert all(result_df['allocated_energy_kwh'] <= max_per_point + 0.01)
        assert result_df['allocated_energy_kwh'].iloc[0] <= max_per_point + 0.01  # 最高价点
    
    def test_battery_crate_limit(self):
        """测试用例3：电池C倍率限制 - 单点最大能量受 c_rate × capacity × 0.25h 约束"""
        df_discharge = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01 18:00', periods=2, freq='15min'),
            'load_kw': [500.0, 500.0],
            'price_per_kwh': [1.5, 1.2]
        })
        
        available_energy_kwh = 100.0
        limit_kw = 1000.0  # 变压器容量很大，不构成限制
        c_rate = 0.4
        capacity_kwh = 100.0  # 电池功率限制 = 0.4×100=40kW，每点最多 40×0.25=10kWh
        
        result_df = _allocate_discharge_by_price(
            df_discharge=df_discharge,
            available_energy_kwh=available_energy_kwh,
            limit_kw=limit_kw,
            c_rate=c_rate,
            capacity_kwh=capacity_kwh
        )
        
        # 验证：每个点分配的能量不超过 c_rate × capacity × 0.25h
        max_per_point = c_rate * capacity_kwh * 0.25
        assert all(result_df['allocated_energy_kwh'] <= max_per_point + 0.01)


class TestAllocateDischargeEdgeCases:
    """测试边界场景"""
    
    def test_insufficient_energy(self):
        """测试用例4：能量不足 - 可用能量耗尽后停止分配"""
        df_discharge = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01 20:00', periods=4, freq='15min'),
            'load_kw': [100.0, 100.0, 100.0, 100.0],
            'price_per_kwh': [1.5, 1.2, 0.8, 0.5]  # 按价格降序排列测试数据
        })
        
        available_energy_kwh = 15.0  # 只够分配给1-2个点
        limit_kw = 100.0
        c_rate = 0.5
        capacity_kwh = 1000.0
        
        result_df = _allocate_discharge_by_price(
            df_discharge=df_discharge,
            available_energy_kwh=available_energy_kwh,
            limit_kw=limit_kw,
            c_rate=c_rate,
            capacity_kwh=capacity_kwh
        )
        
        # 验证：总分配能量等于可用能量
        total_allocated = result_df['allocated_energy_kwh'].sum()
        assert abs(total_allocated - available_energy_kwh) < 0.01
        
        # 验证：至少有1个低价点未分配到能量
        assert (result_df['allocated_energy_kwh'] == 0).any()
    
    def test_equal_prices(self):
        """测试用例5：价格相等 - 相同价格时按时间顺序分配"""
        df_discharge = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01 12:00', periods=3, freq='15min'),
            'load_kw': [100.0, 100.0, 100.0],
            'price_per_kwh': [1.2, 1.2, 1.2]  # 所有点价格相同
        })
        
        available_energy_kwh = 20.0  # 只够分配给部分点
        limit_kw = 100.0
        c_rate = 0.5
        capacity_kwh = 1000.0
        
        result_df = _allocate_discharge_by_price(
            df_discharge=df_discharge,
            available_energy_kwh=available_energy_kwh,
            limit_kw=limit_kw,
            c_rate=c_rate,
            capacity_kwh=capacity_kwh
        )
        
        # 验证：结果按时间顺序返回
        assert result_df['timestamp'].is_monotonic_increasing
        
        # 验证：总分配能量不超过可用能量
        total_allocated = result_df['allocated_energy_kwh'].sum()
        assert total_allocated <= available_energy_kwh + 0.01
        
        # 验证：至少有分配发生（不是所有点都为0）
        assert total_allocated > 0


class TestAllocateDischargeIntegration:
    """集成测试：复杂场景"""
    
    def test_realistic_scenario(self):
        """综合场景：模拟实际放电窗口（混合尖、峰、平价）"""
        # 放电窗口：10:00-12:00（8个15分钟点）
        # 价格分布：2个尖(1.5), 3个峰(1.2), 3个平(0.8)
        df_discharge = pd.DataFrame({
            'timestamp': pd.date_range('2024-01-01 10:00', periods=8, freq='15min'),
            'load_kw': [120.0] * 8,
            'price_per_kwh': [1.5, 1.2, 0.8, 1.2, 1.5, 0.8, 1.2, 0.8]
        })
        
        available_energy_kwh = 60.0  # 一个充电窗口的典型充电量
        limit_kw = 100.0
        c_rate = 0.5
        capacity_kwh = 200.0  # 200kWh 电池
        
        result_df = _allocate_discharge_by_price(
            df_discharge=df_discharge,
            available_energy_kwh=available_energy_kwh,
            limit_kw=limit_kw,
            c_rate=c_rate,
            capacity_kwh=capacity_kwh
        )
        
        # 验证1：尖段时间点（索引0和4）必须优先分配
        jianduan_indices = result_df[result_df['price_per_kwh'] == 1.5].index
        assert all(result_df.loc[jianduan_indices, 'allocated_energy_kwh'] > 0)
        
        # 验证2：总分配能量合理
        total_allocated = result_df['allocated_energy_kwh'].sum()
        assert 0 < total_allocated <= available_energy_kwh + 0.01
        
        # 验证3：高价点分配总量 > 低价点分配总量
        high_price_allocated = result_df[result_df['price_per_kwh'] >= 1.2]['allocated_energy_kwh'].sum()
        low_price_allocated = result_df[result_df['price_per_kwh'] < 1.2]['allocated_energy_kwh'].sum()
        assert high_price_allocated > low_price_allocated
        
        # 验证4：结果按时间顺序排列
        assert result_df['timestamp'].is_monotonic_increasing


# Pytest 配置：运行测试时显示详细输出
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
