#!/bin/bash

# =================================================================
# CryptoRadar 停止脚本
# 功能：彻底停止现有的前后端程序
# =================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# PID 文件路径
PID_DIR="$PROJECT_ROOT/logs"
BACKEND_PID="$PID_DIR/backend.pid"
FRONTEND_PID="$PID_DIR/frontend.pid"

echo -e "${RED}===> 正在停止 CryptoRadar 系统...${NC}"

# 停止后端进程
if [ -f "$BACKEND_PID" ]; then
    OLD_PID=$(cat "$BACKEND_PID")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        kill -9 "$OLD_PID" 2>/dev/null
        echo -e "${RED}  已停止后端进程 (PID: $OLD_PID)${NC}"
    else
        echo -e "${RED}  后端进程未运行${NC}"
    fi
    rm -f "$BACKEND_PID"
else
    # 备用方案：通过进程名查找
    ps aux | grep "main.py" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    echo -e "${RED}  已尝试停止后端进程${NC}"
fi

# 停止前端进程
if [ -f "$FRONTEND_PID" ]; then
    OLD_PID=$(cat "$FRONTEND_PID")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        kill -9 "$OLD_PID" 2>/dev/null
        echo -e "${RED}  已停止前端进程 (PID: $OLD_PID)${NC}"
    else
        echo -e "${RED}  前端进程未运行${NC}"
    fi
    rm -f "$FRONTEND_PID"
else
    # 备用方案：通过进程名查找
    ps aux | grep -E "npm|vite" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    echo -e "${RED}  已尝试停止前端进程${NC}"
fi

echo -e "${RED}所有相关进程已清理。${NC}"
echo -e "${GREEN}✓ 停止完成${NC}"
