#!/bin/bash

echo ""
echo "========================================"
echo "  Agent Chat Hub"
echo "  统一查看 AI Agent 聊天记录"
echo "========================================"
echo ""

# 检查 Python
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo "[错误] 未找到 Python"
    echo "请先安装 Python 3.8+"
    echo "  macOS: brew install python3"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip"
    exit 1
fi

PYVER=$($PYTHON --version 2>&1)
echo "[√] $PYVER 已安装"

# 检查并安装依赖
echo "[1/2] 检查依赖..."
if ! $PYTHON -c "import fastapi" 2>/dev/null; then
    echo "[2/2] 安装依赖（首次运行需要）..."
    $PYTHON -m pip install -r "$(dirname "$0")/requirements.txt" --quiet --disable-pip-version-check
    if [ $? -ne 0 ]; then
        echo "[错误] 依赖安装失败，请检查网络连接"
        exit 1
    fi
    echo "[√] 依赖安装完成"
else
    echo "[√] 依赖已安装"
fi

# 启动服务
echo ""
echo "========================================"
echo "  正在启动..."
echo "  浏览器将自动打开"
echo "  按 Ctrl+C 停止服务"
echo "========================================"
echo ""

cd "$(dirname "$0")"
$PYTHON -m app.main
