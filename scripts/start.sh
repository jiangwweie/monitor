#!/bin/bash

# =================================================================
# CryptoRadar 启动脚本
# 功能：停止现有进程并重新启动前后端服务
# =================================================================

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 日志和 PID 文件路径
LOGS_DIR="$PROJECT_ROOT/logs"
BACKEND_LOG="$LOGS_DIR/backend.log"
FRONTEND_LOG="$LOGS_DIR/frontend.log"
BACKEND_PID="$LOGS_DIR/backend.pid"
FRONTEND_PID="$LOGS_DIR/frontend.pid"

echo -e "${BLUE}===> 正在准备启动 CryptoRadar...${NC}"

# 确保日志目录存在
mkdir -p "$LOGS_DIR"

# =================================================================
# 步骤 1: 停止现有的前后端进程
# =================================================================
echo -e "${YELLOW}步骤 1: 停止现有的前后端进程...${NC}"

# 通过 PID 文件停止进程（更精确）
if [ -f "$BACKEND_PID" ]; then
    OLD_PID=$(cat "$BACKEND_PID")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        kill -9 "$OLD_PID" 2>/dev/null
        echo -e "${GREEN}  已停止后端进程 (PID: $OLD_PID)${NC}"
    fi
    rm -f "$BACKEND_PID"
fi

if [ -f "$FRONTEND_PID" ]; then
    OLD_PID=$(cat "$FRONTEND_PID")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        kill -9 "$OLD_PID" 2>/dev/null
        echo -e "${GREEN}  已停止前端进程 (PID: $OLD_PID)${NC}"
    fi
    rm -f "$FRONTEND_PID"
fi

# 备用方案：通过进程名查找并清理
ps aux | grep -E "main.py|npm|vite" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

echo -e "${GREEN}旧进程已清理。${NC}"

# =================================================================
# 步骤 2: 启动后端程序
# =================================================================
echo -e "${YELLOW}步骤 2: 在后台启动后端 Python 引擎...${NC}"

cd "$PROJECT_ROOT"

# 从 .env 文件读取后端端口（如果存在）
BACKEND_PORT_OPT=8000
if [ -f "$PROJECT_ROOT/.env" ]; then
    CUSTOM_PORT=$(grep "^BACKEND_PORT=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
    if [ -n "$CUSTOM_PORT" ]; then
        BACKEND_PORT_OPT=$CUSTOM_PORT
    fi
fi

# 导出环境变量供 main.py 使用
export BACKEND_PORT=$BACKEND_PORT_OPT

if [ -d "venv" ]; then
    nohup venv/bin/python main.py > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
else
    nohup python3 main.py > "$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!
fi

# 保存 PID
echo "$BACKEND_PID" > "$BACKEND_PID"
echo -e "${GREEN}  后端已启动 (PID: $BACKEND_PID), 日志：$BACKEND_LOG${NC}"

# 等待后端启动
sleep 2

# =================================================================
# 步骤 3: 启动前端程序
# =================================================================
echo -e "${YELLOW}步骤 3: 在后台启动前端 Vite 界面...${NC}"

cd "$PROJECT_ROOT/web_ui"

# 检查 node_modules 是否存在
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}  首次运行，安装前端依赖...${NC}"
    npm install
fi

# 从 .env 文件读取前端端口（如果存在）
FRONTEND_PORT=5173
if [ -f "$PROJECT_ROOT/.env" ]; then
    CUSTOM_PORT=$(grep "^FRONTEND_PORT=" "$PROJECT_ROOT/.env" | cut -d'=' -f2)
    if [ -n "$CUSTOM_PORT" ]; then
        FRONTEND_PORT=$CUSTOM_PORT
    fi
fi

nohup npm run dev -- --port $FRONTEND_PORT > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

# 保存 PID
echo "$FRONTEND_PID" > "$FRONTEND_PID"
echo -e "${GREEN}  前端已启动 (PID: $FRONTEND_PID), 日志：$FRONTEND_LOG${NC}"

# =================================================================
# 完成
# =================================================================
sleep 1
echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}🚀 系统启动成功！${NC}"
echo -e "${BLUE}  前端地址：http://localhost:${FRONTEND_PORT}${NC}"
echo -e "${BLUE}  后端 API: http://localhost:${BACKEND_PORT:-8000}${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "${YELLOW}提示：请确保项目根目录的 .env 文件已配置币安 API 密钥${NC}"
echo -e "${YELLOW}      首次运行请执行：cp .env.example .env${NC}"
