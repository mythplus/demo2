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

REM 激活虚拟环境并启动服务
echo [信息] 正在启动 Mem0 API 服务 (端口: 8080)...
echo [信息] 按 Ctrl+C 可优雅退出服务
echo.

d:\Users\V_grhe\Desktop\ai-demo\demo2\.venv\Scripts\python.exe d:\Users\V_grhe\Desktop\ai-demo\demo2\server.py
