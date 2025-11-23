"""
快速诊断脚本 - 检查系统状态和数据流
"""
import sys
import requests
import json
from datetime import datetime

def print_section(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

def check_backend():
    """检查后端服务是否运行"""
    print_section("步骤 1/4: 检查后端服务")
    try:
        response = requests.get('http://localhost:8000/docs', timeout=5)
        if response.status_code == 200:
            print("✅ 后端服务正在运行 (http://localhost:8000)")
            return True
        else:
            print(f"❌ 后端服务响应异常: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务 (http://localhost:8000)")
        print("\n请在另一个终端运行：")
        print("  .\\start_backend_with_env.ps1")
        print("或:")
        print("  $env:DEEPSEEK_API_KEY='sk-3008dc675fad4414abee5ea2b75ed54f'")
        print("  uvicorn backend.app:app --reload")
        return False
    except Exception as e:
        print(f"❌ 错误: {e}")
        return False

def test_api_with_empty_data():
    """测试API接收空数据的行为"""
    print_section("步骤 2/4: 测试空数据场景")
    print("（模拟用户未上传数据直接生成报告的情况）\n")
    
    url = 'http://localhost:8000/api/deepseek/project-summary'
    data = {
        'project_name': '诊断测试项目',
        'project_location': '测试地点',
        'period_start': '2025-11-24',
        'period_end': '2025-11-24',
    }
    
    print("📤 发送空数据请求...")
    try:
        response = requests.post(url, json=data, timeout=60)
        if response.status_code == 200:
            result = response.json()
            markdown = result['markdown']
            
            # 检查是否包含大量0值
            zero_count = markdown.count('约 0.00') + markdown.count('约 0.0')
            
            if zero_count > 5:
                print(f"⚠️  报告生成成功，但包含 {zero_count} 个零值")
                print("   这是正常的，因为没有提供数据")
                print("\n示例内容：")
                lines = [l for l in markdown.split('\n') if '约 0.' in l][:3]
                for line in lines:
                    print(f"   {line.strip()}")
                return True
            else:
                print("✅ 报告生成成功（无零值问题）")
                return True
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(f"   错误信息: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ 请求错误: {str(e)}")
        return False

def test_api_with_complete_data():
    """测试API接收完整数据的行为"""
    print_section("步骤 3/4: 测试完整数据场景")
    print("（验证系统能否正确处理和展示数据）\n")
    
    url = 'http://localhost:8000/api/deepseek/project-summary'
    data = {
        'project_name': '测试储能项目',
        'project_location': '安徽省',
        'period_start': '2025-01-01',
        'period_end': '2025-12-31',
        'load_profile': {
            'avgLoad': '约 1234.56 kW',
            'peakLoad': '约 2345.67 kW',
            'valleyLoad': '约 456.78 kW',
            'peakValleyDifferenceDescription': '峰谷差约 1888.89 kW',
            'seasonalPattern': '全年数据'
        },
        'storage_config': {
            'capacityMWh': '4.00',
            'powerMW': '2.00',
            'configPerspective': '按容方案',
            'efficiencyDescription': '往返效率约 88%',
            'socRangeDescription': 'SOC 范围 10%-90%',
        },
        'storage_results': {
            'effectiveAnnualCycles': '约 280.5 次/年',
            'dailyCycles': '日均约 0.77 次',
            'utilizationHoursRangeDetail': '年度约 561 小时',
            'firstYearRevenueDetail': '约 45.50 万元',
            'revenuePerUnitJudgement': '收益水平中等偏上'
        },
        'quality_report': {
            'loadMissingRateDescription': '缺失 2 天，共 48 小时',
            'impactOnConclusion': '数据质量对结论影响较小'
        }
    }
    
    print("📤 发送完整数据请求...")
    try:
        response = requests.post(url, json=data, timeout=60)
        if response.status_code == 200:
            result = response.json()
            markdown = result['markdown']
            
            # 检查关键数值是否出现在报告中
            key_values = ['1234.56', '2345.67', '4.00', '2.00', '280.5', '45.50']
            found_values = [v for v in key_values if v in markdown]
            
            if len(found_values) >= 4:
                print(f"✅ 系统工作正常！报告中包含 {len(found_values)}/{len(key_values)} 个测试数值")
                print("\n找到的数值：")
                for val in found_values:
                    # 找到包含该数值的行
                    for line in markdown.split('\n'):
                        if val in line:
                            print(f"   {line.strip()}")
                            break
                
                # 保存报告
                filename = f'diagnostic_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.md'
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(markdown)
                print(f"\n✅ 完整报告已保存到: {filename}")
                return True
            else:
                print(f"❌ 数据传递可能有问题，只找到 {len(found_values)}/{len(key_values)} 个测试数值")
                return False
        else:
            print(f"❌ API调用失败: {response.status_code}")
            print(f"   错误信息: {response.text[:200]}")
            return False
    except Exception as e:
        print(f"❌ 请求错误: {str(e)}")
        return False

def print_diagnostic_summary(backend_ok, empty_ok, complete_ok):
    """打印诊断总结"""
    print_section("步骤 4/4: 诊断总结")
    
    if backend_ok and empty_ok and complete_ok:
        print("✅ 系统完全正常！")
        print("\n您报告中数据为0的原因是：")
        print("   您尚未上传负荷数据或运行储能测算")
        print("\n正确使用流程：")
        print("   1. 打开浏览器访问 http://localhost:5173/")
        print("   2. 切换到 'Load Analysis' 页面")
        print("   3. 点击 '上传负荷文件' 按钮，选择CSV文件")
        print("   4. 等待数据分析完成")
        print("   5. 切换到 'Storage Cycles' 页面")
        print("   6. 配置储能参数（容量、功率等）")
        print("   7. 点击 'Calculate' 按钮")
        print("   8. 等待计算完成")
        print("   9. 切换到 'Project Summary' 页面")
        print("   10. 填写项目信息并生成报告")
        print("\n这样生成的报告就会包含实际数值了！")
    elif backend_ok and complete_ok:
        print("✅ 后端功能正常")
        print("⚠️  空数据测试有问题，但不影响正常使用")
    elif backend_ok:
        print("⚠️  后端服务运行正常，但API功能异常")
        print("\n可能的问题：")
        print("   1. DeepSeek API Key未配置或无效")
        print("   2. 网络连接问题")
        print("   3. backend代码有错误")
        print("\n请检查：")
        print("   - 环境变量 DEEPSEEK_API_KEY 是否正确设置")
        print("   - 后端日志中是否有错误信息")
    else:
        print("❌ 后端服务未运行")
        print("\n请先启动后端服务：")
        print("   .\\start_backend_with_env.ps1")

def main():
    print("╔" + "═" * 78 + "╗")
    print("║" + " " * 20 + "项目评估报告系统 - 快速诊断工具" + " " * 21 + "║")
    print("╚" + "═" * 78 + "╝")
    print("\n本工具将检查系统状态并诊断数据为0的问题\n")
    
    # 运行诊断步骤
    backend_ok = check_backend()
    
    if not backend_ok:
        print("\n❌ 后端服务未运行，无法继续诊断")
        print("   请先启动后端服务，然后重新运行此脚本")
        sys.exit(1)
    
    empty_ok = test_api_with_empty_data()
    complete_ok = test_api_with_complete_data()
    
    # 打印总结
    print_diagnostic_summary(backend_ok, empty_ok, complete_ok)
    
    print("\n" + "=" * 80)
    print("诊断完成！")
    print("=" * 80)
    
    if not (backend_ok and complete_ok):
        print("\n如需进一步帮助，请提供：")
        print("   1. 本次诊断的完整输出")
        print("   2. 后端终端的日志信息")
        print("   3. 浏览器开发者工具的Console日志")
        sys.exit(1)

if __name__ == '__main__':
    main()
