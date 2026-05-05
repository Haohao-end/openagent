#!/bin/bash

# OpenAgent 服务器快速部署脚本
# 用途: 在服务器上一键部署 OpenAgent 平台

set -e

echo "=========================================="
echo "  OpenAgent 平台服务器部署脚本"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
REPO_URL="https://github.com/Haohao-end/openagent.git"
INSTALL_DIR="/opt/llmops"

# 1. 检查是否为 root 用户
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ 请使用 root 用户运行此脚本${NC}"
    echo "   sudo bash deploy-server.sh"
    exit 1
fi

echo -e "${GREEN}✓ Root 权限检查通过${NC}"
echo ""

# 2. 检查并安装 Docker
echo "检查 Docker 安装..."
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}⚠️  Docker 未安装，正在安装...${NC}"
    curl -fsSL https://get.docker.com | bash
    systemctl start docker
    systemctl enable docker
    echo -e "${GREEN}✓ Docker 安装完成${NC}"
else
    echo -e "${GREEN}✓ Docker 已安装: $(docker --version)${NC}"
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose 未安装或版本过低${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose 已安装: $(docker compose version)${NC}"
echo ""

# 3. 检查并安装 Git
echo "检查 Git 安装..."
if ! command -v git &> /dev/null; then
    echo -e "${YELLOW}⚠️  Git 未安装，正在安装...${NC}"
    apt update && apt install -y git
    echo -e "${GREEN}✓ Git 安装完成${NC}"
else
    echo -e "${GREEN}✓ Git 已安装: $(git --version)${NC}"
fi
echo ""

# 4. 克隆或更新代码
echo "=========================================="
echo "  克隆/更新代码"
echo "=========================================="
if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${BLUE}检测到已存在的仓库，正在更新...${NC}"
    cd "$INSTALL_DIR"
    git fetch origin
    git reset --hard origin/main
    echo -e "${GREEN}✓ 代码更新完成${NC}"
else
    echo -e "${BLUE}正在克隆仓库...${NC}"
    rm -rf "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    echo -e "${GREEN}✓ 代码克隆完成${NC}"
fi
echo ""

# 5. 配置环境变量
echo "=========================================="
echo "  配置环境变量"
echo "=========================================="

# 检查 api/.env 是否存在
if [ ! -f "$INSTALL_DIR/api/.env" ]; then
    echo -e "${YELLOW}⚠️  api/.env 文件不存在${NC}"
    echo "正在从 .env.example 创建..."
    cp "$INSTALL_DIR/api/.env.example" "$INSTALL_DIR/api/.env"
    echo -e "${RED}❌ 重要: 请编辑 api/.env 文件，填入真实的 API Keys！${NC}"
    echo "   vim $INSTALL_DIR/api/.env"
    echo ""
    read -p "是否现在编辑 api/.env? [Y/n] " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]] || [[ -z $REPLY ]]; then
        vim "$INSTALL_DIR/api/.env"
    else
        echo -e "${YELLOW}⚠️  请稍后手动编辑: vim $INSTALL_DIR/api/.env${NC}"
        echo "   然后运行: cd $INSTALL_DIR/docker && docker compose up -d"
        exit 0
    fi
else
    echo -e "${GREEN}✓ api/.env 文件已存在${NC}"
fi

# 检查 docker/.env 是否存在
if [ ! -f "$INSTALL_DIR/docker/.env" ]; then
    echo -e "${YELLOW}⚠️  docker/.env 文件不存在${NC}"
    echo "正在从 .env.example 创建..."
    cp "$INSTALL_DIR/docker/.env.example" "$INSTALL_DIR/docker/.env"
    echo -e "${GREEN}✓ docker/.env 文件已创建（使用默认配置）${NC}"
fi
echo ""

# 6. 构建并启动服务
echo "=========================================="
echo "  构建并启动服务"
echo "=========================================="
cd "$INSTALL_DIR/docker"

echo "正在构建 Docker 镜像..."
docker compose build

echo ""
echo "正在启动服务..."
docker compose up -d

echo ""
echo "等待服务启动..."
sleep 10

# 7. 检查服务状态
echo ""
echo "=========================================="
echo "  服务状态"
echo "=========================================="
docker compose ps

# 8. 健康检查
echo ""
echo "=========================================="
echo "  健康检查"
echo "=========================================="

# 检查数据库
if docker compose exec llmops-db pg_isready -U postgres &> /dev/null; then
    echo -e "${GREEN}✓ PostgreSQL 运行正常${NC}"
else
    echo -e "${RED}❌ PostgreSQL 连接失败${NC}"
fi

# 检查 Redis
if docker compose exec llmops-redis redis-cli -a llmops123456 ping &> /dev/null; then
    echo -e "${GREEN}✓ Redis 运行正常${NC}"
else
    echo -e "${RED}❌ Redis 连接失败${NC}"
fi

# 检查 API
if curl -s http://localhost:5001/health &> /dev/null; then
    echo -e "${GREEN}✓ API 服务运行正常${NC}"
else
    echo -e "${YELLOW}⚠️  API 服务可能还在启动中...${NC}"
fi

# 9. 显示访问信息
echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo -e "${GREEN}访问地址:${NC}"
echo "  - 前端:  http://$(hostname -I | awk '{print $1}'):3000"
echo "  - API:   http://$(hostname -I | awk '{print $1}'):5001"
echo "  - Nginx: http://$(hostname -I | awk '{print $1}')"
echo ""
echo -e "${BLUE}常用命令:${NC}"
echo "  查看日志:   cd $INSTALL_DIR/docker && docker compose logs -f"
echo "  重启服务:   cd $INSTALL_DIR/docker && docker compose restart"
echo "  停止服务:   cd $INSTALL_DIR/docker && docker compose stop"
echo "  更新部署:   bash $0"
echo ""
echo -e "${YELLOW}注意事项:${NC}"
echo "  1. 确保 api/.env 中配置了真实的 API Keys"
echo "  2. 建议修改 docker/.env 中的数据库密码"
echo "  3. 生产环境请配置 HTTPS 和防火墙"
echo "  4. 定期备份数据: $INSTALL_DIR/docker/volumes/"
echo ""
echo -e "${GREEN}详细文档: $INSTALL_DIR/DEPLOYMENT.md${NC}"
echo ""
