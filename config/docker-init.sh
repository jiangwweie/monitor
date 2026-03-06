#!/bin/bash

# =================================================================
# CryptoRadar Docker 初始化脚本
# 功能：创建必要的目录和配置文件
# =================================================================

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Docker 数据目录
DOCKER_BASE="/Users/jiangwei/Documents/docker/monitor"

echo -e "${BLUE}===> CryptoRadar Docker 初始化${NC}"

# 创建目录
echo -e "${YELLOW}步骤 1: 创建必要的目录...${NC}"
mkdir -p "$DOCKER_BASE"/{data,logs,config}

if [ $? -eq 0 ]; then
    echo -e "${GREEN}  ✓ 目录创建完成${NC}"
else
    echo -e "${RED}  ✗ 目录创建失败${NC}"
    exit 1
fi

# 复制配置模板
echo -e "${YELLOW}步骤 2: 复制配置模板...${NC}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "$SCRIPT_DIR/.env.example" ]; then
    cp "$SCRIPT_DIR/.env.example" "$DOCKER_BASE/.env"
    echo -e "${GREEN}  ✓ 配置模板已复制：$DOCKER_BASE/.env${NC}"
else
    echo -e "${RED}  ✗ 配置模板不存在：$SCRIPT_DIR/.env.example${NC}"
    exit 1
fi

# 提示
echo -e "${BLUE}"
echo -e "================================================="
echo -e "${GREEN}✓ 初始化完成！${NC}"
echo -e "${BLUE}=================================================${NC}"
echo ""
echo -e "${YELLOW}下一步操作：${NC}"
echo ""
echo -e "1. 编辑配置文件："
echo -e "   ${BLUE}vi $DOCKER_BASE/.env${NC}"
echo ""
echo -e "2. 填入币安 API 密钥（必填）："
echo -e "   ${BLUE}BINANCE_API_KEY=你的 API Key${NC}"
echo -e "   ${BLUE}BINANCE_API_SECRET=你的 API Secret${NC}"
echo ""
echo -e "3. （可选）修改端口："
echo -e "   ${BLUE}BACKEND_PORT=8000${NC}"
echo -e "   ${BLUE}FRONTEND_PORT=5174${NC}"
echo ""
echo -e "4. 启动 Docker："
echo -e "   ${BLUE}cd $SCRIPT_DIR${NC}"
echo -e "   ${BLUE}docker-compose up --build -d${NC}"
echo ""
