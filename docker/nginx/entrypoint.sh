#!/bin/bash

# Nginx 容器启动脚本
# 用途: 根据环境变量动态生成 Nginx 配置

set -e

echo "=========================================="
echo "  Nginx 配置生成"
echo "=========================================="

# 设置默认值
DOMAIN_NAME=${DOMAIN_NAME:-localhost}
ENABLE_HTTPS=${ENABLE_HTTPS:-false}
SSL_CERT_FILE=${SSL_CERT_FILE:-server.crt}
SSL_KEY_FILE=${SSL_KEY_FILE:-server.key}

echo "域名: $DOMAIN_NAME"
echo "启用 HTTPS: $ENABLE_HTTPS"

# 生成 Nginx 配置
if [ "$ENABLE_HTTPS" = "true" ]; then
    echo "生成 HTTPS 配置..."

    # 检查 SSL 证书文件是否存在
    if [ ! -f "/etc/ssl/$SSL_CERT_FILE" ]; then
        echo "❌ 错误: SSL 证书文件不存在: /etc/ssl/$SSL_CERT_FILE"
        echo "请将 SSL 证书上传到服务器的 docker/ssl/ 目录"
        exit 1
    fi

    if [ ! -f "/etc/ssl/$SSL_KEY_FILE" ]; then
        echo "❌ 错误: SSL 私钥文件不存在: /etc/ssl/$SSL_KEY_FILE"
        echo "请将 SSL 私钥上传到服务器的 docker/ssl/ 目录"
        exit 1
    fi

    # 生成 HTTPS 配置
    cat > /etc/nginx/conf.d/default.conf << EOF
# HTTP 重定向到 HTTPS
server {
    listen 80;
    server_name $DOMAIN_NAME;
    return 301 https://\$host\$request_uri;
}

# HTTPS 配置
server {
    listen 443 ssl;
    server_name $DOMAIN_NAME;

    ssl_certificate /etc/ssl/$SSL_CERT_FILE;
    ssl_certificate_key /etc/ssl/$SSL_KEY_FILE;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';

    # API 代理
    location /api/ {
        proxy_pass http://llmops-api:5001/;
        include /etc/nginx/proxy.conf;
    }

    # 前端代理
    location / {
        proxy_pass http://llmops-ui:3000;
        include /etc/nginx/proxy.conf;
    }
}
EOF

else
    echo "生成 HTTP 配置（不启用 HTTPS）..."

    # 生成纯 HTTP 配置
    cat > /etc/nginx/conf.d/default.conf << EOF
# HTTP 配置（开发环境）
server {
    listen 80;
    server_name $DOMAIN_NAME;

    # API 代理
    location /api/ {
        proxy_pass http://llmops-api:5001/;
        include /etc/nginx/proxy.conf;
    }

    # 前端代理
    location / {
        proxy_pass http://llmops-ui:3000;
        include /etc/nginx/proxy.conf;
    }
}
EOF

fi

echo "✓ Nginx 配置生成完成"
echo ""
cat /etc/nginx/conf.d/default.conf
echo ""
echo "=========================================="

# 测试 Nginx 配置
nginx -t

# 启动 Nginx
exec nginx -g "daemon off;"
