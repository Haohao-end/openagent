# 配置重构快速参考

## 📋 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `docker/.env` | ✨ 新增 | Docker 基础设施配置 |
| `docker/docker-compose.yaml` | 🔄 重构 | 简化为 150 行(原 265 行) |
| `docker/README.md` | ✨ 新增 | 详细使用文档 |
| `docker/MIGRATION.md` | ✨ 新增 | 迁移指南 |
| `docker/start.sh` | ✨ 新增 | 快速启动脚本 |
| `docker/.gitignore` | ✨ 新增 | Git 忽略规则 |
| `api/docker/entrypoint.sh` | 🔄 更新 | 新增更多默认值 |
| `api/.env` | ♻️ 复用 | 业务配置(已存在) |

## 🎯 核心改进

### 1. 配置分层

```
┌─────────────────────────────────────┐
│  api/.env                           │
│  - 业务配置                          │
│  - 前端构建参数唯一来源              │
└─────────────────────────────────────┘
           ↓ Docker 构建直接读取
┌─────────────────────────────────────┐
│  docker-compose.yaml                │
│  - 服务编排                          │
│  - 直接构建 llmops-ui                │
└─────────────────────────────────────┘
           ↓ 引用
┌─────────────────────────────────────┐
│  docker/.env                        │
│  - 端口映射                          │
│  - 数据库密码                        │
│  - 镜像版本                          │
└─────────────────────────────────────┘
           ↓ 回退
┌─────────────────────────────────────┐
│  entrypoint.sh                      │
│  - 默认值                            │
│  - 兜底配置                          │
└─────────────────────────────────────┘
```

### 2. 配置对比

#### 旧方案 (硬编码)
```yaml
# docker-compose.yaml (265 行)
llmops-api:
  environment:
    JWT_SECRET_KEY: your-random-secret-key-here
    OPENAI_API_KEY: sk-your-openai-key-here
    DEEPSEEK_API_KEY: sk-your-deepseek-key-here
    MOONSHOT_API_KEY: sk-your-moonshot-key-here
    # ... 70+ 行配置
```

#### 新方案 (动态读取)
```yaml
# docker-compose.yaml (150 行)
llmops-api:
  env_file:
    - ../api/.env  # 自动读取所有配置
  environment:
    MODE: api      # 仅覆盖必要配置
    REDIS_HOST: llmops-redis
```

## 🚀 快速开始

### 方式 1: 使用启动脚本(推荐)

```bash
cd docker
./start.sh
```

### 方式 2: 手动启动

```bash
cd docker

# 1. 启动服务
docker compose up -d --build

# 2. 查看状态
docker compose ps
```

## 📝 常用命令

```bash
# 查看配置(验证变量替换)
docker compose config

# 查看日志
docker compose logs -f llmops-api

# 重启服务
docker compose restart llmops-api

# 停止服务
docker compose stop

# 删除服务(保留数据)
docker compose down

# 删除服务和数据
docker compose down -v
```

## 🔧 配置修改

### 修改 API Key

```bash
# 编辑 api/.env
vim ../api/.env

# 重启容器
docker compose restart llmops-api llmops-celery
```

### 修改端口

```bash
# 编辑 docker/.env
vim .env

# 重新创建容器
docker compose down
docker compose up -d --build
```

### 修改数据库密码

```bash
# 编辑 docker/.env
vim .env

# 删除数据并重新创建
docker compose down -v
docker compose up -d --build
```

## 🎨 配置示例

### docker/.env
```bash
# 基础设施配置
POSTGRES_PASSWORD=your_secure_password
REDIS_PASSWORD=your_redis_password
API_PORT=8001
UI_PORT=8080
```

### api/.env
```bash
# 业务配置
VITE_API_PREFIX=http://127.0.0.1:5001
OPENAI_API_KEY=sk-your-real-key
DEEPSEEK_API_KEY=sk-your-deepseek-key
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-secret
```

## ⚠️ 注意事项

1. **不要提交 .env 文件到 Git**
   - 已添加到 `.gitignore`
   - 使用 `.env.example` 作为模板

2. **配置优先级**
   ```
   docker-compose.yaml environment (最高)
   ↓
   api/.env
   ↓
   docker/.env
   ↓
   entrypoint.sh 默认值 (最低)
   ```

3. **网络隔离**
   - 容器内: `llmops-db`, `llmops-redis`
   - 本地开发: `localhost`

4. **数据持久化**
   - 数据存储在 `docker/volumes/`
   - 删除容器不会丢失数据
   - 使用 `docker compose down -v` 会删除数据

## 🐛 故障排查

### 容器无法启动

```bash
# 查看日志
docker compose logs llmops-api

# 检查配置
docker compose config

# 查看容器状态
docker compose ps
```

### 数据库连接失败

```bash
# 检查数据库是否就绪
docker compose ps llmops-db

# 查看数据库日志
docker compose logs llmops-db

# 测试连接
docker compose exec llmops-db pg_isready -U postgres
```

### API Key 无效

```bash
# 检查环境变量是否正确注入
docker compose exec llmops-api env | grep API_KEY

# 重启容器
docker compose restart llmops-api
```

## 📚 文档索引

- **README.md**: 详细使用文档
- **MIGRATION.md**: 迁移指南和技术细节
- **QUICKSTART.md**: 本文件,快速参考
- **.env.example**: 配置模板

## 🎉 优势总结

| 方面 | 改进 |
|------|------|
| 代码量 | docker-compose.yaml 减少 43% |
| 可维护性 | 配置集中,易于修改 |
| 安全性 | 敏感信息隔离 |
| 灵活性 | 支持多环境配置 |
| 易用性 | 提供启动脚本和文档 |
| 复用性 | 本地开发和 Docker 共用配置 |

## 🔗 相关链接

- [Docker Compose 文档](https://docs.docker.com/compose/)
- [环境变量最佳实践](https://12factor.net/config)
- [项目 CLAUDE.md](../CLAUDE.md)
