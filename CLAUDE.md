# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ọya is a local-first, editable wiki generator for codebases. It uses LLMs to generate documentation from source code and stores everything in `.oyawiki/` within the target repository.

IMPORTANT: this is a generic repository analysis tool. DO NOT MAKE ASSUMPTIONS ABOUT THE CODEBASE BEING ANALYZED. For example, we often use Oya to analyze itself and you often create designs assuming the same tech stack as Oya. THIS IS AN ERROR. Do not make assumptions about the programming languages, frameworks, tools, etc. These must be discovered, not assumed.

## Development Commands

### Backend (Python/FastAPI)

```bash
cd backend
source .venv/bin/activate  # Uses existing venv
pip install -e ".[dev]"    # Install with dev dependencies

# Run server (requires WORKSPACE_PATH env var)
export WORKSPACE_PATH=/path/to/repo
uvicorn oya.main:app --reload

# Run tests
pytest                      # All tests
pytest tests/test_qa_api.py # Single file
pytest -k "test_name"       # By name pattern
```

### Frontend (React/TypeScript/Vite)

```bash
cd frontend
npm install
npm run dev      # Dev server on :5173
npm run build    # TypeScript check + Vite build
npm run lint     # ESLint
npm run test     # Vitest (run once)
npm run test:watch  # Vitest (watch mode)
```

### Docker

```bash
docker-compose up  # Runs both services
```

## Architecture

### Backend Structure (`backend/src/oya/`)

- **api/routers/**: FastAPI endpoints (repos, wiki, jobs, search, qa, notes)
- **generation/**: Wiki generation pipeline
  - `orchestrator.py`: Main generation coordinator - handles the full pipeline
  - `prompts.py`: All LLM prompt templates
  - `synthesis.py`: Combines parsed code into documentation
  - `summaries.py`: Hierarchical code summarization
  - `staging.py`: Atomic wiki updates via staging directory
- **llm/**: LiteLLM-based client supporting OpenAI, Anthropic, Google, Ollama
- **parsing/**: Tree-sitter based code parsers (Python, TypeScript, Java, fallback)
- **vectorstore/**: ChromaDB for semantic search and Q&A
- **db/**: SQLite for job tracking and metadata
- **notes/**: Human correction system

### Frontend Structure (`frontend/src/`)

- **components/**: React components
  - `Layout.tsx`, `Sidebar.tsx`, `TopBar.tsx`: Shell UI
  - `GenerationProgress.tsx`: Real-time job progress via SSE
  - `IndexingPreviewModal.tsx`: File selection before generation
  - `QADock.tsx`: Q&A interface
  - `pages/`: Route components (Overview, Architecture, Workflow, Directory, File)
- **context/AppContext.tsx**: Global state (repo status, wiki tree, generation jobs)
- **api/**: Typed API client functions

### Data Flow

1. User triggers generation → `POST /api/repos/init`
2. Backend creates job, starts async generation via `orchestrator.py`
3. Progress streamed via SSE at `/api/jobs/{id}/stream`
4. Wiki written to `.oyawiki-building/` (staging), then atomically promoted to `.oyawiki/`
5. Frontend polls `/api/wiki/tree` and renders markdown pages

### Key Patterns

- **Settings**: Loaded via `config.py:load_settings()` from env vars, cached with `@lru_cache`
- **LLM calls**: All go through `llm/client.py`, logged to `.oya-logs/llm-queries.jsonl`
- **Tests**: pytest with `asyncio_mode = "auto"`, hypothesis for property testing
- **Staging**: Generation writes to `.oyawiki-building/`, promotes atomically on success

### Configuration Constants

Hard-coded values that control application behavior are extracted to config files for easier tuning and documentation.

**Backend:** Configuration is centralized in `backend/src/oya/config.py` with the `CONFIG_SCHEMA` dictionary defining all settings with defaults and validation. Access via `load_settings().section.property`:
- `settings.generation` - LLM temperatures, chunking parameters
- `settings.ask` - Q&A token budgets, confidence thresholds, CGRAG settings
- `settings.llm` - Default LLM client settings
- `settings.search` - Result limits, deduplication
- `settings.files` - File size limits, concurrency
- `settings.paths` - Directory names

**Frontend:** `frontend/src/config/`
- `layout.ts` - Panel dimensions, z-index layers
- `qa.ts` - Confidence level colors
- `storage.ts` - localStorage keys
- `timing.ts` - Polling intervals, relative time thresholds

## Environment Variables

Required: `WORKSPACE_PATH` - path to the repo being documented

LLM config (auto-detected from available keys):
- `ACTIVE_PROVIDER`: openai | anthropic | google | ollama
- `ACTIVE_MODEL`: Model name (has provider-specific defaults)
- Provider API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`
- `OLLAMA_ENDPOINT`: Defaults to `http://localhost:11434`

## Code Style

- Backend: Python 3.11+, ruff for linting, line length 100
- Frontend: TypeScript strict, ESLint, Tailwind CSS
