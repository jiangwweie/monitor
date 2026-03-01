#!/bin/bash

# =================================================================
# CryptoRadar 停止脚本
# 功能: 彻底停止现有的前后端程序
# =================================================================

# 颜色定义
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${RED}===> 正在停止 CryptoRadar 系统...${NC}"

# 1. & 2. 停止前后端程序
# 查找并杀掉 Python 引擎进程以及 Vite/npm 进程
ps aux | grep -E "main.py|npm|vite" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

echo -e "${RED}所有相关进程已清理。${NC}"
