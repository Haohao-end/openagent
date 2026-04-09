# OpenAgent - End-to-End AI Agent Platform

<div align="center">

![AI Agent](https://github.com/user-attachments/assets/f4cad915-411e-4e0f-95bc-8f8afdcf1019)

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-20.10+-blue.svg)](https://www.docker.com/)

[English](README.md) | [中文](README_ZH.md)

**Demo**: http://82.157.66.198/

**API Docs**: https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417

</div>

---

## Overview

OpenAgent is a full-stack platform for building and operating AI agent applications. The repository contains:

- A Flask backend with LangChain and LangGraph orchestration
- A Vue 3 frontend for agent, workflow, dataset, tool, and conversation management
- Celery workers for background jobs
- PostgreSQL, Redis, Weaviate, and Nginx in the Docker stack

The current codebase focuses on:

- Multi-provider LLM integration
- Workflow authoring and execution
- Conversation management and search
- Public app and workflow publishing
- Knowledge base, document, and dataset management
- Built-in tools and notification pipelines

---

## Project Layout

```text
.
├── api/        # Flask backend, services, handlers, tasks, tests
├── ui/         # Vue 3 frontend, components, views, tests
├── docker/     # Docker Compose stack and deployment config
├── docs/       # High-level documentation index and deployment guides
└── README.md   # Project overview
```

---

## Features

### Backend

- REST APIs built with Flask
- Service-oriented backend structure
- JWT, OAuth, and role-based account flows
- SSE / websocket driven real-time notifications
- Celery-based background tasks

### Frontend

- Vue 3 + Vite + TypeScript
- Workflow editor and app management views
- Conversation history, search, and publishing pages
- Notification components and live UI updates

### Infrastructure

- Docker Compose deployment
- PostgreSQL for persistence
- Redis for cache and task queue
- Weaviate for vector search
- Nginx as reverse proxy

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (Vue 3)                     │
│  Agent Builder  Workflow Editor  Dataset Manager  Tools UI   │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP / SSE / WebSocket
┌─────────────────────────────────────────────────────────────┐
│                      Backend (Flask + Celery)                │
│  API Layer   Services   LangChain / LangGraph   Background   │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure                            │
│  PostgreSQL   Redis   Weaviate   Nginx                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 8GB+ RAM recommended for the full stack

### Start with Docker

```bash
git clone https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git
cd LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents

cp api/.env.example api/.env
# edit api/.env and fill in the required API keys

cd docker
docker compose up -d --build
```

### Service URLs

| Service | URL | Notes |
|---|---|---|
| Frontend | http://localhost:3000 | Vue 3 web UI |
| API | http://localhost:5001 | Flask REST API |
| Nginx | http://localhost | Reverse proxy |

For more deployment details, see [DOCKER_QUICKSTART.md](DOCKER_QUICKSTART.md) and [docker/README.md](docker/README.md).

---

## Local Development

### Backend

```bash
cd api
pip install -r requirements.txt
flask run --port 5001
```

Run tests:

```bash
cd api
pytest
```

### Frontend

```bash
cd ui
npm install
npm run serve
```

Vite serves the frontend on port `5173` by default and proxies `/api` to `http://localhost:5001`.

Useful frontend commands:

```bash
cd ui
npm run type-check
npm run lint
npm run build
npm run test:unit -- --run
```

---

## Configuration

### Backend environment

Copy `api/.env.example` to `api/.env` and set at least one LLM provider key plus the required database and Redis settings.

### Docker environment

If you need to customize ports, container passwords, or other infrastructure settings, use the Docker configuration documented in [docker/README.md](docker/README.md).

### Key references

- [api/.env.example](api/.env.example)
- [docker/README.md](docker/README.md)
- [docker/SECURITY.md](docker/SECURITY.md)
- [CLAUDE.md](CLAUDE.md)

---

## Documentation

- [docs/deployment/DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md) - deployment guide
- [docs/deployment/QUICKSTART_GUIDE.md](docs/deployment/QUICKSTART_GUIDE.md) - quick start guide
- [api/README.md](api/README.md) - backend notes
- [ui/README.md](ui/README.md) - frontend notes
- [docker/README.md](docker/README.md) - Docker setup
- [docker/SECURITY.md](docker/SECURITY.md) - security guidance

---

## Testing

The repository already includes a large automated test suite.

- Backend: `cd api && pytest`
- Frontend: `cd ui && npm run test:unit -- --run`

---

## License

License terms are not declared in a root `LICENSE` file at the moment. Add one if you want the licensing to be explicit.
