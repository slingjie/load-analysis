"""
测试数据流 - 调试报告生成时数据为0的问题
"""
import requests
import json

# 模拟前端发送的实际请求
url = 'http://localhost:8000/api/deepseek/project-summary'

# 测试1: 空数据（模拟当前问题）
print("=" * 80)
print("测试1: 发送空数据（模拟当前用户遇到的问题）")
print("=" * 80)

empty_data = {
    'project_name': '测试项目',
    'project_location': '测试地点',
    'period_start': '2025-11-24',
    'period_end': '2025-11-24',
    # load_profile, storage_config, storage_results 都为空或undefined
}

print("\n📤 发送请求:")
print(json.dumps(empty_data, indent=2, ensure_ascii=False))

try:
    response = requests.post(url, json=empty_data, timeout=60)
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ 成功！状态码: {response.status_code}")
        print(f"报告长度: {len(result['markdown'])} 字符")
        
        # 检查报告中的关键数值
        markdown = result['markdown']
        if '约 0.00' in markdown or '约 0.0' in markdown:
            print("\n❌ 问题确认：报告中包含大量 0 值")
            print("示例片段：")
            lines = markdown.split('\n')
            for i, line in enumerate(lines):
                if '约 0.' in line:
                    print(f"  行 {i}: {line}")
                    if i > 10:  # 只显示前几个
                        print("  ...")
                        break
        else:
            print("\n✅ 报告中没有 0 值")
    else:
        print(f"\n❌ 失败: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"\n❌ 错误: {str(e)}")

# 测试2: 完整数据
print("\n" + "=" * 80)
print("测试2: 发送完整数据（验证系统功能）")
print("=" * 80)

complete_data = {
    'project_name': '某医院储能项目',
    'project_location': '安徽省合肥市',
    'period_start': '2025-01-01',
    'period_end': '2025-01-31',
    'load_profile': {
        'avgLoad': '约 1200.50 kW',
        'peakLoad': '约 2500.00 kW',
        'valleyLoad': '约 400.00 kW',
        'peakValleyDifferenceDescription': '峰谷差约 2100.00 kW',
        'seasonalPattern': '评估周期：2025-01-01 至 2025-01-31'
    },
    'storage_config': {
        'capacityMWh': '4.00',
        'powerMW': '2.00',
        'configPerspective': '按容方案',
        'efficiencyDescription': '往返效率约 88%',
        'socRangeDescription': 'SOC 范围 10%-90%',
        'reserveMarginDescription': '充电余量 10.0%，放电余量 10.0%'
    },
    'storage_results': {
        'effectiveAnnualCycles': '约 280.0 次/年',
        'dailyCycles': '日均约 0.77 次',
        'utilizationHoursRangeDetail': '年度约 560 小时',
        'firstYearRevenueDetail': '约 45.50 万元',
        'revenuePerUnitJudgement': '收益水平中等偏上'
    },
    'quality_report': {
        'loadMissingRateDescription': '缺失 2 天，共 48 小时',
        'impactOnConclusion': '数据质量对结论影响较小'
    }
}

print("\n📤 发送请求（带完整数据）:")
print("（省略详细内容，请看上面的 complete_data）")

try:
    response = requests.post(url, json=complete_data, timeout=60)
    if response.status_code == 200:
        result = response.json()
        print(f"\n✅ 成功！状态码: {response.status_code}")
        print(f"报告长度: {len(result['markdown'])} 字符")
        
        # 检查报告中的关键数值
        markdown = result['markdown']
        if '约 45.50 万元' in markdown and '约 280.0 次/年' in markdown:
            print("\n✅ 数据正确传递：报告中包含实际数值")
            print("示例片段：")
            lines = markdown.split('\n')
            for i, line in enumerate(lines):
                if '45.50' in line or '280.0' in line or '1200.50' in line:
                    print(f"  {line.strip()}")
        else:
            print("\n❌ 数据未正确传递")
        
        # 保存完整报告
        with open('test_complete_data_report.md', 'w', encoding='utf-8') as f:
            f.write(markdown)
        print("\n✅ 完整报告已保存到 test_complete_data_report.md")
    else:
        print(f"\n❌ 失败: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"\n❌ 错误: {str(e)}")

print("\n" + "=" * 80)
print("总结")
print("=" * 80)
print("""
如果测试1生成的报告全是0，测试2生成的报告有实际数值，
说明问题出在前端传递的数据上。

请检查：
1. 浏览器控制台中的日志 - 查找 🔍 [buildLoadProfile] 等日志
2. Network 标签中的请求体 - 查看实际发送的 JSON
3. 确认用户是否已经：
   - 上传了负荷数据
   - 运行了储能测算
""")
