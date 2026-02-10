"""
PyInstaller 打包脚本 — 将后端打包为 backend-server.exe

用法:
    python scripts/build_backend.py

产出:
    src-tauri/binaries/backend-server-x86_64-pc-windows-msvc.exe

说明:
    Tauri 的 externalBin 机制要求 sidecar 文件名包含平台三元组后缀，
    Windows x64 环境下为 -x86_64-pc-windows-msvc.exe。
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"
ENTRY = BACKEND_DIR / "run_server.py"
TAURI_BIN_DIR = ROOT / "src-tauri" / "binaries"

# PyInstaller 输出目录（临时）
DIST_DIR = ROOT / "dist_pyinstaller"

# 目标文件名（Tauri sidecar 需包含平台三元组）
TARGET_NAME = "backend-server-x86_64-pc-windows-msvc"


def main():
    print(f"[build_backend] Project Root: {ROOT}")
    print(f"[build_backend] Entry Script: {ENTRY}")

    if not ENTRY.exists():
        print(f"[ERROR] Entry script not found: {ENTRY}")
        sys.exit(1)

    # 确保输出目录存在
    TAURI_BIN_DIR.mkdir(parents=True, exist_ok=True)

    # PyInstaller 打包命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", TARGET_NAME,
        "--distpath", str(TAURI_BIN_DIR),
        "--workpath", str(DIST_DIR / "build"),
        "--specpath", str(DIST_DIR),
        "--clean",
        # 隐式导入后端模块
        "--hidden-import", "backend",
        "--hidden-import", "backend.app",
        "--hidden-import", "backend.services",
        "--hidden-import", "backend.services.loader",
        "--hidden-import", "backend.services.quality",
        "--hidden-import", "backend.services.cycles",
        "--hidden-import", "backend.services.cleaning",
        "--hidden-import", "backend.services.economics",
        "--hidden-import", "backend.services.local_sync",
        "--hidden-import", "backend.services.app_paths",
        "--hidden-import", "backend.services.deepseek_summary",
        "--hidden-import", "backend.schemas",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespan",
        "--hidden-import", "uvicorn.lifespan.on",
        # 排除桌面版不需要的大型包
        "--exclude-module", "playwright",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        str(ENTRY),
    ]

    print(f"[build_backend] Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode != 0:
        print(f"[ERROR] PyInstaller build failed (exit code {result.returncode})")
        sys.exit(1)

    # 验证产物
    exe_path = TAURI_BIN_DIR / f"{TARGET_NAME}.exe"
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"[build_backend] ✅ Build success: {exe_path} ({size_mb:.1f} MB)")
    else:
        print(f"[ERROR] Output binary not found: {exe_path}")
        sys.exit(1)

    # 清理临时目录
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR, ignore_errors=True)
        print("[build_backend] Cleaned up temporary directory")


if __name__ == "__main__":
    main()
