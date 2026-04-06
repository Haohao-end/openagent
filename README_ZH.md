# LLMOps - 端到端大模型运维平台

<div align="center">

![AI Agent](https://github.com/user-attachments/assets/f4cad915-411e-4e0f-95bc-8f8afdcf1019)

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-20.10+-blue.svg)](https://www.docker.com/)

[English](README.md) | [中文](README_ZH.md)

**在线演示**: http://82.157.66.198/

**API 文档**: https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417

</div>

---

## 项目概述

LLMOps 是一个面向 AI Agent 应用构建与运维的全栈平台。当前仓库包含：

- 基于 Flask 的后端服务，结合 LangChain / LangGraph 做编排
- 基于 Vue 3 的前端，用于 Agent、工作流、数据集、工具和对话管理
- 用于后台任务的 Celery
- Docker 方案里包含 PostgreSQL、Redis、Weaviate 和 Nginx

当前代码库主要覆盖这些能力：

- 多模型接入
- 工作流编排和执行
- 对话管理与搜索
- 应用和工作流发布
- 知识库、文档和数据集管理
- 内置工具与通知链路

---

## 项目结构

```text
.
├── api/        # Flask 后端、服务层、处理器、任务、测试
├── ui/         # Vue 3 前端、组件、页面、测试
├── docker/     # Docker Compose 和部署配置
├── docs/       # 文档索引与部署说明
└── README_ZH.md
```

---

## 功能特性

### 后端

- Flask REST API
- 服务层分层结构
- JWT、OAuth 和账号权限流程
- SSE / WebSocket 实时通知
- 基于 Celery 的后台任务

### 前端

- Vue 3 + Vite + TypeScript
- 工作流编辑器和应用管理页面
- 对话历史、搜索和发布页面
- 通知组件和实时 UI 更新

### 基础设施

- Docker Compose 一键部署
- PostgreSQL 持久化存储
- Redis 作为缓存和任务队列
- Weaviate 向量检索
- Nginx 反向代理

---

## 系统架构

```text
┌─────────────────────────────────────────────────────────────┐
│                         前端 (Vue 3)                          │
│   Agent 构建器   工作流编辑器   数据集管理   工具界面         │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP / SSE / WebSocket
┌─────────────────────────────────────────────────────────────┐
│                      后端 (Flask + Celery)                    │
│   API 层   服务层   LangChain / LangGraph   后台任务          │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                         基础设施                              │
│      PostgreSQL      Redis      Weaviate      Nginx          │
└─────────────────────────────────────────────────────────────┘
```

---

## 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 推荐 8GB+ 内存运行完整栈

### Docker 启动

```bash
git clone https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git
cd LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents

cp api/.env.example api/.env
# 编辑 api/.env，填入必要的 API Key

cd docker
docker compose up -d --build
```

### 服务地址

| 服务 | 地址 | 说明 |
|---|---|---|
| 前端 | http://localhost:3000 | Vue 3 Web 界面 |
| API | http://localhost:5001 | Flask REST API |
| Nginx | http://localhost | 反向代理 |

更多部署细节请查看 [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) 和 [docker/README.md](docker/README.md)。

---

## 本地开发

### 后端

```bash
cd api
pip install -r requirements.txt
flask run --port 5001
```

运行测试：

```bash
cd api
pytest
```

### 前端

```bash
cd ui
npm install
npm run serve
```

Vite 默认在 `5173` 端口提供服务，并将 `/api` 代理到 `http://localhost:5001`。

常用前端命令：

```bash
cd ui
npm run type-check
npm run lint
npm run build
npm run test:unit -- --run
```

---

## 配置说明

### 后端配置

先将 `api/.env.example` 复制为 `api/.env`，并至少配置一个模型提供商的 Key，以及数据库和 Redis 的必要参数。

### Docker 配置

如果你需要修改端口、容器密码或其他基础设施参数，请查看 [docker/README.md](docker/README.md)。

### 重要参考

- [api/.env.example](api/.env.example)
- [docker/README.md](docker/README.md)
- [docker/SECURITY.md](docker/SECURITY.md)
- [CLAUDE.md](CLAUDE.md)

---

## 文档

- [docs/deployment/DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md) - 部署指南
- [docs/deployment/QUICKSTART_GUIDE.md](docs/deployment/QUICKSTART_GUIDE.md) - 快速开始指南
- [api/README.md](api/README.md) - 后端说明
- [ui/README.md](ui/README.md) - 前端说明
- [docker/README.md](docker/README.md) - Docker 配置
- [docker/SECURITY.md](docker/SECURITY.md) - 安全说明

---

## 测试

仓库已经包含较完整的自动化测试。

- 后端：`cd api && pytest`
- 前端：`cd ui && npm run test:unit -- --run`

---

## 许可证

当前仓库根目录还没有单独的 `LICENSE` 文件。如果你需要显式声明许可证，建议补充该文件并同步更新这里。
