"""
测试 DeepSeek 项目总结 API
"""
import requests
import json

def test_deepseek_api():
    url = 'http://localhost:8000/api/deepseek/project-summary'
    data = {
        'project_name': '测试项目',
        'project_location': '测试地点',
        'period_start': '2025-01-01',
        'period_end': '2025-01-31'
    }
    
    print('=' * 60)
    print('测试 DeepSeek 项目总结 API')
    print('=' * 60)
    print(f'\n请求 URL: {url}')
    print(f'请求数据: {json.dumps(data, ensure_ascii=False, indent=2)}')
    print('\n正在调用接口...')
    
    try:
        response = requests.post(url, json=data, timeout=60)
        print(f'\n状态码: {response.status_code}')
        
        if response.status_code == 200:
            result = response.json()
            print('\n✓ 接口调用成功！')
            print('=' * 60)
            print(f'报告 ID: {result["report_id"]}')
            print(f'项目名称: {result["project_name"]}')
            print(f'评估周期: {result["period_start"]} ~ {result["period_end"]}')
            print(f'生成时间: {result["generated_at"]}')
            print(f'Markdown 长度: {len(result["markdown"])} 字符')
            
            if result.get("summary"):
                print('\n关键摘要:')
                for key, value in result["summary"].items():
                    if value:
                        print(f'  - {key}: {value}')
            
            print('\n报告内容预览 (前 500 字符):')
            print('-' * 60)
            print(result["markdown"][:500])
            if len(result["markdown"]) > 500:
                print('...')
            print('-' * 60)
            
            # 保存完整报告
            filename = f'{result["report_id"]}.md'
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(result["markdown"])
            print(f'\n✓ 完整报告已保存到: {filename}')
            
        else:
            print(f'\n✗ 请求失败')
            print(f'错误信息: {response.text}')
            
    except requests.exceptions.Timeout:
        print('\n✗ 请求超时 (60秒)')
        print('提示: DeepSeek API 可能需要较长时间响应，请稍后重试')
    except requests.exceptions.ConnectionError:
        print('\n✗ 连接错误')
        print('提示: 请确认后端服务是否在 http://localhost:8000 运行')
    except Exception as e:
        print(f'\n✗ 发生错误: {type(e).__name__}')
        print(f'错误详情: {str(e)}')

if __name__ == '__main__':
    test_deepseek_api()
