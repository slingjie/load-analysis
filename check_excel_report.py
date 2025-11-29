"""检查 Excel 报表内容"""
import pandas as pd
from pathlib import Path

# 读取最新的报表
xlsx_path = Path(r"d:\Desktop\ai\1028负荷展示和tou配置\outputs\20251129_223719\points_payload_计算结果.xlsx")

print(f"检查报表: {xlsx_path}")
print("=" * 60)

# 读取所有 sheet 名称
xl = pd.ExcelFile(xlsx_path)
print(f"\n包含的 Sheet 列表 ({len(xl.sheet_names)} 个):")
for i, name in enumerate(xl.sheet_names, 1):
    print(f"  {i}. {name}")

# 检查 power_step15 sheet 是否存在，它包含负荷数据
if "power_step15" in xl.sheet_names:
    print("\n" + "=" * 60)
    print("power_step15 Sheet（逐15分钟功率/负荷明细）:")
    df = pd.read_excel(xlsx_path, sheet_name="power_step15")
    print(f"  行数: {len(df)}")
    print(f"  列名: {list(df.columns)}")
    
    # 检查关键列
    key_cols = ["load_kw", "load_with_storage_physics_kw", "load_with_storage_sample_kw", 
                "load_with_storage_main_kw", "p_grid_effect_main_kw", "p_batt_kw"]
    print(f"\n  关键负荷相关列:")
    for col in key_cols:
        if col in df.columns:
            print(f"    ✓ {col}: min={df[col].min():.2f}, max={df[col].max():.2f}")
        else:
            print(f"    ✗ {col}: 不存在")
    
    # 显示前几行
    print(f"\n  前5行数据预览:")
    cols_to_show = [c for c in ["timestamp", "load_kw", "load_with_storage_main_kw", "p_batt_kw", "op"] if c in df.columns]
    print(df[cols_to_show].head().to_string(index=False))
else:
    print("\n⚠️  power_step15 Sheet 不存在！")

# 检查其他重要 sheet
print("\n" + "=" * 60)
for sheet in ["days", "months", "profit_days", "profit_months"]:
    if sheet in xl.sheet_names:
        df = pd.read_excel(xlsx_path, sheet_name=sheet)
        print(f"\n{sheet} Sheet: {len(df)} 行, 列: {list(df.columns)[:5]}...")
