"""
测试经济性现金流报表导出功能

验证：
1. 导出函数能否成功生成 ZIP 文件
2. ZIP 内是否包含年度现金流明细和经济性指标汇总
3. CSV 文件格式和内容是否正确
"""

import os
import sys
import zipfile
import csv
from pathlib import Path

# 添加 backend 目录到路径
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))

from services.economics import compute_economics, export_economics_cashflow_report, EconomicsResult


def test_export_economics_report():
    """测试经济性报表导出"""
    print("=" * 60)
    print("测试：导出经济性现金流报表（包含用户分成和放电量）")
    print("=" * 60)
    
    # 1. 准备测试数据
    first_year_revenue = 100000  # 首年收益 10 万元
    project_years = 15
    annual_om_cost = 1000  # 年运维成本 1000 元
    first_year_decay_rate = 0.03
    subsequent_decay_rate = 0.02
    capex_per_wh = 1.0
    installed_capacity_kwh = 100
    cell_replacement_year = 8
    cell_replacement_cost = 5000
    first_year_energy_kwh = 50000  # 首年能量 50000 kWh
    user_share_percent = 30.0  # 用户分成 30%
    
    print(f"\n测试参数:")
    print(f"  首年收益: {first_year_revenue:,.0f} 元")
    print(f"  项目年限: {project_years} 年")
    print(f"  年运维成本: {annual_om_cost:,.0f} 元")
    print(f"  首年衰减率: {first_year_decay_rate * 100:.1f}%")
    print(f"  后续衰减率: {subsequent_decay_rate * 100:.1f}%")
    print(f"  CAPEX单价: {capex_per_wh:.2f} 元/Wh")
    print(f"  装机容量: {installed_capacity_kwh:.0f} kWh")
    print(f"  电芯更换年份: 第 {cell_replacement_year} 年")
    print(f"  电芯更换成本: {cell_replacement_cost:,.0f} 元")
    print(f"  首年能量: {first_year_energy_kwh:,.0f} kWh")
    print(f"  用户分成比例: {user_share_percent:.1f}%")
    
    # 2. 计算经济性结果
    print("\n步骤 1: 计算经济性结果...")
    result = compute_economics(
        first_year_revenue=first_year_revenue,
        project_years=project_years,
        annual_om_cost=annual_om_cost,
        first_year_decay_rate=first_year_decay_rate,
        subsequent_decay_rate=subsequent_decay_rate,
        capex_per_wh=capex_per_wh,
        installed_capacity_kwh=installed_capacity_kwh,
        first_year_energy_kwh=first_year_energy_kwh,
        cell_replacement_year=cell_replacement_year,
        cell_replacement_cost=cell_replacement_cost,
    )
    
    print(f"✓ 计算成功")
    print(f"  总投资: {result.capex_total:,.2f} 元")
    print(f"  IRR: {result.irr * 100:.2f}%" if result.irr else "  IRR: 无法收敛")
    print(f"  静态回收期: {result.static_payback_years:.2f} 年" if result.static_payback_years else "  静态回收期: 超出项目周期")
    print(f"  项目末累计净现金流: {result.final_cumulative_net_cashflow:,.2f} 元")
    if result.static_lcoe:
        print(f"  静态度电成本: {result.static_lcoe:.4f} 元/kWh")
    if result.lcoe_ratio:
        print(f"  经济可行性比值: {result.lcoe_ratio:.4f}")
        print(f"  筛选结论: {result.screening_result}")
    
    # 3. 计算年度放电量（与前端逻辑一致）
    print("\n步骤 2: 计算年度放电量...")
    yearly_discharge_energy_kwh = []
    current_base_energy = first_year_energy_kwh
    phase_start_year = 1
    
    for year_index in range(1, project_years + 1):
        # 换电芯年份视为新阶段首年：放电量重置为首年水平
        if cell_replacement_year and year_index == cell_replacement_year:
            current_base_energy = first_year_energy_kwh
            phase_start_year = year_index
        
        years_in_phase = year_index - phase_start_year  # 0 表示阶段首年
        energy_this_year = (
            current_base_energy *
            (1 - first_year_decay_rate) *
            pow(1 - subsequent_decay_rate, years_in_phase)
        )
        yearly_discharge_energy_kwh.append(energy_this_year)
    
    print(f"✓ 计算完成，共 {len(yearly_discharge_energy_kwh)} 年数据")
    print(f"  第1年放电量: {yearly_discharge_energy_kwh[0]:,.2f} kWh")
    print(f"  第{cell_replacement_year}年放电量（换电芯）: {yearly_discharge_energy_kwh[cell_replacement_year-1]:,.2f} kWh")
    
    # 4. 导出报表
    print(f"\n步骤 3: 导出经济性报表（用户分成 {user_share_percent}%）...")
    zip_filename = export_economics_cashflow_report(
        result=result,
        user_share_percent=user_share_percent,
        yearly_discharge_energy_kwh=yearly_discharge_energy_kwh,
    )
    
    print(f"✓ 报表生成成功: {zip_filename}")
    
    # 5. 验证 ZIP 文件
    print("\n步骤 4: 验证 ZIP 文件...")
    zip_path = os.path.join("outputs", zip_filename)
    
    if not os.path.exists(zip_path):
        print(f"✗ 错误: ZIP 文件不存在: {zip_path}")
        return False
    
    print(f"✓ ZIP 文件存在: {zip_path}")
    print(f"  文件大小: {os.path.getsize(zip_path):,} 字节")
    
    # 5. 检查 ZIP 内容
    print("\n步骤 5: 检查 ZIP 内容...")
    with zipfile.ZipFile(zip_path, 'r') as zipf:
        file_list = zipf.namelist()
        print(f"✓ ZIP 包含 {len(file_list)} 个文件:")
        for fname in file_list:
            print(f"  - {fname}")
        
        # 检查必需文件
        expected_files = ['年度现金流明细', '经济性指标汇总']
        for expected in expected_files:
            found = any(expected in fname for fname in file_list)
            if found:
                print(f"✓ 找到必需文件: {expected}")
            else:
                print(f"✗ 缺少必需文件: {expected}")
                return False
        
        # 6. 验证年度现金流明细
        print("\n步骤 6: 验证年度现金流明细...")
        cashflow_file = [f for f in file_list if '年度现金流明细' in f][0]
        
        with zipf.open(cashflow_file) as f:
            # 读取 CSV 内容
            content = f.read().decode('utf-8-sig')
            reader = csv.reader(content.splitlines())
            rows = list(reader)
            
            print(f"✓ 年度现金流明细包含 {len(rows)} 行（含表头）")
            print(f"  表头: {rows[0]}")
            
            # 验证列数
            expected_cols = 9  # 年份、原年度总收益、用户方年度收益、项目方年度收益、储能放电量、运维成本、电芯更换成本、年度净现金流、累计净现金流
            if len(rows[0]) == expected_cols:
                print(f"✓ 列数正确: {expected_cols} 列")
            else:
                print(f"✗ 列数错误: 期望 {expected_cols} 列，实际 {len(rows[0])} 列")
                return False
            
            # 显示前 3 年和换电芯年的数据
            print(f"\n  前 3 年数据:")
            for i in range(1, min(4, len(rows))):
                year_data = rows[i]
                print(f"    年份{year_data[0]}: 原总收益={year_data[1]}, 用户收益={year_data[2]}, 项目收益={year_data[3]}, 放电量={year_data[4]}kWh")
            
            if cell_replacement_year < len(rows):
                print(f"\n  第 {cell_replacement_year} 年（换电芯年）:")
                year_data = rows[cell_replacement_year]
                print(f"    {year_data}")
        
        # 7. 验证经济性指标汇总
        print("\n步骤 7: 验证经济性指标汇总...")
        summary_file = [f for f in file_list if '经济性指标汇总' in f][0]
        
        with zipf.open(summary_file) as f:
            content = f.read().decode('utf-8-sig')
            reader = csv.reader(content.splitlines())
            rows = list(reader)
            
            print(f"✓ 经济性指标汇总包含 {len(rows)} 行（含表头）")
            print(f"  表头: {rows[0]}")
            
            # 显示所有指标
            print(f"\n  经济性指标:")
            for row in rows[1:]:
                print(f"    {row[0]}: {row[1]} {row[2]}")
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = test_export_economics_report()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
