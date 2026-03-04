# 🚀 LLMOps - End-to-End LLM Operations Platform

<div align="center">

![AI Agent](https://github.com/user-attachments/assets/f4cad915-411e-4e0f-95bc-8f8afdcf1019)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/docker-20.10+-blue.svg)](https://www.docker.com/)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents)

[English](README.md) | [中文](README_ZH.md)

**🌐 Online Demo**: http://82.157.66.198/

**📚 Documentation**: https://deepwiki.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents

**📖 API Docs**: https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417

</div>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Architecture](#-architecture)
- [Quick Start](#-quick-start)
- [Deployment](#-deployment)
- [Configuration](#-configuration)
- [Documentation](#-documentation)
- [License](#-license)

---

## 🎯 Overview

**LLMOps** is a comprehensive platform for building, deploying, and managing AI Agent applications with multiple LLM providers. It features a Python Flask backend with LangChain/LangGraph orchestration and a Vue 3 frontend, enabling seamless development of intelligent agent workflows.

### 🌟 Key Highlights

- 🤖 **Multi-Agent System**: Build complex AI agents with LangGraph
- 🔄 **Visual Workflow Builder**: Drag-and-drop interface for workflow design
- 🧠 **Multi-LLM Support**: OpenAI, DeepSeek, Claude, Moonshot, Qianfan, and more
- 📊 **RAG Integration**: Weaviate vector database for knowledge retrieval
- 🔧 **Built-in Tools**: 20+ pre-built tools (search, weather, maps, etc.)
- 🔐 **Enterprise Security**: OAuth, JWT, role-based access control
- 📈 **Real-time Analytics**: Monitor agent performance and usage
- 🐳 **Docker Ready**: One-command deployment with Docker Compose

---

## ✨ Features

### 🤖 AI Agent Development

- **Function Call Agent**: Direct function invocation with LLM
- **ReAct Agent**: Reasoning and acting with tool integration
- **Custom Agents**: Build your own agent types
- **Agent Queue Management**: Handle concurrent agent requests

### 🔄 Workflow System

<img width="1920" height="959" alt="workflow" src="https://github.com/user-attachments/assets/26d6dd8f-03d2-4b45-8ae0-a9817771fa08" />

- **Visual Editor**: Drag-and-drop workflow builder
- **Node Types**: LLM, Tool, Knowledge Retrieval, Code Execution, If-Else
- **DAG Execution**: Directed acyclic graph workflow engine
- **Real-time Streaming**: SSE-based streaming responses

### 🧠 Knowledge Management

- **Dataset Management**: Upload and manage documents
- **Vector Storage**: Weaviate integration for semantic search
- **Multiple Formats**: PDF, DOCX, TXT, Markdown support
- **Chunking Strategies**: Configurable text splitting

### 🔧 Built-in Tools

- **Search**: Google Serper, SerpAPI, Tavily AI
- **Weather**: OpenWeatherMap
- **Maps**: Gaode Maps API
- **News**: News API
- **Computation**: Wolfram Alpha
- **Code**: GitHub integration
- **Image Generation**: Stability AI
- **Custom Tools**: API-based tool integration

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend (Vue 3)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Agent   │  │ Workflow │  │ Dataset  │  │  Tools   │   │
│  │  Builder │  │  Editor  │  │ Manager  │  │ Manager  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ↕ HTTP/SSE
┌─────────────────────────────────────────────────────────────┐
│                      Backend (Flask + Celery)                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              API Layer (Flask)                        │  │
│  │  Handler → Service → Model → Database                │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Core Engine (LangChain/LangGraph)            │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │  │
│  │  │  Agent   │  │ Workflow │  │   RAG    │          │  │
│  │  │  Engine  │  │  Engine  │  │  Engine  │          │  │
│  │  └──────────┘  └──────────┘  └──────────┘          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Background Tasks (Celery)                     │  │
│  │  Document Indexing, Email Sending, etc.              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            ↕
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │PostgreSQL│  │  Redis   │  │ Weaviate │  │  Nginx   │   │
│  │    DB    │  │  Cache   │  │ VectorDB │  │  Proxy   │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- 8GB+ RAM recommended

### One-Command Deployment

```bash
# Clone repository
git clone https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents.git
cd LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents

# Configure environment variables
cp api/.env.example api/.env
vim api/.env  # Fill in your API keys

# Start services
cd docker
bash start.sh
```

### Access Services

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | Vue 3 Web UI |
| API | http://localhost:5001 | Flask REST API |
| Nginx | http://localhost | Reverse Proxy |

---

## 🐳 Deployment

### Server Deployment (One-Click)

```bash
# SSH to your server
ssh root@your-server-ip

# Run deployment script
bash <(curl -fsSL https://raw.githubusercontent.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/main/deploy-server.sh)
```

### Manual Deployment

See **[DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md)** for detailed instructions.

---

## ⚙️ Configuration

### Required Environment Variables

Create `api/.env` from `api/.env.example`:

```bash
# LLM Providers (Configure at least one)
OPENAI_API_KEY=sk-your-openai-key
DEEPSEEK_API_KEY=sk-your-deepseek-key
MOONSHOT_API_KEY=sk-your-moonshot-key

# Database (Auto-configured in Docker)
SQLALCHEMY_DATABASE_URI=postgresql://postgres:password@llmops-db:5432/llmops

# Redis (Auto-configured in Docker)
REDIS_HOST=llmops-redis
REDIS_PASSWORD=your-redis-password

# JWT Secret (Generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-random-secret-key
```

See **[docker/SECURITY.md](docker/SECURITY.md)** for security best practices.

---

## 📚 Documentation

### Core Documentation
- **[DEPLOYMENT.md](docs/deployment/DEPLOYMENT.md)** - Complete deployment guide
- **[QUICKSTART_GUIDE.md](docs/deployment/QUICKSTART_GUIDE.md)** - Quick start guide
- **[CLAUDE.md](CLAUDE.md)** - Project architecture for AI assistants
- **[API Documentation](https://s.apifox.cn/c76bd530-fd50-429c-94cc-f0e41c2675d1/api-305434417)** - REST API reference

### Docker & Infrastructure
- **[docker/README.md](docker/README.md)** - Docker configuration
- **[docker/SECURITY.md](docker/SECURITY.md)** - Security guidelines

### Development Guides
- **[AGENTS.md](docs/development/AGENTS.md)** - Agent development guide
- **[API Configuration](docs/development/API_CONFIG_SUMMARY.md)** - API configuration guide
- **[Frontend Guide](docs/development/FRONTEND_IMPLEMENTATION_GUIDE.md)** - Frontend development

### Feature Documentation
- **[Icon Generation](docs/features/ICON_GENERATION_COMPLETE_GUIDE.md)** - Icon generation system
- **[If-Else Workflow](docs/features/IF_ELSE_ARCHITECTURE.md)** - Conditional workflow nodes

### Testing & QA
- **[Test Guide](docs/testing/TEST_GUIDE.md)** - Testing guidelines
- **[Bug Reports](docs/bugfix/)** - Bug fix history

---

## 🛠️ Development

### Backend (Flask)

```bash
cd api
pip install -r requirements.txt
flask run --port 5001

# Run tests
pytest

# Run Celery worker
celery -A app.http.app:celery worker --loglevel=info
```

### Frontend (Vue 3)

```bash
cd ui
npm install
npm run serve

# Build for production
npm run build
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain) - LLM orchestration framework
- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent workflow engine
- [Weaviate](https://github.com/weaviate/weaviate) - Vector database
- [Vue 3](https://github.com/vuejs/core) - Progressive JavaScript framework
- [Flask](https://github.com/pallets/flask) - Python web framework

---

## 📞 Contact & Support

- **GitHub Issues**: [Report bugs or request features](https://github.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents/issues)
- **Documentation**: [DeepWiki](https://deepwiki.com/Haohao-end/LMForge-End-to-End-LLMOps-Platform-for-Multi-Model-Agents)
- **Online Demo**: http://82.157.66.198/

---

## 🔒 Security Acknowledgements

Special thanks to Rui Yang and Haoyu Wang (Johns Hopkins University) for responsibly reporting a Host Header poisoning issue in the built-in tool icon URL construction and helping improve the security of this project.

<div align="center">

**⭐ Star this repo if you find it helpful!**

Made with ❤️ by [Haohao-end](https://github.com/Haohao-end)

</div>
