#!/bin/bash

# LLMOps Docker 容器启动脚本
# 注意：所有敏感信息（API Keys、密钥等）必须通过 api/.env 或 docker-compose environment 提供
# 本脚本仅设置非敏感的默认配置

# 1.启用错误检查
set -e

# 2.设置非敏感的默认配置
set_default_if_unset() {
  local key="$1"
  local default_value="$2"
  if [[ -z "${!key+x}" ]]; then
    export "${key}=${default_value}"
  fi
}

# Flask 基础配置
set_default_if_unset "FLASK_ENV" "production"
set_default_if_unset "FLASK_DEBUG" "0"

# HuggingFace 镜像
set_default_if_unset "HF_ENDPOINT" "https://hf-mirror.com"

# 服务器配置
set_default_if_unset "SERVER_WORKER_AMOUNT" "4"
set_default_if_unset "SERVER_THREAD_AMOUNT" "4"
set_default_if_unset "CELERY_WORKER_AMOUNT" "4"

# 数据库连接池配置
set_default_if_unset "SQLALCHEMY_POOL_SIZE" "30"
set_default_if_unset "SQLALCHEMY_POOL_RECYCLE" "3600"
set_default_if_unset "SQLALCHEMY_ECHO" "false"

# Redis 配置
set_default_if_unset "REDIS_DB" "0"
set_default_if_unset "REDIS_USE_SSL" "false"

# Celery 配置
set_default_if_unset "CELERY_BROKER_DB" "1"
set_default_if_unset "CELERY_RESULT_BACKEND_DB" "1"
set_default_if_unset "CELERY_TASK_IGNORE_RESULT" "true"
set_default_if_unset "CELERY_RESULT_EXPIRES" "3600"
set_default_if_unset "CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP" "true"

# HuggingFace 离线模式
set_default_if_unset "TRANSFORMERS_OFFLINE" "0"

# 邮件服务默认配置（非敏感）
set_default_if_unset "MAIL_SERVER" "smtp.qq.com"
set_default_if_unset "MAIL_PORT" "587"
set_default_if_unset "MAIL_USE_TLS" "True"
set_default_if_unset "MAIL_USE_SSL" "False"

# 腾讯云 COS 配置（非敏感）
set_default_if_unset "COS_REGION" "ap-beijing"
set_default_if_unset "COS_SCHEME" "https"

# API 基础地址（非敏感）
set_default_if_unset "OPENAI_API_BASE" "https://api.openai.com/v1"
set_default_if_unset "DEEPSEEK_API_BASE" "https://api.deepseek.com/v1"
set_default_if_unset "SILICONFLOW_API_BASE" "https://api.siliconflow.cn"
set_default_if_unset "LANGCHAIN_ENDPOINT" "https://api.smith.langchain.com"

# 3.检查必需的环境变量（从 api/.env 或 docker-compose 提供）
check_required_env() {
  local missing_vars=()

  # 检查数据库配置
  [[ -z "${SQLALCHEMY_DATABASE_URI}" ]] && missing_vars+=("SQLALCHEMY_DATABASE_URI")

  # 检查 Redis 配置
  [[ -z "${REDIS_HOST}" ]] && missing_vars+=("REDIS_HOST")
  [[ -z "${REDIS_PORT}" ]] && missing_vars+=("REDIS_PORT")

  # 检查 JWT 密钥
  [[ -z "${JWT_SECRET_KEY}" ]] && missing_vars+=("JWT_SECRET_KEY")

  if [ ${#missing_vars[@]} -gt 0 ]; then
    echo "❌ 错误: 缺少必需的环境变量:"
    printf '  - %s\n' "${missing_vars[@]}"
    echo ""
    echo "请确保:"
    echo "  1. api/.env 文件存在并包含所有必需配置"
    echo "  2. docker-compose.yaml 中配置了 env_file: - ../api/.env"
    echo "  3. 或通过 docker-compose environment 提供这些变量"
    exit 1
  fi
}

# 4.检查必需的环境变量
check_required_env

# 5.判断是否启用的迁移数据同步 如果是则将数据库迁移同步到数据库中
if [[ "${MIGRATION_ENABLED}" == "true" ]]; then
  echo "Checking database migrations..."
  if [ ! -d "internal/migration" ]; then
    echo "Initializing new migrations..."
    flask db init --directory internal/migration
  fi
  echo "Applying pending migrations..."
  flask db upgrade --directory internal/migration
fi

# 6.检测运行的模式(api/celery) 以执行不同的脚本
if [[ "${MODE}" == "celery" ]]; then
  # 7.运行Celery命令
  celery -A app.http.app.celery worker -P ${CELERY_WORKER_CLASS:-prefork} -c ${CELERY_WORKER_AMOUNT:-1} --loglevel DEBUG
else
  # 8.判断当前API环境是开发环境还是生产环境 以执行不同的脚本
  if [[ "${FLASK_ENV}" == "development" ]]; then
    # 9.开发环境使用flask内置服务器
    flask run --host=${LLMOPS_BIND_ADDRESS:-0.0.0.0} --port=${LLMOPS_PORT:-5001} --debug
    else
      # 10.生产环境使用gunicorn服务器进行部署 并配置worker worker_class 超时时间 预加载等
      gunicorn \
        --bind "${LLMOPS_BIND_ADDRESS:-0.0.0.0}:${LLMOPS_PORT:-5001}" \
        --workers ${SERVER_WORKER_AMOUNT:-1} \
        --worker-class ${SERVER_WORKER_CLASS:-gthread} \
        --threads ${SERVER_THREAD_AMOUNT:-2} \
        --timeout ${GUNICORN_TIMEOUT:-600} \
        --preload \
        app.http.app:app
    fi
fi
