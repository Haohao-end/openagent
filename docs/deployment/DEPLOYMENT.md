# 🚀 LLMOps 平台部署指南

## 📋 目录
1. [本地提交代码到 GitHub](#1-本地提交代码到-github)
2. [服务器环境准备](#2-服务器环境准备)
3. [服务器部署步骤](#3-服务器部署步骤)
4. [常见问题排查](#4-常见问题排查)

---

## 1. 本地提交代码到 GitHub

### 步骤 1.1: 初始化 Git 仓库（如果还没有）

```bash
cd /home/haohao/llmops

# 检查是否已经是 Git 仓库
git status

# 如果不是，初始化 Git 仓库
git init

# 添加远程仓库
git remote add origin https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git

# 或者如果已经有 origin，更新它
git remote set-url origin https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git
```

### 步骤 1.2: 安全检查（重要！）

```bash
# 运行安全检查脚本
bash docker/security-check.sh

# 确保输出显示：
# ✓ api/.env 未被 Git 跟踪
# ✓ docker/.env 未被 Git 跟踪
# ✓ entrypoint.sh 中未发现敏感信息
# ✓ docker-compose.yaml 中未发现硬编码的 API Keys
```

### 步骤 1.3: 查看将要提交的文件

```bash
# 查看当前状态
git status

# 查看修改的内容
git diff

# 特别检查这些文件是否被忽略
git check-ignore api/.env docker/.env
# 应该输出:
# api/.env
# docker/.env
```

### 步骤 1.4: 添加文件到 Git

```bash
# 添加所有修改的文件
git add .

# 或者选择性添加
git add docker/
git add api/.env.example
git add api/docker/entrypoint.sh
git add .gitignore
git add CLAUDE.md
```

### 步骤 1.5: 提交代码

```bash
# 提交代码
git commit -m "feat: 重构 Docker 配置，实现安全的环境变量管理

- 移除 entrypoint.sh 中的硬编码敏感信息
- 使用 env_file 从 api/.env 读取配置
- 添加 docker/.env 用于基础设施配置
- 更新 .gitignore 防止敏感文件泄露
- 添加安全检查脚本和完整文档
- 简化 docker-compose.yaml (从 265 行减少到 154 行)
"
```

### 步骤 1.6: 推送到 GitHub

```bash
# 推送到 main 分支
git push -u origin main

# 如果是第一次推送，可能需要强制推送
git push -u origin main --force

# 如果需要输入 GitHub 凭证
# 用户名: Haohao-end
# 密码: 使用 Personal Access Token (不是密码)
```

### 步骤 1.7: 创建 GitHub Personal Access Token（如果需要）

1. 访问: https://github.com/settings/tokens
2. 点击 "Generate new token" → "Generate new token (classic)"
3. 勾选权限: `repo` (完整仓库访问)
4. 生成并复制 Token
5. 在 Git 推送时使用 Token 作为密码

---

## 2. 服务器环境准备

### 步骤 2.1: 连接到服务器

```bash
# 从 WSL2 连接到服务器
ssh root@82.157.66.198

# 或使用密钥
ssh -i ~/.ssh/your_key root@82.157.66.198
```

### 步骤 2.2: 安装必需软件

```bash
# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | bash

# 启动 Docker
systemctl start docker
systemctl enable docker

# 验证 Docker 安装
docker --version
docker compose version

# 安装 Git
apt install -y git

# 安装其他工具
apt install -y curl wget vim
```

### 步骤 2.3: 创建部署目录

```bash
# 创建应用目录
mkdir -p /opt/llmops
cd /opt/llmops
```

---

## 3. 服务器部署步骤

### 步骤 3.1: 克隆代码

```bash
cd /opt/llmops

# 克隆仓库
git clone https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git .

# 或者如果已经克隆过，拉取最新代码
git pull origin main
```

### 步骤 3.2: 配置环境变量

```bash
# 创建 api/.env 文件
cd /opt/llmops/api
cp .env.example .env

# 编辑 api/.env，填入真实的 API Keys
vim .env
```

**重要配置项（必须修改）：**

```bash
# api/.env

# Flask 配置
FLASK_DEBUG=0
FLASK_ENV=production

# JWT 密钥（生成随机密钥）
JWT_SECRET_KEY=your-random-secret-key-here

# 数据库配置（Docker 环境会自动覆盖）
SQLALCHEMY_DATABASE_URI=postgresql://postgres:llmops123456@127.0.0.1:5432/llmops?client_encoding=utf8

# Redis 配置（Docker 环境会自动覆盖）
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=llmops123456

# Weaviate 配置（Docker 环境会自动覆盖）
WEAVIATE_HTTP_HOST=localhost
WEAVIATE_HTTP_PORT=8080
WEAVIATE_API_KEY=ftBC9hKkjfdbdi0W3T6kEtMh5BZFpGa1DF8

# LLM API Keys（必须填入真实值）
OPENAI_API_KEY=sk-your-real-openai-key
DEEPSEEK_API_KEY=sk-your-real-deepseek-key
MOONSHOT_API_KEY=sk-your-real-moonshot-key
CLAUDE_API_KEY=sk-your-real-claude-key
DASHSCOPE_API_KEY=sk-your-real-dashscope-key

# OAuth 配置（如果需要）
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=https://your-domain.com/auth/authorize/github

# 其他服务配置
GAODE_API_KEY=your-gaode-key
SERPER_API_KEY=your-serper-key
# ... 其他配置
```

### 步骤 3.3: 配置 Docker 环境变量（可选）

```bash
cd /opt/llmops/docker
cp .env.example .env

# 编辑 docker/.env（可选，修改端口和密码）
vim .env
```

**建议修改的配置：**

```bash
# docker/.env

# 数据库密码（建议修改为强密码）
POSTGRES_PASSWORD=your-secure-db-password

# Redis 密码（建议修改为强密码）
REDIS_PASSWORD=your-secure-redis-password

# Weaviate API Key（建议修改）
WEAVIATE_API_KEY=your-weaviate-api-key

# 端口配置（如果需要修改）
API_PORT=5001
UI_PORT=3000
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
```

### 步骤 3.4: 构建并启动服务

```bash
cd /opt/llmops/docker

# 方式 1: 使用启动脚本（推荐）
bash start.sh

# 方式 2: 手动启动
docker compose build
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f llmops-api
docker compose logs -f llmops-celery
```

### 步骤 3.5: 验证部署

```bash
# 检查容器状态
docker compose ps

# 应该看到所有服务都是 Up 状态:
# llmops-api       Up
# llmops-celery    Up
# llmops-ui        Up
# llmops-db        Up (healthy)
# llmops-redis     Up (healthy)
# llmops-weaviate  Up
# llmops-nginx     Up

# 测试 API
curl http://localhost:5001/health

# 测试前端
curl http://localhost:3000

# 测试 Nginx
curl http://localhost
```

### 步骤 3.6: 配置防火墙（如果需要）

```bash
# 开放必要的端口
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw allow 22/tcp    # SSH

# 启用防火墙
ufw enable

# 查看状态
ufw status
```

---

## 4. 常见问题排查

### 问题 1: 容器无法启动

```bash
# 查看容器日志
docker compose logs llmops-api
docker compose logs llmops-celery

# 检查环境变量
docker compose exec llmops-api env | grep API_KEY

# 重新构建镜像
docker compose build --no-cache
docker compose up -d
```

### 问题 2: 数据库连接失败

```bash
# 检查数据库状态
docker compose ps llmops-db

# 查看数据库日志
docker compose logs llmops-db

# 测试数据库连接
docker compose exec llmops-db pg_isready -U postgres

# 进入数据库
docker compose exec llmops-db psql -U postgres -d llmops
```

### 问题 3: Redis 连接失败

```bash
# 检查 Redis 状态
docker compose ps llmops-redis

# 测试 Redis 连接
docker compose exec llmops-redis redis-cli -a llmops123456 ping

# 查看 Redis 日志
docker compose logs llmops-redis
```

### 问题 4: API Keys 无效

```bash
# 检查环境变量是否正确注入
docker compose exec llmops-api env | grep -E "OPENAI|DEEPSEEK|MOONSHOT"

# 如果没有，检查 api/.env 文件
cat /opt/llmops/api/.env | grep API_KEY

# 重启容器
docker compose restart llmops-api llmops-celery
```

### 问题 5: 端口被占用

```bash
# 查看端口占用
netstat -tulpn | grep -E "5001|3000|80|443"

# 修改 docker/.env 中的端口配置
vim docker/.env

# 重新创建容器
docker compose down
docker compose up -d
```

---

## 5. 更新部署

### 步骤 5.1: 拉取最新代码

```bash
cd /opt/llmops

# 拉取最新代码
git pull origin main
```

### 步骤 5.2: 重新构建并启动

```bash
cd /opt/llmops/docker

# 停止服务
docker compose down

# 重新构建镜像
docker compose build

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

### 步骤 5.3: 数据库迁移（如果有）

```bash
# API 容器会自动执行迁移（MIGRATION_ENABLED=true）
# 查看迁移日志
docker compose logs llmops-api | grep migration
```

---

## 6. 备份与恢复

### 备份数据

```bash
cd /opt/llmops/docker

# 备份数据库
docker compose exec llmops-db pg_dump -U postgres llmops > backup_$(date +%Y%m%d).sql

# 备份 volumes
tar -czf volumes_backup_$(date +%Y%m%d).tar.gz volumes/
```

### 恢复数据

```bash
# 恢复数据库
cat backup_20260304.sql | docker compose exec -T llmops-db psql -U postgres llmops

# 恢复 volumes
tar -xzf volumes_backup_20260304.tar.gz
```

---

## 7. 监控与日志

### 查看实时日志

```bash
# 所有服务
docker compose logs -f

# 特定服务
docker compose logs -f llmops-api
docker compose logs -f llmops-celery

# 最近 100 行
docker compose logs --tail=100 llmops-api
```

### 查看资源使用

```bash
# 查看容器资源使用
docker stats

# 查看磁盘使用
df -h
du -sh /opt/llmops/docker/volumes/*
```

---

## 8. 安全建议

1. ✅ **定期更新密钥**: 每 90 天更换一次 API Keys 和数据库密码
2. ✅ **使用 HTTPS**: 配置 SSL 证书（Let's Encrypt）
3. ✅ **限制访问**: 使用防火墙限制端口访问
4. ✅ **定期备份**: 每天自动备份数据库和 volumes
5. ✅ **监控日志**: 使用日志聚合工具（如 ELK Stack）
6. ✅ **更新依赖**: 定期更新 Docker 镜像和依赖包

---

## 9. 快速命令参考

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose stop

# 重启服务
docker compose restart

# 删除服务（保留数据）
docker compose down

# 删除服务和数据
docker compose down -v

# 查看日志
docker compose logs -f [service_name]

# 进入容器
docker compose exec llmops-api bash

# 查看环境变量
docker compose exec llmops-api env

# 重新构建
docker compose build --no-cache

# 拉取最新代码并重新部署
git pull && docker compose down && docker compose build && docker compose up -d
```

---

## 10. 联系与支持

- GitHub: https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents
- Issues: https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/issues

---

**祝部署顺利！🚀**
