#!/bin/bash

# Nginx 容器启动脚本
# 用途: 根据环境变量动态生成 Nginx 配置

set -e

echo "=========================================="
echo "  Nginx 配置生成"
echo "=========================================="

# 设置默认值（使用 NGINX_* 前缀，避免与应用侧变量冲突）
export NGINX_DOMAIN_NAME=${NGINX_DOMAIN_NAME:-${DOMAIN_NAME:-localhost}}
export NGINX_SSL_CERT_FILE=${NGINX_SSL_CERT_FILE:-server.crt}
export NGINX_SSL_KEY_FILE=${NGINX_SSL_KEY_FILE:-server.key}
export NGINX_ENABLE_HTTPS=${NGINX_ENABLE_HTTPS:-${ENABLE_HTTPS:-false}}
ENABLE_HTTPS_NORMALIZED="$(echo "$NGINX_ENABLE_HTTPS" | tr '[:upper:]' '[:lower:]')"
export API_UPSTREAM_HOST=${API_UPSTREAM_HOST:-llmops-api}
export API_UPSTREAM_PORT=${API_UPSTREAM_PORT:-5001}
export UI_UPSTREAM_HOST=${UI_UPSTREAM_HOST:-llmops-ui}
export UI_UPSTREAM_PORT=${UI_UPSTREAM_PORT:-3000}

echo "域名: $NGINX_DOMAIN_NAME"
echo "SSL 证书: $NGINX_SSL_CERT_FILE"
echo "SSL 私钥: $NGINX_SSL_KEY_FILE"
echo "启用 HTTPS: $NGINX_ENABLE_HTTPS"
echo "API 上游: ${API_UPSTREAM_HOST}:${API_UPSTREAM_PORT}"
echo "UI 上游: ${UI_UPSTREAM_HOST}:${UI_UPSTREAM_PORT}"
echo ""

# 检查 SSL 证书文件是否存在
if [ "$ENABLE_HTTPS_NORMALIZED" = "true" ]; then
    if [ ! -f "/etc/ssl/$NGINX_SSL_CERT_FILE" ]; then
        echo "❌ 错误: SSL 证书文件不存在: /etc/ssl/$NGINX_SSL_CERT_FILE"
        echo "请将 SSL 证书上传到服务器的 docker/nginx/ssl/ 目录"
        exit 1
    fi

    if [ ! -f "/etc/ssl/$NGINX_SSL_KEY_FILE" ]; then
        echo "❌ 错误: SSL 私钥文件不存在: /etc/ssl/$NGINX_SSL_KEY_FILE"
        echo "请将 SSL 私钥上传到服务器的 docker/nginx/ssl/ 目录"
        exit 1
    fi

    echo "✓ SSL 证书文件检查通过"
fi

# 生成 Nginx 配置
echo "正在生成 Nginx 配置..."
if [ "$ENABLE_HTTPS_NORMALIZED" = "true" ]; then
    cat > /etc/nginx/conf.d/default.conf <<EOF
server {
    listen 80;
    server_name ${NGINX_DOMAIN_NAME};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl;
    server_name ${NGINX_DOMAIN_NAME};

    ssl_certificate /etc/ssl/${NGINX_SSL_CERT_FILE};
    ssl_certificate_key /etc/ssl/${NGINX_SSL_KEY_FILE};

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;

    location /api/ {
        proxy_pass http://${API_UPSTREAM_HOST}:${API_UPSTREAM_PORT}/;
        include /etc/nginx/proxy.conf;
    }

    location / {
        proxy_pass http://${UI_UPSTREAM_HOST}:${UI_UPSTREAM_PORT};
        include /etc/nginx/proxy.conf;
    }
}
EOF
else
    cat > /etc/nginx/conf.d/default.conf <<EOF
server {
    listen 80;
    server_name ${NGINX_DOMAIN_NAME};

    location /api/ {
        proxy_pass http://${API_UPSTREAM_HOST}:${API_UPSTREAM_PORT}/;
        include /etc/nginx/proxy.conf;
    }

    location / {
        proxy_pass http://${UI_UPSTREAM_HOST}:${UI_UPSTREAM_PORT};
        include /etc/nginx/proxy.conf;
    }
}
EOF
fi

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
