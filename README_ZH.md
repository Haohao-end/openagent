# 🚀 LLMOps - 端到端大模型运维平台

<div align="center">

![AI Agent](https://github.com/user-attachments/assets/f4cad915-411e-4e0f-95bc-8f8afdcf1019)

[![许可证](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-20.10+-blue.svg)](https://www.docker.com/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents)

[English](README.md) | [中文](README_ZH.md)

**🌐 在线演示**: http://82.157.66.198/

**📚 技术文档**: https://deepwiki.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents

**📖 API 文档**: https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417

</div>

---

## 📋 目录

- [项目概述](#-项目概述)
- [功能特性](#-功能特性)
- [系统架构](#-系统架构)
- [快速开始](#-快速开始)
- [部署指南](#-部署指南)
- [配置说明](#-配置说明)
- [文档中心](#-文档中心)
- [许可证](#-许可证)

---

## 🎯 项目概述

**LLMOps** 是一个用于构建、部署和管理支持多模型提供商的 AI Agent 应用的综合平台。它采用 Python Flask 后端配合 LangChain/LangGraph 编排能力，结合 Vue 3 前端，能够无缝开发智能 Agent 工作流。

### 🌟 核心亮点

- 🤖 **多 Agent 系统**: 使用 LangGraph 构建复杂的 AI Agent
- 🔄 **可视化工作流构建器**: 拖拽式工作流设计界面
- 🧠 **多模型支持**: 支持 OpenAI、DeepSeek、Claude、Moonshot、千帆等多种模型
- 📊 **RAG 集成**: 使用 Weaviate 向量数据库实现知识检索
- 🔧 **内置工具**: 20+ 预置工具（搜索、天气、地图等）
- 🔐 **企业级安全**: OAuth、JWT、基于角色的访问控制
- 📈 **实时分析**: 监控 Agent 性能和用量
- 🐳 **Docker 就绪**: 通过 Docker Compose 一键部署

---

## ✨ 功能特性

### 🤖 AI Agent 开发

- **函数调用 Agent**: 通过 LLM 直接调用函数
- **ReAct Agent**: 结合工具进行推理和行动
- **自定义 Agent**: 构建自己的 Agent 类型
- **Agent 队列管理**: 处理并发 Agent 请求

### 🔄 工作流系统

<img width="1920" height="959" alt="工作流" src="https://github.com/user-attachments/assets/26d6dd8f-03d2-4b45-8ae0-a9817771fa08" />

- **可视化编辑器**: 拖拽式工作流构建器
- **节点类型**: LLM、工具、知识检索、代码执行、If-Else 条件判断
- **DAG 执行**: 有向无环图工作流引擎
- **实时流式响应**: 基于 SSE 的流式响应

### 🧠 知识管理

- **数据集管理**: 上传和管理文档
- **向量存储**: 集成 Weaviate 实现语义搜索
- **多格式支持**: 支持 PDF、DOCX、TXT、Markdown 格式
- **分块策略**: 可配置的文本分割策略

### 🔧 内置工具

- **搜索**: Google Serper、SerpAPI、Tavily AI
- **天气**: OpenWeatherMap
- **地图**: 高德地图 API
- **新闻**: News API
- **计算**: Wolfram Alpha
- **代码**: GitHub 集成
- **图像生成**: Stability AI
- **自定义工具**: 基于 API 的工具集成

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         前端 (Vue 3)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Agent   │  │  工作流  │  │  数据集  │  │   工具   │   │
│  │  构建器  │  │  编辑器  │  │  管理器  │  │  管理器  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/SSE
┌─────────────────────────────────────────────────────────────┐
│                      后端 (Flask + Celery)                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │               API 层 (Flask)                          │  │
│  │   控制器 → 服务层 → 模型层 → 数据库                  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            核心引擎 (LangChain/LangGraph)             │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │  │
│  │  │  Agent   │  │  工作流  │  │   RAG    │          │  │
│  │  │   引擎   │  │   引擎   │  │   引擎   │          │  │
│  │  └──────────┘  └──────────┘  └──────────┘          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │             后台任务 (Celery)                          │  │
│  │           文档索引、邮件发送等                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                     基础设施层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │PostgreSQL│  │  Redis   │  │ Weaviate │  │  Nginx   │   │
│  │   数据库 │  │  缓存    │  │ 向量数据库│  │  反向代理│   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- 推荐 8GB+ 内存

### 一键部署

```bash
# 克隆仓库
git clone https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git
cd LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents

# 配置环境变量
cp api/.env.example api/.env
vim api/.env  # 填写你的 API 密钥

# 启动服务
cd docker
bash start.sh
```

### 访问服务

| 服务  | 访问地址              | 说明           |
| ----- | --------------------- | -------------- |
| 前端  | http://localhost:3000 | Vue 3 Web 界面 |
| API   | http://localhost:5001 | Flask REST API |
| Nginx | http://localhost      | 反向代理       |

---

## 🐳 部署指南

### 服务器部署（一键脚本）

```bash
# SSH 登录到服务器
ssh root@your-server-ip

# 运行部署脚本
bash <(curl -fsSL https://raw.githubusercontent.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/main/deploy-server.sh)
```

### 手动部署

详细说明请参考 **[DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md)**。

---

## ⚙️ 配置说明

### 必需的环境变量

根据 `api/.env.example` 创建 `api/.env` 文件：

```bash
# LLM 提供商（至少配置一个）
OPENAI_API_KEY=sk-your-openai-key
DEEPSEEK_API_KEY=sk-your-deepseek-key
MOONSHOT_API_KEY=sk-your-moonshot-key

# 数据库（Docker 中自动配置）
SQLALCHEMY_DATABASE_URI=postgresql://postgres:password@llmops-db:5432/llmops

# Redis（Docker 中自动配置）
REDIS_HOST=llmops-redis
REDIS_PASSWORD=your-redis-password

# JWT 密钥（使用命令生成：openssl rand -hex 32）
JWT_SECRET_KEY=your-random-secret-key
```

安全最佳实践请参考 **[docker/SECURITY.md](docker/SECURITY.md)**。

---

## 📚 文档中心

### 核心文档

- **[部署指南](docs/deployment/DEPLOYMENT.md)** - 完整的部署说明
- **[快速入门指南](docs/deployment/QUICKSTART_GUIDE.md)** - 快速上手指南
- **[CLAUDE.md](CLAUDE.md)** - 面向 AI 助手的项目架构说明
- **[API 文档](https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417)** - REST API 参考文档

### Docker 与基础设施

- **[docker/README.md](docker/README.md)** - Docker 配置说明
- **[docker/SECURITY.md](docker/SECURITY.md)** - 安全指南

### 开发指南

- **[Agent 开发指南](docs/development/AGENTS.md)** - Agent 开发说明
- **[API 配置指南](docs/development/API_CONFIG_SUMMARY.md)** - API 配置说明
- **[前端开发指南](docs/development/FRONTEND_IMPLEMENTATION_GUIDE.md)** - 前端开发说明

### 功能文档

- **[图标生成系统](docs/features/ICON_GENERATION_COMPLETE_GUIDE.md)** - 图标生成系统完整指南
- **[If-Else 工作流](docs/features/IF_ELSE_ARCHITECTURE.md)** - 条件工作流节点说明

### 测试与质量

- **[测试指南](docs/testing/TEST_GUIDE.md)** - 测试规范
- **[Bug 修复记录](docs/bugfix/)** - Bug 修复历史

---

## 🛠️ 开发指南

### 后端开发 (Flask)

```bash
cd api
pip install -r requirements.txt
flask run --port 5001

# 运行测试
pytest

# 运行 Celery 工作进程
celery -A app.http.app:celery worker --loglevel=info
```

### 前端开发 (Vue 3)

```bash
cd ui
npm install
npm run serve

# 生产环境构建
npm run build
```

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM 编排框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent 工作流引擎
- [Weaviate](https://github.com/weaviate/weaviate) - 向量数据库
- [Vue 3](https://github.com/vuejs/core) - 渐进式 JavaScript 框架
- [Flask](https://github.com/pallets/flask) - Python Web 框架

---

## 📞 联系与支持

- **GitHub Issues**: [报告 Bug 或请求功能](https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/issues)
- **技术文档**: [DeepWiki](https://deepwiki.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents)
- **在线演示**: http://82.157.66.198/

---

## 🔒 安全致谢

特别感谢约翰霍普金斯大学的 Rui Yang 和 Haoyu Wang 负责任地报告了内置工具图标 URL 构建中的主机头污染问题，并帮助改进了本项目的安全性。

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个 Star！**

由 [Haohao-end](https://github.com/Haohao-end) 用心打造 ❤️

</div>
