#!/usr/bin/env pwsh
<#
.SYNOPSIS
    快速启动脚本 - 同时启动后端和前端

.DESCRIPTION
    这个脚本将同时启动后端 (FastAPI) 和前端 (Vite) 服务器

.EXAMPLE
    .\start-services.ps1

.NOTES
    确保在项目根目录运行此脚本
#>

param(
    [switch]$NoReload,     # 不使用 --reload 模式
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "  数据完整性分析系统 - 快速启动脚本" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

# 检查项目目录
if (-not (Test-Path "backend\app.py")) {
    Write-Host "❌ 错误: 请在项目根目录运行此脚本" -ForegroundColor Red
    exit 1
}

# 检查虚拟环境
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    Write-Host "❌ 错误: 虚拟环境不存在" -ForegroundColor Red
    Write-Host "请先运行: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# 检查 .env.local
if (-not (Test-Path ".env.local")) {
    Write-Host "⚠️  警告: .env.local 不存在，创建默认配置..." -ForegroundColor Yellow
    @"
GEMINI_API_KEY=PLACEHOLDER_API_KEY
VITE_BACKEND_BASE_URL=http://localhost:$BackendPort
"@ | Out-File -Encoding UTF8 .env.local
    Write-Host "✅ 已创建 .env.local" -ForegroundColor Green
}

Write-Host ""
Write-Host "启动配置:" -ForegroundColor Cyan
Write-Host "  后端端口: $BackendPort"
Write-Host "  前端端口: $FrontendPort"
Write-Host "  Reload 模式: $(if ($NoReload) { '禁用' } else { '启用' })"
Write-Host ""

# 激活虚拟环境
Write-Host "📦 激活虚拟环境..." -ForegroundColor Yellow
& ".\.venv\Scripts\Activate.ps1"

# 检查依赖
Write-Host "🔍 检查依赖..." -ForegroundColor Yellow
python -c "import fastapi, pandas, uvicorn; print('✅ 所有依赖就绪')" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 缺少依赖，安装中..." -ForegroundColor Red
    pip install -r backend/requirements.txt
}

Write-Host ""
Write-Host "🚀 启动后端服务..." -ForegroundColor Green
Write-Host "   URL: http://localhost:$BackendPort" -ForegroundColor Cyan
Write-Host ""

# 启动后端
$backendArgs = @(
    "-m", "uvicorn",
    "backend.app:app",
    "--host", "0.0.0.0",
    "--port", $BackendPort.ToString()
)

if (-not $NoReload) {
    $backendArgs += "--reload"
}

# 创建日志文件
$logFile = "backend.log"

# 使用 Start-Process 在后台启动后端,重定向输出
$backendProcess = Start-Process `
    -FilePath "python.exe" `
    -ArgumentList $backendArgs `
    -PassThru `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError "backend.error.log"

Write-Host "✅ 后端已启动 (PID: $($backendProcess.Id))"
Write-Host "   日志文件: $logFile"
Write-Host ""

# 等待后端启动
Write-Host "⏳ 等待后端服务启动..." -ForegroundColor Yellow
Start-Sleep -Seconds 3

# 检查后端是否正常
try {
    $response = Invoke-WebRequest -Uri "http://localhost:$BackendPort/health" -UseBasicParsing -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 200) {
        Write-Host "✅ 后端服务正常 (/health: OK)" -ForegroundColor Green
    } else {
        Write-Host "⚠️  后端未准备好,查看日志: tail -f $logFile" -ForegroundColor Yellow
    }
}
catch {
    Write-Host "⚠️  无法连接后端,查看日志: tail -f $logFile" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "🚀 启动前端开发服务器..." -ForegroundColor Green
Write-Host "   URL: http://localhost:$FrontendPort" -ForegroundColor Cyan
Write-Host "   提示: Ctrl+C 将同时停止前后端服务" -ForegroundColor Yellow
Write-Host ""

# 注册退出清理
$cleanup = {
    Write-Host ""
    Write-Host "🛑 清理资源..." -ForegroundColor Yellow
    Get-Process -Id $backendProcess.Id -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "✅ 已停止后端服务"
}
Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action $cleanup | Out-Null

try {
    # 启动前端（在当前窗口）
    npm run dev
}
finally {
    # 清理后端进程
    & $cleanup
}
