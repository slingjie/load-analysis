$env:DEEPSEEK_API_KEY = '<YOUR_DEEPSEEK_API_KEY>'
Set-Location 'D:\Desktop\ai\1028负荷展示和tou配置'
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
