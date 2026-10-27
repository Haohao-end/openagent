# Docker 部署配置说明

## ⚠️ 安全提示

**所有敏感信息（API Keys、密钥、密码）必须存储在 `.env` 文件中，绝不提交到 Git！**

详细安全配置请参考: [SECURITY.md](../SECURITY.md)

## 配置文件结构

```
docker/
├── .env                    # Docker Compose 基础设施配置(端口、密码等)
├── docker-compose.yaml     # 服务编排配置
└── ...

api/
├── .env                    # 应用业务配置(API Keys、LLM配置等)
└── ...
```

## 配置优先级

### 1. Docker 基础设施配置 (`docker/.env`)

用于配置 Docker 服务的基础参数:
- 数据库用户名/密码
- Redis 密码
- 端口映射
- 镜像版本

**这些配置会被 docker-compose.yaml 引用**

### 2. 应用业务配置 (`api/.env`)

用于配置应用的业务逻辑:
- LLM API Keys (OpenAI, DeepSeek, Moonshot 等)
- 第三方服务 Keys (高德地图、Serper 搜索等)
- OAuth 配置
- LangSmith 追踪配置
- 邮件服务配置

**这些配置通过 `env_file` 注入后端容器,`VITE_API_PREFIX` 还会被 UI Docker 构建直接读取**

### 3. Docker Compose 环境变量覆盖

在 `docker-compose.yaml` 的 `environment` 部分,会覆盖以下配置:
- `MODE`: 运行模式 (api/celery)
- `MIGRATION_ENABLED`: 是否执行数据库迁移
- 数据库/Redis/Weaviate 连接地址(使用 Docker 服务名)

## 配置流程

### 方式一: 直接使用 `docker compose` (推荐)

1. 确保 `api/.env` 文件存在并配置完整,尤其是 `VITE_API_PREFIX`
2. 启动服务:
   ```bash
   cd docker
   docker compose up -d --build
   ```
3. 查看状态:
   ```bash
   docker compose ps
   ```

**说明**:
- `api/.env` 是后端运行配置和 UI 构建时 `VITE_API_PREFIX` 的唯一来源
- `llmops-ui` 构建时会直接读取 `../api/.env`,不再需要 `.ui-build.env`
- 缺少 `VITE_API_PREFIX` 时,UI 镜像会在构建阶段直接失败

### 方式二: 使用启动脚本

```bash
cd docker
./start.sh
```

## 环境变量说明

### docker/.env 变量

`docker/.env` 用于 Compose 文件插值，例如端口和镜像标签。PostgreSQL 与 Redis 的用户名、数据库名和密码由各服务从 `api/.env` 读取。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| WEAVIATE_API_KEY | 未设置时使用 Compose 配置中的回退值 | Weaviate API Key |
| UI_PORT | 3000 | 前端端口 |
| API_PORT | 5001 | API 端口 |
| REDIS_PORT | 6379 | Redis 端口 |
| POSTGRES_PORT | 5432 | PostgreSQL 端口 |
| WEAVIATE_HTTP_PORT | 8080 | Weaviate HTTP 端口 |
| WEAVIATE_GRPC_PORT | 50051 | Weaviate gRPC 端口 |
| NGINX_HTTP_PORT | 80 | Nginx HTTP 端口 |
| NGINX_HTTPS_PORT | 443 | Nginx HTTPS 端口 |
| IMAGE_VERSION | 0.1.0 | 镜像版本标签 |

### api/.env 变量

参考 `api/.env.example` 或项目文档中的完整说明。

主要包括:
- 前端构建配置 (`VITE_API_PREFIX`)
- Flask 配置 (FLASK_DEBUG, FLASK_ENV)
- JWT 密钥
- PostgreSQL 用户名、密码和数据库名，以及 Redis 密码 (本地开发时使用 localhost 连接)
- LLM 服务商配置 (OpenAI, DeepSeek, 月之暗面等)
- 工具插件配置 (高德地图, Serper 搜索, GitHub Token 等)
- OAuth 配置 (GitHub, Google)
- 对象存储配置 (腾讯云 COS)
- 邮件服务配置

## 常见场景

### 场景 1: 修改 LLM API Key

只需修改 `api/.env`:
```bash
# 编辑 api/.env
OPENAI_API_KEY=your-new-key

# 重启相关服务
cd docker
docker compose restart llmops-api llmops-celery
```

### 场景 2: 轮换数据库和 Redis 密码

PostgreSQL 已有数据目录时，只修改环境变量不会更新数据库角色密码。先连接现有数据库并在 `psql` 提示符运行 `\password`，按提示为当前用户设置新密码：

```bash
cd docker
docker compose exec llmops-db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

然后将 `POSTGRES_PASSWORD` 和 `REDIS_PASSWORD` 更新到 `api/.env`，并仅重建使用这些配置的服务：

```bash
vim ../api/.env
docker compose up -d --no-build --no-deps llmops-db llmops-redis llmops-api llmops-celery
```

不要使用 `docker compose down -v` 轮换密码；该命令会删除数据库、Redis 和 Weaviate 的持久化卷。

### 场景 3: 修改端口映射

修改 `docker/.env`:
```bash
# 编辑 docker/.env
API_PORT=8001
UI_PORT=8080

# 重新创建容器
cd docker
docker compose down
docker compose up -d --build
```

### 场景 4: 本地开发 + Docker 基础设施

1. 启动 Docker 基础设施(数据库、Redis、Weaviate):
   ```bash
   cd docker
   docker compose up -d llmops-db llmops-redis llmops-weaviate
   ```

2. 本地运行 API 和 UI:
   ```bash
   # 终端 1: 启动 API
   cd api
   flask run --port 5001

   # 终端 2: 启动 Celery
   cd api
   celery -A app.http.app:celery worker --loglevel=info

   # 终端 3: 启动 UI
   cd ui
   npm run serve
   ```

## 注意事项

1. **网络隔离**: Docker 容器内部使用服务名通信(如 `llmops-db`),本地开发使用 `localhost`
2. **配置同步**: 修改 `api/.env` 中的 `VITE_API_PREFIX` 后,需要重新 build `llmops-ui`
3. **密钥安全**: 不要将包含真实密钥的 `.env` 文件提交到 Git
4. **健康检查**: 数据库和 Redis 配置了健康检查,API 和 Celery 会等待它们就绪后再启动
5. **数据持久化**: 数据库、Redis、Weaviate 的数据都挂载到 `docker/volumes/` 目录
6. **前端构建约束**: `llmops-ui` 构建时会直接读取 `api/.env` 中的 `VITE_API_PREFIX`
7. **Weaviate 升级**: Weaviate 只支持逐个小版本升级(如 1.28 → 1.29 → 1.30 …),不能跳过小版本。如果 `docker/volumes/weaviate` 中已有旧版本(如 1.28.x)的数据,请先备份该目录,再依次使用每个中间小版本的最新补丁版启动一次 `llmops-weaviate`(等待 `/v1/.well-known/ready` 就绪),最后再切换到 `docker-compose.yaml` 中的版本。全新部署无需此步骤。参见 [Weaviate 升级说明](https://docs.weaviate.io/deploy/migration)

## 故障排查

### 容器无法启动

```bash
# 查看容器日志
docker compose logs llmops-api
docker compose logs llmops-celery

# 查看所有容器状态
docker compose ps
```

### 数据库连接失败

检查 `docker/.env` 中的数据库密码是否与 `docker-compose.yaml` 中的配置一致。

### API Key 无效

检查 `api/.env` 中的 API Key 是否正确配置:
```bash
cd docker
docker compose restart llmops-api llmops-celery
```

## 清理与重置

```bash
# 停止所有服务
docker compose down

# 删除所有数据(谨慎操作!)
sudo rm -rf volumes/

# 重新启动
docker compose up -d --build
```
