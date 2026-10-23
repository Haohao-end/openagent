<a id="readme-top"></a>

<div align="center">
  <img src="https://github.com/user-attachments/assets/15024f52-cb4d-4222-bd8e-b7aa385a6f3e" alt="OpenAgent Logo" width="360" />

  <p align="center">
    An end-to-end AI agent platform for building, orchestrating, publishing, and operating AI applications.
    <br />
    Flask + LangChain/LangGraph backend, Vue 3 workspace, visual workflows, datasets, tools, and OpenAPI delivery.
  </p>

  <p align="center">
    <strong>Sponsored by <a href="https://www.atlascloud.ai/?utm_source=github&utm_medium=link&utm_campaign=openagent">Atlas Cloud</a> and <a href="https://bloome.im/app?ref=uqIIEORd&utm_medium=github&utm_source=Haohao-end-openagent-ivor-202606">Bloome</a></strong>
  </p>

  <p align="center">
    <a href="https://openllm.cloud">Visit Website</a>
    ·
    <a href="https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417">API Docs</a>
    ·
    <a href="README_ZH.md">中文文档</a>
    ·
    <a href="https://github.com/Haohao-end/openagent">GitHub</a>
  </p>

  <p align="center">
    <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
    <img src="https://img.shields.io/badge/flask-3.x-000000?logo=flask&logoColor=white" alt="Flask" />
    <img src="https://img.shields.io/badge/vue-3-4FC08D?logo=vue.js&logoColor=white" alt="Vue 3" />
    <img src="https://img.shields.io/badge/docker-compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose" />
    <img src="https://img.shields.io/badge/weaviate-vector%20db-00C6A7" alt="Weaviate" />
    <a href="https://deepwiki.com/Haohao-end/openagent"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki" /></a>
  </p>
</div>

## Table of Contents

- [About The Project](#about-the-project)
- [Architecture](#architecture)
- [Built With](#built-with)
- [Getting Started](#getting-started)
- [Usage](#usage)
- [Testing](#testing)
- [Contact](#contact)
- [Acknowledgments](#acknowledgments)

## About The Project

<img alt="OpenAgent Product Overview" src="https://github.com/user-attachments/assets/0f8f7517-1622-46ea-9554-fb13af4841a1" />

OpenAgent is a full-stack platform for teams building AI applications rather than a single chat demo. The repository combines a Flask backend, Celery workers, a Vue 3 frontend, visual workflow authoring, dataset and document management, public app and workflow publishing, and OpenAPI-based delivery.

What the current codebase already supports:

- Use the home assistant to route user requests to published public agents through A2A, or turn natural-language requirements into new AI app creation flows.
- Build and manage AI apps from a dedicated workspace with draft, publish, analysis, version comparison, and prompt comparison flows.
- Enable Deep Research to let the app decompose complex tasks and coordinate bound capabilities across multi-step execution, suitable for scenarios requiring deep reasoning and concrete outputs.
- Design workflows visually with nodes for LLMs, tool calls, dataset retrieval, code execution, HTTP requests, branching, text processing, template transforms, and structured parameter extraction.
- Manage datasets, upload documents, inspect segments, and connect retrieval to agents and workflows.
- Browse public apps, tools, and workflows through store-style views.
- Expose published apps over REST and SSE through `POST /api/openapi/chat`.

## Architecture

<a href="https://github.com/user-attachments/assets/f6bdccf2-a6ff-4924-b68b-ec4d3581796e">
  <img src="https://github.com/user-attachments/assets/f6bdccf2-a6ff-4924-b68b-ec4d3581796e" alt="Basic chatbot architecture" width="100%" />
</a>

Click the diagram to view the full-resolution architecture image.

### Built With

- AI framework and orchestration: LangChain, LangGraph, workflow orchestration, tool calling, A2A delegation, skills, memory
- Knowledge and retrieval: RAG, semantic retrieval, full-text retrieval, hybrid retrieval, Weaviate, FAISS
- Backend: Python, Flask, SQLAlchemy, Celery, Flask-SocketIO, Redis, PostgreSQL
- Frontend: Vue 3, JavaScript / TypeScript, Vite, TailwindCSS, Pinia, Vue Flow, Arco Design
- Infrastructure and delivery: Docker Compose, Nginx, OpenAPI, SSE
- Model integrations: OpenAI, Atlas Cloud, DeepSeek, Grok, Google, Moonshot, Tongyi, Wenxin, Ollama, Zhipu

### Sponsored By

#### Atlas Cloud

<p align="center">
  <img src="ui/public/atlas-cloudXopenagent.jpg" alt="Atlas Cloud" width="560" />
</p>

- Atlas Cloud is a model provider on OpenRouter. Integrate it in this project via `ATLASCLOUD_API_KEY` and `ATLASCLOUD_API_BASE`.
- Official website: [Atlas Cloud](https://www.atlascloud.ai/?utm_source=github&utm_medium=link&utm_campaign=openagent)
- Integration docs: [https://www.atlascloud.ai/docs](https://www.atlascloud.ai/docs)

#### Bloome

<p align="center">
  <a href="https://bloome.im/app?ref=uqIIEORd&utm_medium=github&utm_source=Haohao-end-openagent-ivor-202606">
    <img src="ui/public/bloome-outreach-tmp.png" alt="Bloome" width="850" />
  </a>
</p>

- Bloome is an AI-agent IM platform where you can interact with AI agents and build collaborative communities. Official website: [Bloome](https://bloome.im/app?ref=uqIIEORd&utm_medium=github&utm_source=Haohao-end-openagent-ivor-202606)

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Getting Started

### Prerequisites

- Docker 20.10+
- Docker Compose 2.x
- 8 GB+ RAM recommended for the full stack
- Access to at least one supported model provider API key

### Installation

1. Clone the repository.

   ```bash
   git clone https://github.com/Haohao-end/openagent.git
   cd openagent
   ```

2. Create the runtime environment file.

   ```bash
   cp api/.env.example api/.env
   ```

3. Review the minimum required settings in `api/.env`.

   - `JWT_SECRET_KEY`
   - `POSTGRES_PASSWORD`
   - `REDIS_PASSWORD`
   - `WEAVIATE_API_KEY`
   - `VITE_API_PREFIX`
   - At least one provider key such as `OPENAI_API_KEY`, `ATLASCLOUD_API_KEY`, `DEEPSEEK_API_KEY`, or `DASHSCOPE_API_KEY`

4. Start the Docker stack.

   ```bash
   cd docker
   docker compose up -d --build
   ```

5. Open the local services.

   | Service | URL | Notes |
   | --- | --- | --- |
   | Frontend | http://localhost:3000 | Vue 3 web UI |
   | API | http://localhost:5001 | Flask REST API |
   | Nginx | http://localhost | Reverse proxy |

### Local Development

Backend:

```bash
cd api
pip install -r requirements.txt
flask run --port 5001
```

Frontend:

```bash
cd ui
npm install
npm run serve
```

Vite serves the frontend on port `5173` by default. The frontend configuration resolves the API base from `VITE_API_PREFIX`, and local development commonly proxies `/api` to the Flask backend.

Useful commands:

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

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Usage

### 1. Home Assistant Experience

<img width="2560" height="1418" alt="OpenAgent Home Assistant" src="https://github.com/user-attachments/assets/7ebb7827-838b-4bd2-b522-9f544f32416a" />

Use the home page as the default assistant entry point to route user questions to the most relevant published public agents through A2A, or describe a new idea in natural language and trigger AI app creation. The same surface also supports multi-turn chat, suggested prompts, image upload, and audio input.

### 2. App Workspace and Deep Research

<img width="1920" height="1080" alt="OpenAgent App Workspace Deep Research" src="https://github.com/user-attachments/assets/2dd4dc3e-f216-4c8d-96e4-7a2f81e138ae" />

The app workspace is the main work area for an AI app, not a standalone settings page. The left side handles model, prompt, and capability bindings. The right side is used for live debugging, execution traces, and result checks. In the current codebase, the README term `Deep Research` maps to the deep thinking mode behind `enable_deep_thinking`.

Key capabilities:

- Configuration and version management: manage model changes, prompt logic, drafts, publishing, version comparison, prompt comparison, and app duplication in one place.
- Capability integration: bind plugins, MCP, Skills, child Agent apps, workflows, and datasets through a single workspace.
- Complex task execution: with `Deep Research` enabled, the app can break work into steps and coordinate bound capabilities across a longer execution chain.
- Sandbox and artifact output: support script execution, code handling, file generation, and attachment export for tasks that need concrete outputs.
- Debugging and result verification: use the right-side panel to run real conversations and inspect deep execution timelines, task state, produced artifacts, and final results.

### 3. Visual Workflow Editor

<img width="2560" height="1599" alt="OpenAgent Workflow Editor" src="https://github.com/user-attachments/assets/23b510e2-1232-4f52-9262-812a7523ae21" />

Author workflows with nodes such as LLM, tool, dataset retrieval, code, HTTP request, template transform, text processor, variable assigner, parameter extractor, if/else, start, and end.

### 4. Dataset and Retrieval

<img width="2560" height="1418" alt="OpenAgent Dataset Management" src="https://github.com/user-attachments/assets/6f000681-db56-461a-bac9-a2dd5d6cd009" />

Create datasets, upload documents, inspect segments, and wire retrieval nodes into workflows or AI apps for knowledge-enabled behavior.

### 5. OpenAPI Delivery

<img width="2560" height="1418" alt="OpenAgent OpenAPI" src="https://github.com/user-attachments/assets/40769d35-89e1-4b76-9686-a431a77a42c7" />

Publish an app and call it over `POST /api/openapi/chat` with standard or streaming responses, including support for multi-turn conversation identifiers.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Testing

The repository already includes automated backend and frontend tests.

- Backend: `cd api && pytest`
- Frontend unit tests: `cd ui && npm run test:unit -- --run`
- Frontend type check: `cd ui && npm run type-check`
- Frontend build validation: `cd ui && npm run build`

## Contact

- Project Link: https://github.com/Haohao-end/openagent
- Website: https://openllm.cloud
- API Docs: https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417
- DeepWiki: https://deepwiki.com/Haohao-end/openagent

## Acknowledgments

- Thanks to Atlas Cloud and Bloome for supporting OpenAgent.
- Special thanks to Rui Yang and Haoyu Wang (Johns Hopkins University) for responsibly reporting a Host Header poisoning issue in the built-in tool icon URL construction and helping improve the security of this project.
- Special thanks to Ryan B for responsibly reporting an SSRF vulnerability in the custom API-tool server URL and helping improve the project's outbound request security.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
