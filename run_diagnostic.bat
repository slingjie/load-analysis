@echo off
chcp 65001 >nul
cls
echo ╔════════════════════════════════════════════════════════════════════════════════╗
echo ║                     项目评估报告系统 - 一键诊断工具                          ║
echo ╚════════════════════════════════════════════════════════════════════════════════╝
echo.
echo 正在检查后端服务状态...
echo.

REM 检查后端是否运行
curl -s http://localhost:8000/docs >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 后端服务未运行
    echo.
    echo 请先在另一个终端运行以下命令启动后端：
    echo   .\start_backend_with_env.ps1
    echo.
    echo 或按任意键自动启动后端服务...
    pause >nul
    
    echo.
    echo 正在启动后端服务...
    start "后端服务" powershell -NoExit -Command "$env:DEEPSEEK_API_KEY='sk-3008dc675fad4414abee5ea2b75ed54f'; uvicorn backend.app:app --reload"
    
    echo 等待后端服务启动（15秒）...
    timeout /t 15 /nobreak >nul
    echo.
)

echo 后端服务运行中，开始诊断...
echo.
echo ────────────────────────────────────────────────────────────────────────────────
echo.

REM 运行诊断脚本
python quick_diagnostic.py

echo.
echo ────────────────────────────────────────────────────────────────────────────────
echo.
echo 诊断完成！
echo.
echo 如需查看详细调试指南，请打开：
echo   DEBUG_GUIDE.md
echo.
echo 如需了解解决方案，请打开：
echo   DIAGNOSTIC_SOLUTION.md
echo.
pause
