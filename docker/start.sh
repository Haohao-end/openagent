#!/bin/bash

# LLMOps Docker 快速启动脚本
# 用途: 检查配置并启动 Docker 服务

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "  LLMOps Docker 环境启动脚本"
echo "=========================================="
echo ""

# 1. 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: Docker 未安装"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "❌ 错误: Docker Compose 未安装或版本过低"
    echo "请安装 Docker Compose V2: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker 环境检查通过"
echo ""

# 2. 检查配置文件
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo "⚠️  警告: docker/.env 文件不存在"
    echo "正在从 .env.example 创建..."
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "✓ 已创建 docker/.env 文件"
    echo ""
fi

if [ ! -f "$PROJECT_ROOT/api/.env" ]; then
    echo "⚠️  警告: api/.env 文件不存在"
    echo "容器将使用 entrypoint.sh 中的默认配置"
    echo "建议: 复制 api/.env.example 并配置真实的 API Keys"
    echo ""
else
    echo "✓ 检测到 api/.env 配置文件"
    echo ""
fi

# 3. 检查 docker-compose.yaml 语法
echo "正在验证 docker-compose.yaml 配置..."
if docker compose -f "$SCRIPT_DIR/docker-compose.yaml" config --quiet; then
    echo "✓ docker-compose.yaml 配置正确"
    echo ""
else
    echo "❌ 错误: docker-compose.yaml 配置有误"
    exit 1
fi

# 4. 显示配置摘要
echo "=========================================="
echo "  配置摘要"
echo "=========================================="
source "$SCRIPT_DIR/.env"
echo "前端端口:        http://localhost:${UI_PORT:-3000}"
echo "API 端口:        http://localhost:${API_PORT:-5001}"
echo "Nginx HTTP:      http://localhost:${NGINX_HTTP_PORT:-80}"
echo "Nginx HTTPS:     https://localhost:${NGINX_HTTPS_PORT:-443}"
echo "PostgreSQL:      localhost:${POSTGRES_PORT:-5432}"
echo "Redis:           localhost:${REDIS_PORT:-6379}"
echo "Weaviate:        http://localhost:${WEAVIATE_HTTP_PORT:-8080}"
echo "镜像版本:        ${IMAGE_VERSION:-0.1.0}"
echo ""

# 5. 询问是否继续
read -p "是否启动服务? [Y/n] " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]] && [[ ! -z $REPLY ]]; then
    echo "已取消启动"
    exit 0
fi

# 6. 启动服务
echo ""
echo "=========================================="
echo "  启动 Docker 服务"
echo "=========================================="
cd "$SCRIPT_DIR"

# 构建镜像
echo "正在构建镜像..."
docker compose build

# 启动服务
echo ""
echo "正在启动服务..."
docker compose up -d

# 7. 等待服务就绪
echo ""
echo "等待服务启动..."
sleep 5

# 8. 显示服务状态
echo ""
echo "=========================================="
echo "  服务状态"
echo "=========================================="
docker compose ps

# 9. 显示日志提示
echo ""
echo "=========================================="
echo "  启动完成!"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  - 前端:  http://localhost:${UI_PORT:-3000}"
echo "  - API:   http://localhost:${API_PORT:-5001}"
echo "  - Nginx: http://localhost:${NGINX_HTTP_PORT:-80}"
echo ""
echo "常用命令:"
echo "  查看日志:   docker compose logs -f [服务名]"
echo "  停止服务:   docker compose stop"
echo "  重启服务:   docker compose restart"
echo "  删除服务:   docker compose down"
echo "  删除数据:   docker compose down -v"
echo ""
echo "服务名称:"
echo "  - llmops-ui       (前端)"
echo "  - llmops-api      (API 服务)"
echo "  - llmops-celery   (异步任务)"
echo "  - llmops-db       (PostgreSQL)"
echo "  - llmops-redis    (Redis)"
echo "  - llmops-weaviate (向量数据库)"
echo "  - llmops-nginx    (反向代理)"
echo ""
