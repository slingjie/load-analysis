$env:DEEPSEEK_API_KEY = 'sk-3008dc675fad4414abee5ea2b75ed54f'
Set-Location 'D:\Desktop\ai\1028负荷展示和tou配置'
uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
