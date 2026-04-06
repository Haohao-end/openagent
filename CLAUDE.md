# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an LLMOps platform like dify featuring a Python Flask backend (API) and a Vue 3 frontend (UI) styled with TailwindCSS. The platform integrates Celery for distributed task processing, LangChain and LangGraph for LLM orchestration, Weaviate as the vector database, and Redis for caching and message brokering, enabling comprehensive development and management of AI Agent applications.

## Architecture

### Backend (api/)

**Core Structure:**
- `app/http/` - Flask application entry point and dependency injection setup
- `internal/` - Main application logic organized by layers:
  - `handler/` - HTTP request handlers (controllers)
  - `service/` - Business logic layer
  - `model/` - SQLAlchemy database models
  - `schema/` - Marshmallow schemas for request/response validation
  - `entity/` - Domain entities and data transfer objects
  - `router/` - URL routing configuration
  - `middleware/` - Request/response middleware
  - `core/` - Core LLM functionality:
    - `agent/` - LangGraph-based agent implementations
    - `workflow/` - Workflow execution engine with node system
    - `language_model/` - LLM provider integrations (OpenAI, Anthropic, DeepSeek, etc.)
    - `tools/` - Built-in and API tools for agents
    - `builtin_apps/` - Pre-built application templates
    - `retrievers/` - RAG retrieval implementations
    - `vector_store/` - Vector database abstractions
    - `file_extractor/` - Document parsing (unstructured library)
    - `memory/` - Conversation memory management
  - `migration/` - Alembic database migrations
  - `task/` - Celery background tasks
  - `extension/` - Flask extensions (logging, Redis, Celery)
- `pkg/` - Reusable packages and utilities
- `config/` - Configuration management
- `test/` - Test suite with pytest

**Key Technologies:**
- Flask 3.1 with Flask-SQLAlchemy, Flask-Login, Flask-Migrate
- LangChain ecosystem (langchain_core, langchain_community, langgraph)
- PostgreSQL (via psycopg2-binary) + Redis + Weaviate (vector DB)
- Celery for async tasks
- Multiple LLM providers via langchain integrations

**Dependency Injection:**
Uses Python `injector` library. All services, handlers, and infrastructure components are registered in `app/http/module.py` and injected via constructor parameters.

### Frontend (ui/)

**Core Structure:**
- `src/views/` - Page components organized by feature:
  - `space/` - Main workspace (apps, datasets, workflows, tools)
  - `auth/` - Authentication pages
  - `web-apps/` - Public-facing app interfaces
  - `openapi/` - OpenAPI integration views
  - `layouts/` - Layout components
- `src/components/` - Reusable Vue components
- `src/services/` - API client services
- `src/stores/` - Pinia state management
- `src/router/` - Vue Router configuration
- `src/models/` - TypeScript type definitions
- `src/utils/` - Utility functions
- `src/hooks/` - Vue composition API hooks

**Key Technologies:**
- Vue 3.4 with Composition API
- TypeScript (strict mode disabled)
- Vite 5 for build tooling
- Pinia for state management
- Arco Design Vue UI library
- Vue Flow for workflow visualization
- ECharts for analytics
- Vitest for unit testing

## Development Commands

### Backend (api/)

**Setup:**
```bash
cd api
pip install -r requirements.txt
```

**Database migrations:**
```bash
# Create migration
flask db migrate -m "description"

# Apply migrations
flask db upgrade

# Rollback
flask db downgrade
```

**Run development server:**
```bash
# Set environment variables in .env file first
python app/http/app.py
# Or use Flask CLI:
flask run --port 5001
```

**Testing:**
```bash
# Run all tests with coverage (enforces 100% coverage on handler/service)
pytest

# Run specific test file
pytest test/internal/service/test_account_service.py

# Run with verbose output
pytest -v -s

# Coverage is stored in tmp/coverage.xml
# Cache is stored in tmp/.pytest_cache
```

**Celery worker:**
```bash
celery -A app.http.app:celery worker --loglevel=info
```

### Frontend (ui/)

**Setup:**

bash

```
cd ui
npm install
```



**Development:**

bash

```
# Start dev server (default port 5173)
npm run serve

# Type checking
npm run type-check

# Linting
npm run lint

# Format code
npm run format
```



**Build:**

bash

```
# Production build
npm run build

# Preview production build
npm run preview
```



**Testing:**

bash

```
# Run unit tests
npm run test:unit
```

### Docker Infrastructure

**Start services:**
```bash
cd docker
docker-compose up -d
```

Services:
- PostgreSQL: localhost:5432 (user: postgres, password: llmops123456, db: llmops)
- Redis: localhost:6379 (password: llmops123456)
- Weaviate: localhost:8080 (API key: ftBC9hKkjfdbdi0W3T6kEtMh5BZFpGa1DF8)

## Key Patterns

### Backend Service Layer Pattern

Services follow a consistent pattern:
1. Handler receives request → validates with schema
2. Handler calls service method
3. Service contains business logic → calls models/external APIs
4. Service returns entity/data
5. Handler serializes response with schema

Example flow: `AppHandler.create_app()` → `AppService.create_app()` → `App.create()` model method

### Workflow System

Workflows are DAG-based with nodes in `internal/core/workflow/nodes/`:
- Each node type (LLM, Tool, Knowledge Retrieval, etc.) implements `run()` method
- Nodes are connected via edges defining execution flow
- Workflow execution is managed by `Workflow` class in `internal/core/workflow/workflow.py`
- Node configurations stored in app config JSON

### Agent System

Agents use LangGraph for state management:
- Agent definitions in `internal/core/agent/agents/`
- Agents can use tools, memory, and retrieval
- Assistant agent (`ASSISTANT_AGENT_ID` in .env) provides help within the platform

### Vector Database Integration

- Weaviate is the primary vector store
- Dataset documents are chunked and embedded
- Segments stored with metadata for retrieval
- Integration via `flask_weaviate` and `langchain_weaviate`

## Configuration

### Backend Environment Variables

Key variables in `api/.env` (see `.env.example`):
- Database: `SQLALCHEMY_DATABASE_URI`
- Redis: `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD`
- Weaviate: `WEAVIATE_HTTP_HOST`, `WEAVIATE_HTTP_PORT`
- LLM providers: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPSEEK_API_KEY`, etc.
- OAuth: `GITHUB_CLIENT_ID`, `GOOGLE_CLIENT_ID`
- Storage: `COS_*` for Tencent Cloud COS

### Frontend Environment Variables

Variables in `ui/.env`:
- API endpoint configuration
- OAuth redirect URIs

## Testing Guidelines

### Backend Tests

- Tests mirror source structure: `test/internal/service/` matches `internal/service/`
- Use pytest fixtures defined in `conftest.py`
- Coverage requirement: 100% branch coverage for `internal/handler` and `internal/service`
- Coverage config in `pytest.ini`
- Mock external dependencies (LLM APIs, vector DB, etc.)

### Frontend Tests

- Unit tests with Vitest
- Test files colocated with components or in `__tests__` directories
- Use Vue Test Utils for component testing

## Important Notes

- **Timezone:** Backend uses UTC internally, converts to Asia/Shanghai for display
- **Datetime deprecation:** Tests enforce no usage of `datetime.utcnow()` or `utcfromtimestamp()`
- **Dependency injection:** All services must be registered in `app/http/module.py`
- **Database sessions:** Use Flask-SQLAlchemy session management, avoid manual session handling
- **API versioning:** No explicit versioning currently, all routes under root prefix
- **CORS:** Enabled for all origins in development
- **File uploads:** Handled via `UploadFileService`, stored in COS or local storage
- **Background tasks:** Long-running operations (document indexing, etc.) use Celery
- **LLM streaming:** Supported via SSE (Server-Sent Events) for real-time responses
