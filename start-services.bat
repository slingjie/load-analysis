@echo off
REM 快速启动脚本 - Windows Batch 版本
REM 用法: 在项目根目录运行此脚本

setlocal enabledelayedexpansion

echo.
REM 强制使用 UTF-8 控制台编码以避免中文乱码（对新打开的 cmd 窗口也会生效）
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
set LANG=zh_CN.UTF-8

echo ==========================================
echo   项目服务 - 前后端一键启动
echo ==========================================
echo.

REM 检查虚拟环境
if not exist ".venv\Scripts\activate.bat" (
    echo 错误: 虚拟环境不存在
    echo 请先运行: python -m venv .venv
    pause
    exit /b 1
)

REM 检查 .env.local
if not exist ".env.local" (
    echo 创建 .env.local...
    (
        echo GEMINI_API_KEY=PLACEHOLDER_API_KEY
        echo VITE_BACKEND_BASE_URL=http://localhost:8000
    ) > .env.local
    echo 已创建 .env.local
)

REM 激活虚拟环境
call .venv\Scripts\activate.bat
set "PY_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PY_EXE%" (
    echo 错误: 未找到虚拟环境 Python: %PY_EXE%
    pause
    exit /b 1
)

echo.
echo 启动后端服务...
echo 后端 URL: http://localhost:8000
echo.

REM 检查端口并尝试释放（避免端口被占用导致 uvicorn 绑定失败）
set "PORT=8000"
set "PID="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%"') do (
    set "PID=%%a"
)
if defined PID (
    echo 端口 %PORT% 已被进程 !PID! 占用，尝试终止...
    taskkill /PID !PID! /F >nul 2>&1
    if !errorlevel! equ 0 (
        echo 成功终止进程 !PID!
    ) else (
        echo 无法终止进程 !PID!，可能需要以管理员身份运行或手动处理
    )
    timeout /t 1 /nobreak >nul
)

REM 若端口仍被占用，自动切换到下一个可用端口（最多尝试 20 个）
set "TRY=0"
:CHECK_PORT
set /a TRY+=1
set "PID="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    set "PID=%%a"
)
if defined PID (
    if %TRY% GEQ 20 (
        echo 错误: 无法找到可用端口（从 8000 起尝试了 20 个）
        pause
        exit /b 1
    )
    set /a PORT+=1
    goto CHECK_PORT
)

REM 启动后端（在新 cmd 窗口运行：切换到脚本目录、激活虚拟环境、设置 UTF-8）
start "backend-service" cmd /k "cd /d "%~dp0" && chcp 65001>nul && call .venv\Scripts\activate.bat && "%PY_EXE%" -X utf8 -m uvicorn backend.app:app --app-dir "%~dp0" --host 0.0.0.0 --port %PORT% --reload-dir "%~dp0" --reload"

REM 等待后端启动
echo 等待后端启动...
timeout /t 3 /nobreak

REM 尝试测试后端
curl -s http://localhost:%PORT%/health >nul 2>&1
if %errorlevel% equ 0 (
    echo 后端服务正常
) else (
    echo 警告: 后端可能未启动，请检查上面的窗口
)

REM 检查本地同步接口是否已加载（避免后端仍在运行旧版本导致 404）
curl -s http://localhost:%PORT%/openapi.json | findstr /C:"/api/local-sync/snapshot" >nul 2>&1
if %errorlevel% equ 0 (
    echo 本地同步接口已加载 (/api/local-sync/snapshot)
) else (
    echo 警告: 未检测到本地同步接口 (/api/local-sync/snapshot)；请确认后端已更新并彻底重启
)

echo.
echo 启动前端开发服务器...
echo 前端 URL: http://localhost:5173
echo.

REM 启动前端（在新 cmd 窗口运行：切换到脚本目录、设置 UTF-8）
start "frontend-dev" cmd /k "cd /d "%~dp0" && chcp 65001>nul && npm run dev"

REM 清理
echo.
echo 停止中...
REM 终止匹配新窗口标题的后端窗口
taskkill /FI "WINDOWTITLE eq backend-service*" /T /F >nul 2>&1

echo 已停止所有服务
pause
