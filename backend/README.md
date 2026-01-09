# Oya Backend

Local-first editable wiki generator for codebases.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Setup

```bash
# Install dependencies
uv sync

# Install dev dependencies
uv sync --dev
```

## Configuration

Set environment variables or create a `.env` file:

```bash
# Required
WORKSPACE_PATH=/path/to/your/repository

# LLM Provider (auto-detected from API keys if not set)
ACTIVE_PROVIDER=openai    # openai | anthropic | google | ollama
ACTIVE_MODEL=gpt-4o       # Model identifier for the provider

# API Keys (set the one for your provider)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...

# Ollama (for local models)
OLLAMA_ENDPOINT=http://localhost:11434

# Optional
MAX_FILE_SIZE_KB=1024           # Max file size to process (default: 1024)
PARALLEL_FILE_LIMIT=10          # Parallel LLM calls (auto: 2 for Ollama, 10 for cloud)
CHUNK_SIZE=4096                 # Chunk size for text processing
```

### Provider Auto-Detection

If `ACTIVE_PROVIDER` is not set, Oya detects the provider from available API keys:
1. `OPENAI_API_KEY` → openai (gpt-4o)
2. `ANTHROPIC_API_KEY` → anthropic (claude-3-5-sonnet)
3. `GOOGLE_API_KEY` → google (gemini-1.5-pro)
4. None → ollama (llama2)

### Parallel Processing

The `PARALLEL_FILE_LIMIT` controls concurrent LLM calls during wiki generation:
- **Cloud APIs** (OpenAI, Anthropic, Google): defaults to 10
- **Ollama** (local models): defaults to 2 (prevents CPU/GPU overload)

Set explicitly to override: `PARALLEL_FILE_LIMIT=5`

## Running

```bash
# Development server
uv run uvicorn oya.main:app --reload --port 8000

# Production
uv run uvicorn oya.main:app --host 0.0.0.0 --port 8000
```

## Testing

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_config.py

# Run with coverage
uv run pytest --cov=oya
```

## Project Structure

```
backend/
├── src/oya/
│   ├── api/              # FastAPI routers and schemas
│   │   ├── routers/      # API endpoints (repos, wiki, search, notes, jobs, qa)
│   │   ├── deps.py       # Dependency injection
│   │   └── schemas.py    # Pydantic models
│   ├── db/               # Database layer
│   │   ├── connection.py # SQLite connection management
│   │   └── migrations.py # Schema definitions
│   ├── generation/       # Wiki generation pipeline
│   │   ├── orchestrator.py  # Main pipeline coordinator
│   │   ├── file.py          # File documentation generator
│   │   ├── directory.py     # Directory documentation generator
│   │   ├── architecture.py  # Architecture page generator
│   │   ├── overview.py      # Overview page generator
│   │   ├── synthesis.py     # Synthesis map generator
│   │   ├── workflows.py     # Workflow documentation generator
│   │   ├── summaries.py     # Summary data models
│   │   ├── prompts.py       # LLM prompt templates
│   │   └── chunking.py      # Text chunking utilities
│   ├── llm/              # LLM client abstraction
│   │   └── client.py     # Multi-provider LLM client (via LiteLLM)
│   ├── notes/            # User corrections/notes
│   │   ├── service.py    # Notes CRUD operations
│   │   └── schemas.py    # Note models
│   ├── parsing/          # Code parsing (tree-sitter)
│   │   ├── registry.py      # Parser registry
│   │   ├── python_parser.py
│   │   ├── typescript_parser.py
│   │   ├── java_parser.py
│   │   └── fallback_parser.py
│   ├── qa/               # Question answering
│   │   └── service.py    # RAG-based Q&A
│   ├── repo/             # Repository handling
│   │   ├── git_repo.py   # Git operations
│   │   └── file_filter.py # File inclusion/exclusion
│   ├── vectorstore/      # Vector embeddings
│   │   └── store.py      # ChromaDB integration
│   ├── config.py         # Configuration management
│   └── main.py           # FastAPI application entry
└── tests/                # Test suite
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/repos/status` | Get repository status |
| POST | `/api/repos/init` | Initialize wiki generation |
| GET | `/api/jobs/{job_id}` | Get generation job status |
| GET | `/api/wiki/tree` | Get wiki page tree |
| GET | `/api/wiki/pages/{path}` | Get wiki page content |
| GET | `/api/search` | Search wiki pages |
| GET | `/api/notes` | List user notes |
| POST | `/api/notes` | Create a note |
| PUT | `/api/notes/{id}` | Update a note |
| DELETE | `/api/notes/{id}` | Delete a note |
| POST | `/api/qa/ask` | Ask a question about the codebase |

## Generation Pipeline

The wiki generation follows a bottom-up approach:

1. **Analysis** - Scan repository, identify files to process
2. **Files** - Generate documentation for each source file
3. **Directories** - Generate documentation for each directory
4. **Synthesis** - Build a codebase understanding map
5. **Architecture** - Generate architecture documentation
6. **Overview** - Generate project overview
7. **Workflows** - Generate workflow documentation

Each phase extracts structured summaries that inform subsequent phases, ensuring high-quality documentation even without a README.

## Data Storage

All generated data is stored in `.oyawiki/` within the workspace:

```
.oyawiki/
├── wiki/           # Generated markdown documentation
├── notes/          # User corrections and notes
└── meta/
    ├── oya.db      # SQLite database (pages, notes, jobs)
    ├── chroma/     # ChromaDB vector store
    ├── index/      # Search index
    └── cache/      # Processing cache
```
