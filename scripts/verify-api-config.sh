#!/bin/bash

# API 配置验证脚本
# 用于验证 Nginx 代理和 API 配置是否正确

set -e

echo "=========================================="
echo "  LLMOps API 配置验证工具"
echo "=========================================="
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. 检查环境变量配置
echo "1. 检查环境变量配置..."
if [ -f "ui/.env.development" ]; then
    DEV_PREFIX=$(grep "VITE_API_PREFIX" ui/.env.development | cut -d'=' -f2)
    if [ -z "$DEV_PREFIX" ]; then
        check_pass "开发环境配置: 自动模式 (推荐)"
    else
        check_warn "开发环境配置: 手动模式 ($DEV_PREFIX)"
    fi
else
    check_fail "未找到 ui/.env.development 文件"
fi

if [ -f "ui/.env.production" ]; then
    PROD_PREFIX=$(grep "VITE_API_PREFIX" ui/.env.production | cut -d'=' -f2)
    if [ -z "$PROD_PREFIX" ]; then
        check_pass "生产环境配置: 自动模式 (推荐)"
    else
        check_warn "生产环境配置: 手动模式 ($PROD_PREFIX)"
    fi
else
    check_fail "未找到 ui/.env.production 文件"
fi
echo ""

# 2. 检查 Nginx 配置文件
echo "2. 检查 Nginx 配置文件..."
if [ -f "docker/nginx/nginx.conf" ]; then
    check_pass "找到 nginx.conf"
else
    check_fail "未找到 docker/nginx/nginx.conf"
fi

if [ -f "docker/nginx/conf.d/default.conf" ]; then
    check_pass "找到 default.conf"

    # 检查 /api/ 代理配置
    if grep -q "location /api/" docker/nginx/conf.d/default.conf; then
        check_pass "配置了 /api/ 代理"
    else
        check_fail "未配置 /api/ 代理"
    fi

    # 检查后端代理地址
    if grep -q "proxy_pass.*llmops-api:5001" docker/nginx/conf.d/default.conf; then
        check_pass "后端代理地址正确"
    else
        check_warn "后端代理地址可能不正确"
    fi
else
    check_fail "未找到 docker/nginx/conf.d/default.conf"
fi

if [ -f "docker/nginx/proxy.conf" ]; then
    check_pass "找到 proxy.conf"
else
    check_fail "未找到 docker/nginx/proxy.conf"
fi
echo ""

# 3. 检查 Docker Compose 配置
echo "3. 检查 Docker Compose 配置..."
if [ -f "docker/docker-compose.yml" ]; then
    check_pass "找到 docker-compose.yml"

    # 检查服务定义
    if grep -q "llmops-api:" docker/docker-compose.yml; then
        check_pass "定义了 llmops-api 服务"
    else
        check_fail "未定义 llmops-api 服务"
    fi

    if grep -q "llmops-ui:" docker/docker-compose.yml; then
        check_pass "定义了 llmops-ui 服务"
    else
        check_fail "未定义 llmops-ui 服务"
    fi

    if grep -q "nginx:" docker/docker-compose.yml; then
        check_pass "定义了 nginx 服务"
    else
        check_fail "未定义 nginx 服务"
    fi
else
    check_fail "未找到 docker/docker-compose.yml"
fi
echo ""

# 4. 检查前端配置代码
echo "4. 检查前端配置代码..."
if [ -f "ui/src/config/index.ts" ]; then
    check_pass "找到 config/index.ts"

    # 检查是否包含智能获取逻辑
    if grep -q "getApiPrefix" ui/src/config/index.ts; then
        check_pass "包含智能 API 前缀获取逻辑"
    else
        check_fail "未包含智能 API 前缀获取逻辑"
    fi

    if grep -q "location?.origin" ui/src/config/index.ts; then
        check_pass "支持动态域名获取"
    else
        check_fail "不支持动态域名获取"
    fi
else
    check_fail "未找到 ui/src/config/index.ts"
fi
echo ""

# 5. 运行时检查 (如果服务正在运行)
echo "5. 运行时检查..."
if command -v docker-compose &> /dev/null; then
    if docker-compose -f docker/docker-compose.yml ps | grep -q "Up"; then
        check_pass "Docker Compose 服务正在运行"

        # 检查 Nginx 容器
        if docker-compose -f docker/docker-compose.yml ps nginx | grep -q "Up"; then
            check_pass "Nginx 容器运行中"

            # 测试 Nginx 配置
            if docker-compose -f docker/docker-compose.yml exec -T nginx nginx -t &> /dev/null; then
                check_pass "Nginx 配置语法正确"
            else
                check_fail "Nginx 配置语法错误"
            fi
        else
            check_warn "Nginx 容器未运行"
        fi

        # 检查后端容器
        if docker-compose -f docker/docker-compose.yml ps llmops-api | grep -q "Up"; then
            check_pass "后端容器运行中"
        else
            check_warn "后端容器未运行"
        fi

        # 检查前端容器
        if docker-compose -f docker/docker-compose.yml ps llmops-ui | grep -q "Up"; then
            check_pass "前端容器运行中"
        else
            check_warn "前端容器未运行"
        fi
    else
        check_warn "Docker Compose 服务未运行"
    fi
else
    check_warn "未安装 docker-compose,跳过运行时检查"
fi
echo ""

# 6. 网络连通性测试
echo "6. 网络连通性测试..."
if command -v curl &> /dev/null; then
    # 测试本地后端
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/health 2>/dev/null | grep -q "200"; then
        check_pass "本地后端可访问 (localhost:5001/health)"
    else
        check_warn "本地后端不可访问 (这是正常的,如果使用 Docker)"
    fi

    # 测试 Nginx 代理
    if curl -s -o /dev/null -w "%{http_code}" http://localhost/api/health 2>/dev/null | grep -q "200"; then
        check_pass "Nginx 代理可访问 (localhost/api/health)"
    else
        check_warn "Nginx 代理不可访问 (请确保服务已启动)"
    fi
else
    check_warn "未安装 curl,跳过网络测试"
fi
echo ""

# 总结
echo "=========================================="
echo "  验证完成"
echo "=========================================="
echo ""
echo "如果所有检查都通过,说明配置正确!"
echo "如果有警告或错误,请参考 API_CONFIG_GUIDE.md 进行修复"
echo ""
echo "快速启动命令:"
echo "  cd docker && docker-compose up -d"
echo ""
echo "查看日志:"
echo "  docker-compose -f docker/docker-compose.yml logs -f nginx"
echo ""
