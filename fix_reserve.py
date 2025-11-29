"""修复放电余量限制"""
import re

file_path = r'd:\Desktop\ai\1028负荷展示和tou配置\backend\services\cycles.py'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

old_code = '''        # 禁止"余电上网"：不允许引入储能后的负荷变为负值
        # 注意：这里是针对电网视角的总负荷（原始负荷 + 储能影响），与计费口径无关。
        if load_kw > 0:
            max_discharge = max(-p_grid_phys, -p_grid_sample, 0.0)
            if max_discharge > 0:
                allowed_discharge = load_kw  # 最多只能把负荷削到 0
                if max_discharge > allowed_discharge + 1e-6:
                    scale_dis = allowed_discharge / max_discharge if allowed_discharge > 0 else 0.0
                    if scale_dis < 0:
                        scale_dis = 0.0
                    if scale_dis < 1.0:
                        p_batt *= scale_dis
                        e_in_phys *= scale_dis
                        e_out_phys *= scale_dis
                        e_in_sample *= scale_dis
                        e_out_sample *= scale_dis
                        p_grid_phys *= scale_dis
                        p_grid_sample *= scale_dis'''

new_code = '''        # 放电余量限制：确保引入储能后的负荷不低于 reserve_discharge_kw
        # 同时禁止"余电上网"（负荷不能为负）
        # 注意：这里是针对电网视角的总负荷（原始负荷 + 储能影响）
        if p_batt < 0:  # 仅在放电时检查
            max_discharge = max(-p_grid_phys, -p_grid_sample, 0.0)
            if max_discharge > 0:
                # 放电后负荷的下限 = max(reserve_discharge_kw, 0)
                min_load_after = max(reserve_dis, 0.0)
                # 最大允许削减量 = 当前负荷 - 下限
                allowed_discharge = max(load_kw - min_load_after, 0.0)
                if max_discharge > allowed_discharge + 1e-6:
                    scale_dis = allowed_discharge / max_discharge if allowed_discharge > 0 else 0.0
                    if scale_dis < 0:
                        scale_dis = 0.0
                    if scale_dis < 1.0:
                        p_batt *= scale_dis
                        e_in_phys *= scale_dis
                        e_out_phys *= scale_dis
                        e_in_sample *= scale_dis
                        e_out_sample *= scale_dis
                        p_grid_phys *= scale_dis
                        p_grid_sample *= scale_dis'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("✓ 修改成功！")
else:
    print("✗ 未找到匹配的代码块")
    # 尝试查找相似的内容
    if "禁止" in content and "余电上网" in content:
        print("文件中存在相关关键词，但格式可能不同")
        # 打印周围的内容
        idx = content.find("禁止")
        print(f"找到位置: {idx}")
        print(repr(content[idx:idx+500]))
