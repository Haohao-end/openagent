#!/bin/bash

# Nginx 容器启动脚本
# 用途: 使用 envsubst 替换配置模板中的变量

set -e

echo "=========================================="
echo "  Nginx 配置生成"
echo "=========================================="

# 设置默认值
export DOMAIN_NAME=${DOMAIN_NAME:-localhost}
export SSL_CERT_FILE=${SSL_CERT_FILE:-server.crt}
export SSL_KEY_FILE=${SSL_KEY_FILE:-server.key}
export ENABLE_HTTPS=${ENABLE_HTTPS:-false}

echo "域名: $DOMAIN_NAME"
echo "SSL 证书: $SSL_CERT_FILE"
echo "SSL 私钥: $SSL_KEY_FILE"
echo "启用 HTTPS: $ENABLE_HTTPS"
echo ""

# 检查 SSL 证书文件是否存在
if [ "$ENABLE_HTTPS" = "true" ]; then
    if [ ! -f "/etc/ssl/$SSL_CERT_FILE" ]; then
        echo "❌ 错误: SSL 证书文件不存在: /etc/ssl/$SSL_CERT_FILE"
        echo "请将 SSL 证书上传到服务器的 docker/nginx/ssl/ 目录"
        exit 1
    fi

    if [ ! -f "/etc/ssl/$SSL_KEY_FILE" ]; then
        echo "❌ 错误: SSL 私钥文件不存在: /etc/ssl/$SSL_KEY_FILE"
        echo "请将 SSL 私钥上传到服务器的 docker/nginx/ssl/ 目录"
        exit 1
    fi

    echo "✓ SSL 证书文件检查通过"
fi

# 使用 envsubst 替换模板中的变量
echo "正在生成 Nginx 配置..."
envsubst '${DOMAIN_NAME} ${SSL_CERT_FILE} ${SSL_KEY_FILE}' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

echo "✓ Nginx 配置生成完成"
echo ""
echo "=========================================="
echo "  生成的配置:"
echo "=========================================="
cat /etc/nginx/conf.d/default.conf
echo ""
echo "=========================================="

# 测试 Nginx 配置
nginx -t

# 启动 Nginx
exec nginx -g "daemon off;"
