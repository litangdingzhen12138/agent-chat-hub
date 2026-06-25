@echo off
chcp 65001 >nul 2>&1
title Agent Chat Visualizer

echo.
echo ========================================
echo   Agent Chat Hub
echo   统一查看 AI Agent 聊天记录
echo ========================================
echo.

:: 检查 Python
where python >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python
    echo 请先安装 Python 3.8+: https://www.python.org/downloads/
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: 获取 Python 版本
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo [√] Python %PYVER% 已安装

:: 检查并安装依赖
echo [1/2] 检查依赖...
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo [2/2] 安装依赖（首次运行需要）...
    python -m pip install -r "%~dp0requirements.txt" --quiet --disable-pip-version-check
    if errorlevel 1 (
        echo [错误] 依赖安装失败，请检查网络连接
        pause
        exit /b 1
    )
    echo [√] 依赖安装完成
) else (
    echo [√] 依赖已安装
)

:: 启动服务
echo.
echo ========================================
echo   正在启动...
echo   浏览器将自动打开
echo   按 Ctrl+C 停止服务
echo ========================================
echo.

cd /d "%~dp0"
python -m app.main

pause
