<a id="readme-top"></a>

<div align="center">
  <img src="https://github.com/user-attachments/assets/15024f52-cb4d-4222-bd8e-b7aa385a6f3e" alt="OpenAgent Logo" width="360" />

  <p align="center">
    An end-to-end AI agent platform for building, orchestrating, publishing, and operating AI applications.
    <br />
    Flask + LangChain/LangGraph backend, Vue 3 workspace, visual workflows, datasets, tools, and OpenAPI delivery.
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
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Testing](#testing)
- [Contact](#contact)
- [Acknowledgments](#acknowledgments)

## About The Project

<img width="2560" height="1418" alt="OpenAgent Product Overview" src="https://github.com/user-attachments/assets/0f8f7517-1622-46ea-9554-fb13af4841a1" />

OpenAgent is a full-stack platform for teams building AI applications rather than a single chat demo. The repository combines a Flask backend, Celery workers, a Vue 3 frontend, visual workflow authoring, dataset and document management, public app and workflow publishing, and OpenAPI-based delivery.

What the current codebase already supports:

- Use the home assistant to route user requests to published public agents through A2A, or turn natural-language requirements into new AI app creation flows.
- Build and manage AI apps from a dedicated workspace with draft, publish, analysis, version comparison, and prompt comparison flows.
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
- Model integrations: OpenAI, DeepSeek, Grok, Google, Moonshot, Tongyi, Wenxin, Ollama, Zhipu

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
   - At least one provider key such as `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, or `DASHSCOPE_API_KEY`

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

### 2. App Workspace

<img width="2560" height="1418" alt="OpenAgent Apps Workspace" src="https://github.com/user-attachments/assets/ec6f6bdb-70d6-4803-8b53-e60185b23da0" />

Manage app drafts, published versions, analysis views, prompt comparisons, copies, and publishing actions from the app workspace.

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

## Project Structure

```text
.
├── api/          # Flask backend, services, handlers, tasks, migrations, tests
├── ui/           # Vue 3 frontend, routes, views, components, tests
├── docker/       # Docker Compose stack, nginx, postgres init, deployment config
├── README.md     # English project overview
└── README_ZH.md  # Chinese project overview
```

## Documentation

- [README_ZH.md](README_ZH.md) - Chinese project overview
- [api/README.md](api/README.md) - backend notes
- [ui/README.md](ui/README.md) - frontend notes
- [docker/README.md](docker/README.md) - Docker stack details
- [api/.env.example](api/.env.example) - environment reference

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

- Special thanks to Rui Yang and Haoyu Wang (Johns Hopkins University) for responsibly reporting a Host Header poisoning issue in the built-in tool icon URL construction and helping improve the security of this project.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
