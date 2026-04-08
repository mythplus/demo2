@echo off
chcp 65001 >nul
echo ============================================
echo   Mem0 Dashboard 后端服务启动脚本
echo   Qdrant 模式: 本地文件模式 (on_disk)
echo ============================================
echo.

REM 检查 OPENAI_API_KEY 是否已设置
if "%OPENAI_API_KEY%"=="" (
    echo [警告] 未检测到 OPENAI_API_KEY 环境变量！
    echo 请先设置 OpenAI API Key:
    echo   set OPENAI_API_KEY=sk-your-key-here
    echo.
    echo 或者在当前终端中临时设置后重新运行此脚本。
    echo.
    pause
    exit /b 1
)

REM 定位脚本所在目录（支持任意位置运行）
cd /d "%~dp0"

REM 检查虚拟环境是否存在
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv，请先创建：python -m venv .venv
    pause
    exit /b 1
)

REM 激活虚拟环境并启动服务
echo [信息] 正在启动 Mem0 API 服务 (端口: 8080)...
echo [信息] 按 Ctrl+C 可优雅退出服务
echo.

.venv\Scripts\python.exe server.py
