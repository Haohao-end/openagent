<a id="readme-top"></a>

<div align="center">
  <img src="https://github.com/user-attachments/assets/15024f52-cb4d-4222-bd8e-b7aa385a6f3e" alt="OpenAgent Logo" width="360" />

  <p align="center">
    一个面向 AI 应用构建、编排、发布与运营的端到端 Agent 平台。
    <br />
    基于 Flask + LangChain/LangGraph 的后端，配合 Vue 3 工作台、可视化工作流、数据集、工具与 OpenAPI 交付能力。
  </p>

  <p align="center">
    <a href="https://openllm.cloud">访问官网</a>
    ·
    <a href="https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417">API 文档</a>
    ·
    <a href="README.md">English</a>
    ·
    <a href="https://github.com/Haohao-end/openagent">GitHub</a>
  </p>

  <p align="center">
    <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
    <img src="https://img.shields.io/badge/flask-3.x-000000?logo=flask&logoColor=white" alt="Flask" />
    <img src="https://img.shields.io/badge/vue-3-4FC08D?logo=vue.js&logoColor=white" alt="Vue 3" />
    <img src="https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose" />
    <img src="https://img.shields.io/badge/weaviate-vector%20db-00C6A7" alt="Weaviate" />
  </p>
</div>

## 目录

- [项目简介](#项目简介)
- [架构图](#架构图)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [功能展示](#功能展示)
- [项目结构](#项目结构)
- [文档与说明](#文档与说明)
- [测试](#测试)
- [Roadmap](#roadmap)
- [安全致谢](#安全致谢)
- [许可证](#许可证)
- [联系方式](#联系方式)
- [鸣谢](#鸣谢)

## 项目简介

<img width="2560" height="1418" alt="OpenAgent Product Overview" src="https://github.com/user-attachments/assets/0f8f7517-1622-46ea-9554-fb13af4841a1" />

OpenAgent 不是单一的聊天 Demo，而是一个面向团队和产品化场景的全栈 AI Agent 平台。当前仓库同时包含 Flask 后端、Celery 后台任务、Vue 3 前端工作台、可视化工作流编排、数据集与文档管理、公共应用发布，以及基于 OpenAPI 的对外调用能力。

当前代码库已经覆盖这些核心能力：

- 首页助手可以通过 A2A 将用户问题路由到应用广场中已发布的公共 Agent，也可以把自然语言需求转成新的 AI Agent / 应用创建流程。
- 在独立工作台中创建和管理 AI 应用，支持草稿、发布、分析、版本对比和提示词对比。
- 通过可视化节点编排工作流，节点涵盖 LLM、工具调用、知识库检索、代码执行、HTTP 请求、条件分支、文本处理、模板转换和参数提取。
- 管理数据集、上传文档、查看切片，并把检索能力接入工作流或应用。
- 通过类似应用商店的页面浏览公共应用、工具和工作流。
- 通过 `POST /api/openapi/chat` 以 REST 或流式方式调用已发布应用。

## 架构图

<a href="https://github.com/user-attachments/assets/f6bdccf2-a6ff-4924-b68b-ec4d3581796e">
  <img src="https://github.com/user-attachments/assets/f6bdccf2-a6ff-4924-b68b-ec4d3581796e" alt="Basic chatbot architecture" width="100%" />
</a>

点击图片可查看原始大图。

### 技术栈

- AI 开发框架与编排：LangChain、LangGraph、Workflow 编排、工具调用、A2A 委派、Skill、Memory
- 知识与检索：RAG、向量检索、全文检索、混合检索、Weaviate、FAISS
- 后端：Python、Flask、SQLAlchemy、Celery、Flask-SocketIO、Redis、PostgreSQL
- 前端：Vue 3、JavaScript / TypeScript、Vite、TailwindCSS、Pinia、Vue Flow、Arco Design
- 基础设施与交付：Docker Compose、Nginx、OpenAPI、SSE
- 模型接入：OpenAI、DeepSeek、Grok、Google、Moonshot、Tongyi、Wenxin、Ollama、Zhipu

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 快速开始

### 环境要求

- Docker 20.10+
- Docker Compose 2.x
- 推荐 8 GB+ 内存运行完整栈
- 至少准备一个可用的模型提供商 API Key

### 安装与启动

1. 克隆仓库。

   ```bash
   git clone https://github.com/Haohao-end/openagent.git
   cd openagent
   ```

2. 创建运行时环境文件。

   ```bash
   cp api/.env.example api/.env
   ```

3. 检查 `api/.env` 中的最小必填项。

   - `JWT_SECRET_KEY`
   - `POSTGRES_PASSWORD`
   - `REDIS_PASSWORD`
   - `WEAVIATE_API_KEY`
   - `VITE_API_PREFIX`
   - 至少一个模型提供商 Key，例如 `OPENAI_API_KEY`、`DEEPSEEK_API_KEY` 或 `DASHSCOPE_API_KEY`

4. 启动 Docker 编排。

   ```bash
   cd docker
   docker compose up -d --build
   ```

5. 打开本地服务。

   | 服务 | 地址 | 说明 |
   | --- | --- | --- |
   | 前端 | http://localhost:3000 | Vue 3 Web 界面 |
   | API | http://localhost:5001 | Flask REST API |
   | Nginx | http://localhost | 反向代理 |

### 本地开发

后端：

```bash
cd api
pip install -r requirements.txt
flask run --port 5001
```

前端：

```bash
cd ui
npm install
npm run serve
```

Vite 默认在 `5173` 端口提供服务。前端会基于 `VITE_API_PREFIX` 解析 API 地址，在本地开发时通常通过 `/api` 代理到 Flask 后端。

常用命令：

```bash
cd api
pytest
```

```bash
cd ui
npm run type-check
npm run lint
npm run build
npm run test:unit -- --run
```

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 功能展示

### 1. 首页助手体验

<img width="2560" height="1418" alt="OpenAgent Home Assistant" src="https://github.com/user-attachments/assets/7ebb7827-838b-4bd2-b522-9f544f32416a" />

首页可以作为默认的 AI 助手入口，通过 A2A 将用户问题路由到应用广场里最相关的已发布公共 Agent，也可以把自然语言需求转成新的 AI Agent / 应用创建流程。同一个入口还支持多轮对话、推荐问题、图片上传和语音输入。

### 2. 应用工作台

<img width="2560" height="1418" alt="OpenAgent Apps Workspace" src="https://github.com/user-attachments/assets/ec6f6bdb-70d6-4803-8b53-e60185b23da0" />

在应用工作台中可以管理草稿、发布版本、分析页、提示词对比、复制应用以及发布相关操作。

### 3. 可视化工作流编辑器

<img width="2560" height="1599" alt="OpenAgent Workflow Editor" src="https://github.com/user-attachments/assets/23b510e2-1232-4f52-9262-812a7523ae21" />

工作流支持通过节点方式编排，包括 LLM、工具调用、数据集检索、代码执行、HTTP 请求、模板转换、文本处理、变量赋值、参数提取、条件分支、开始节点和结束节点。

### 4. 数据集与检索

<img width="2560" height="1418" alt="OpenAgent Dataset Management" src="https://github.com/user-attachments/assets/6f000681-db56-461a-bac9-a2dd5d6cd009" />

你可以创建数据集、上传文档、查看文档切片，并将检索能力接入工作流或 AI 应用，实现知识增强行为。

### 5. OpenAPI 交付

<img width="2560" height="1418" alt="OpenAgent OpenAPI" src="https://github.com/user-attachments/assets/40769d35-89e1-4b76-9686-a431a77a42c7" />

应用发布后，可以通过 `POST /api/openapi/chat` 进行标准调用或流式调用，并支持多轮对话所需的会话标识。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>

## 项目结构

```text
.
├── api/          # Flask 后端、服务、处理器、任务、迁移和测试
├── ui/           # Vue 3 前端、路由、页面、组件和测试
├── docker/       # Docker Compose、nginx、postgres 初始化和部署配置
├── README.md     # 英文项目说明
└── README_ZH.md  # 中文项目说明
```

## 文档与说明

- [README.md](README.md) - English project overview
- [api/README.md](api/README.md) - 后端说明
- [ui/README.md](ui/README.md) - 前端说明
- [docker/README.md](docker/README.md) - Docker 说明
- [api/.env.example](api/.env.example) - 环境变量参考

## 测试

仓库已经包含自动化的后端与前端测试能力。

- 后端：`cd api && pytest`
- 前端单元测试：`cd ui && npm run test:unit -- --run`
- 前端类型检查：`cd ui && npm run type-check`
- 前端构建校验：`cd ui && npm run build`

## Roadmap

- [ ] 保持 `README.md` 与 `README_ZH.md` 结构同步
- [ ] 补充仓库根目录 `LICENSE` 文件
- [ ] 增加更完整的自托管部署和生产运行说明

## 安全致谢

感谢 Rui Yang 和 Haoyu Wang（Johns Hopkins University）以负责任披露的方式报告了内置工具图标 URL 构造中的 Host Header poisoning 问题，帮助项目进一步改进安全性。

## 许可证

当前仓库根目录尚未提供独立的 `LICENSE` 文件。如果你希望对使用者、贡献者和下游项目明确许可证边界，建议补充该文件。

## 联系方式

- 项目地址：https://github.com/Haohao-end/openagent
- 官网：https://openllm.cloud
- API 文档：https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417

## 鸣谢

- README 结构参考了 [Best-README-Template](https://github.com/othneildrew/Best-README-Template)
- 感谢 Rui Yang 和 Haoyu Wang（Johns Hopkins University）以负责任披露的方式报告了内置工具图标 URL 构造中的 Host Header poisoning 问题，帮助项目进一步改进安全性。

<p align="right">(<a href="#readme-top">返回顶部</a>)</p>
