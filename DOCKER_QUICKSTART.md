# 🚀 Docker 快速启动指南

## 📋 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 8GB+ 内存

---

## ⚡ 快速启动（3 步）

### 步骤 1: 配置环境变量

```bash
# 复制模板文件
cp api/.env.example api/.env

# 编辑配置文件，填入你的真实 API Keys
vim api/.env
```

**必须配置的项**:
- `POSTGRES_PASSWORD` - 数据库密码
- `REDIS_PASSWORD` - Redis 密码
- 至少一个 LLM API Key (如 `OPENAI_API_KEY`)
- `JWT_SECRET_KEY` - JWT 密钥（生成方法: `openssl rand -hex 32`）

### 步骤 2: 启动服务

```bash
cd docker
docker compose up -d --build
```

### 步骤 3: 验证服务

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

---

## 🌐 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3000 | Vue 3 Web UI |
| API | http://localhost:5001 | Flask REST API |
| Nginx | http://localhost | 反向代理 |

---

## 🔧 配置说明

### 配置文件位置

- `api/.env` - 你的真实配置（不会提交到 Git）
- `api/.env.example` - 配置模板（只包含键名）

### 配置读取顺序

```
docker-compose.yaml
    ↓ 读取
api/.env (你的真实配置)
    ↓ 覆盖
environment (Docker 特定配置)
```

### 数据库连接

- **本地开发**: 使用 `localhost`
- **Docker 环境**: 自动覆盖为 `llmops-db`

你不需要修改数据库连接字符串，Docker 会自动处理！

---

## 📝 常用命令

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose stop

# 重启服务
docker compose restart

# 查看日志
docker compose logs -f llmops-api

# 删除服务（保留数据）
docker compose down

# 删除服务和数据
docker compose down -v

# 重新构建
docker compose up -d --build
```

---

## 🔍 故障排查

### 问题 1: 端口冲突

**错误**: `bind: address already in use`

**解决**: 修改 `api/.env` 中的端口配置
```ini
UI_PORT=3001
API_PORT=5002
NGINX_HTTP_PORT=8080
```

### 问题 2: 数据库连接失败

**检查**:
```bash
# 查看数据库日志
docker compose logs llmops-db

# 检查数据库是否就绪
docker compose exec llmops-db pg_isready -U postgres
```

### 问题 3: API 启动失败

**检查**:
```bash
# 查看 API 日志
docker compose logs llmops-api

# 检查环境变量
docker compose exec llmops-api env | grep API_KEY
```

---

## 🔒 安全提示

### ✅ 正确的做法

1. `api/.env` 只在本地，不提交到 Git
2. 使用强密码（至少 32 字符）
3. 定期更换密钥
4. 生产环境启用 HTTPS

### ❌ 避免的错误

1. 不要在代码中硬编码密钥
2. 不要在文档中使用真实密钥
3. 不要提交 `.env` 文件到 Git
4. 不要使用弱密码（如 `123456`）

---

## 📚 更多文档

- [完整部署指南](docs/deployment/DEPLOYMENT.md)
- [项目结构说明](PROJECT_STRUCTURE.md)
- [脚本使用指南](scripts/README.md)
- [文档索引](docs/README.md)

---

## 🎉 就这么简单！

配置 `api/.env` → `docker compose up -d` → 完成！
