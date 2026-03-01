#!/bin/bash

# =================================================================
# CryptoRadar 启动脚本
# 功能: 彻底停止现有的前后端程序并重新启动
# =================================================================

# 颜色定义
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}===> 正在准备启动 CryptoRadar...${NC}"

# 1. & 2. 停止前后端程序
echo -e "${YELLOW}步骤 1 & 2: 停止现有的前后端进程...${NC}"
# 查找并杀掉 Python 引擎进程以及 Vite/npm 进程
ps aux | grep -E "main.py|npm|vite" | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null

echo -e "${GREEN}旧进程已清理 (如有)。${NC}"

# 3. 启动后端程序
echo -e "${YELLOW}步骤 3: 在后台启动后端 Python 引擎...${NC}"
if [ -d "venv" ]; then
    nohup venv/bin/python main.py > backend.log 2>&1 &
else
    nohup python3 main.py > backend.log 2>&1 &
fi
echo -e "${GREEN}后端已启动，日志输出至 backend.log ${NC}"

# 4. 启动前端程序
echo -e "${YELLOW}步骤 4: 在后台启动前端 Vite 界面...${NC}"
cd web_ui
# 安装依赖以防万一 (可选，如果已经安装可以注释掉)
# npm install
nohup npm run dev -- --port 5173 > ../frontend.log 2>&1 &
echo -e "${GREEN}前端已启动，端口 5173，日志输出至 frontend.log ${NC}"

echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}🚀 系统启动成功！${NC}"
echo -e "${BLUE}前端地址: http://localhost:5173${NC}"
echo -e "${BLUE}后端 API: http://localhost:8000${NC}"
echo -e "${BLUE}=================================================${NC}"
