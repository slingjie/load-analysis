"""测试业务报表导出功能（包含年度现金流明细）"""
import sys
sys.path.append('backend')

from services.cycles import export_business_report
from pathlib import Path
import tempfile
import traceback
import zipfile

# 创建测试数据 - 模拟实际API调用时的数据
test_days = [{
    'date': '2025-01-01',
    'cycles': 0.0,
    'is_valid': True,
    'point_count': 2
}]

test_months = [{
    'year_month': '2025-01',
    'cycles': 0.0
}]

test_year = {
    'year': 2025,
    'cycles': 0.0
}

# 测试1: 空 profit_summary
print("=" * 80)
print("测试1: 空 profit_summary（不包含年度现金流）")
print("=" * 80)
with tempfile.TemporaryDirectory() as tmpdir:
    try:
        result = export_business_report(
            Path(tmpdir),
            'test.csv',
            test_days,
            test_months,
            test_year,
            profit_summary={'days': {}, 'months': {}, 'year': None},
            step15_df=None,
            window_debug=None,
            energy_formula='physics'
        )
        print('✓ 成功生成报表:', result)
        print('✓ 文件存在:', result.exists())
        print('✓ 文件大小:', result.stat().st_size, 'bytes')
        
        # 检查 ZIP 内容
        with zipfile.ZipFile(result, 'r') as zf:
            files = zf.namelist()
            print('✓ ZIP 内包含的文件:')
            for f in files:
                print('  -', f)
            if any('年度现金流明细' in f for f in files):
                print('  ⚠️  包含年度现金流明细（预期不应包含）')
            else:
                print('  ✓ 不包含年度现金流明细（符合预期）')
    except Exception as e:
        print('✗ 错误:', str(e))
        traceback.print_exc()

# 测试2: 有数据的 profit_summary（包含年度现金流）
print("\n" + "=" * 80)
print("测试2: 有数据的 profit_summary（包含年度现金流）")
print("=" * 80)
profit_summary_with_data = {
    'days': {
        '2025-01-01': {
            'main': {
                'revenue': 100.0,
                'cost': 20.0,
                'profit': 80.0,
                'discharge_energy_kwh': 50.0,
                'charge_energy_kwh': 60.0,
                'profit_per_kwh': 1.6
            }
        }
    },
    'months': {
        '2025-01': {
            'main': {
                'revenue': 100.0,
                'cost': 20.0,
                'profit': 80.0,
                'discharge_energy_kwh': 50.0,
                'charge_energy_kwh': 60.0,
                'profit_per_kwh': 1.6
            }
        }
    },
    'year': {
        'main': {
            'revenue': 3650.0,
            'cost': 730.0,
            'profit': 2920.0,
            'discharge_energy_kwh': 18250.0,
            'charge_energy_kwh': 21900.0,
            'profit_per_kwh': 0.16
        },
        'physics': {
            'revenue': 3800.0,
            'cost': 760.0,
            'profit': 3040.0,
            'discharge_energy_kwh': 19000.0,
            'charge_energy_kwh': 22000.0,
            'profit_per_kwh': 0.16
        },
        'sample': {
            'revenue': 3500.0,
            'cost': 700.0,
            'profit': 2800.0,
            'discharge_energy_kwh': 17500.0,
            'charge_energy_kwh': 21800.0,
            'profit_per_kwh': 0.16
        }
    }
}

with tempfile.TemporaryDirectory() as tmpdir:
    try:
        result = export_business_report(
            Path(tmpdir),
            'test_with_data.csv',
            test_days,
            test_months,
            test_year,
            profit_summary=profit_summary_with_data,
            step15_df=None,
            window_debug=None,
            energy_formula='physics'
        )
        print('✓ 成功生成报表:', result)
        print('✓ 文件存在:', result.exists())
        print('✓ 文件大小:', result.stat().st_size, 'bytes')
        
        # 检查 ZIP 内容
        with zipfile.ZipFile(result, 'r') as zf:
            files = zf.namelist()
            print('✓ ZIP 内包含的文件:')
            for f in files:
                print('  -', f)
            
            # 检查年度现金流明细文件
            cashflow_files = [f for f in files if '年度现金流明细' in f]
            if cashflow_files:
                print('\n✓ 找到年度现金流明细文件:', cashflow_files[0])
                # 读取并显示内容
                import pandas as pd
                import io
                with zf.open(cashflow_files[0]) as cf:
                    df = pd.read_csv(io.TextIOWrapper(cf, encoding='utf-8-sig'))
                    print('✓ 年度现金流明细内容:')
                    print(df.to_string())
                    print('\n✓ 列名:', df.columns.tolist())
                    print('✓ 数据行数:', len(df))
            else:
                print('\n✗ 未找到年度现金流明细文件')
    except Exception as e:
        print('✗ 错误:', str(e))
        traceback.print_exc()

print("\n" + "=" * 80)
print("测试完成")
print("=" * 80)
