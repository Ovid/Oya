# Setup Guide

This guide covers how to run Ọya locally, both with and without Docker.

## Prerequisites

### LLM Provider (Required)

Ọya requires access to an LLM. Choose one:

| Provider | API Key Variable | Example Model |
|----------|-----------------|---------------|
| OpenAI | `OPENAI_API_KEY` | gpt-4o |
| Anthropic | `ANTHROPIC_API_KEY` | claude-3-5-sonnet-20241022 |
| Google | `GOOGLE_API_KEY` | gemini-1.5-pro |
| Ollama | None (local) | llama2, codellama |

### System Requirements

- **Git**: Required for cloning repositories
- **Docker** (optional): For containerized setup

---

## Quick Start with Docker

The fastest way to get started.

```bash
# 1. Clone the repository
git clone https://github.com/your-org/oya.git
cd oya

# 2. Configure environment
cp .env.example .env
# Edit .env and add your LLM API key

# 3. Start services
docker-compose up

# 4. Open http://localhost:5173
```

### Docker Environment Variables

Add to your `.env` file:

```bash
# Pick one LLM provider:
OPENAI_API_KEY=sk-...
# OR
ANTHROPIC_API_KEY=sk-ant-...
# OR
GOOGLE_API_KEY=...
# OR (for local Ollama)
ACTIVE_PROVIDER=ollama
ACTIVE_MODEL=llama2
OLLAMA_ENDPOINT=http://host.docker.internal:11434
```

### Docker Notes

- Backend runs on port 8000
- Frontend runs on port 5173
- Data persists to `~/.oya` on your host machine
- For private repos, SSH keys are mounted from `~/.ssh`

---

## Local Development Setup (No Docker)

### Backend Setup

**Requirements:**
- Python 3.11+
- Git

**Installation:**

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

**Run the server:**

```bash
uvicorn oya.main:app --reload --port 8000
```

The API will be available at http://localhost:8000

### Frontend Setup

**Requirements:**
- Node.js 20+

**Installation:**

```bash
cd frontend

# Install dependencies
npm install
```

**Run the dev server:**

```bash
npm run dev
```

The UI will be available at http://localhost:5173

### Using the Makefile

For convenience, run both services together:

```bash
# Install all dependencies (backend + frontend)
make install

# Start both dev servers
make dev
```

---

## Environment Configuration

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

### Required: LLM Provider

Configure at least one provider:

```bash
# OpenAI
OPENAI_API_KEY=sk-...
ACTIVE_PROVIDER=openai
ACTIVE_MODEL=gpt-4o

# OR Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ACTIVE_PROVIDER=anthropic
ACTIVE_MODEL=claude-3-5-sonnet-20241022

# OR Google
GOOGLE_API_KEY=...
ACTIVE_PROVIDER=google
ACTIVE_MODEL=gemini-1.5-pro

# OR Ollama (local)
ACTIVE_PROVIDER=ollama
ACTIVE_MODEL=llama2
OLLAMA_ENDPOINT=http://localhost:11434
```

If you set multiple API keys, Ọya auto-detects which to use. You can override with `ACTIVE_PROVIDER` and `ACTIVE_MODEL`.

### Optional: Data Directory

```bash
# Default: ~/.oya
OYA_DATA_DIR=/path/to/custom/location
```

### Optional: Performance Tuning

```bash
MAX_FILE_SIZE_KB=1024      # Max file size to process (default: 500)
PARALLEL_FILE_LIMIT=10     # Concurrent LLM calls (default: 2 for Ollama, 10 for cloud)
```

---

## Data Storage

All data is stored locally under `~/.oya` (or `OYA_DATA_DIR`):

```
~/.oya/
├── repos.db                 # Repository registry
└── wikis/
    └── {repo-name}/
        ├── source/          # Git clone
        └── meta/
            ├── wiki/        # Generated documentation
            ├── notes/       # User corrections
            ├── oya.db       # Repo metadata
            ├── chroma/      # Vector embeddings
            └── cache/       # Processing cache
```

No external databases required - SQLite and ChromaDB are embedded.

---

## Running Tests

### Backend Tests

```bash
cd backend
source .venv/bin/activate

pytest                      # All tests
pytest tests/test_qa_api.py # Single file
pytest -k "test_name"       # Pattern match
pytest --cov=src/oya        # With coverage
```

### Frontend Tests

```bash
cd frontend

npm run test           # Run once
npm run test:watch     # Watch mode
npm run test:coverage  # With coverage
```

### All Tests via Makefile

```bash
make test              # Run all tests
make cover             # Tests with coverage
```

---

## Code Quality

### Linting

```bash
# All linting
make lint

# Backend only
cd backend && ruff check .

# Frontend only
cd frontend && npm run lint
```

### Formatting

```bash
# Auto-format everything
make format

# Check formatting without changes
make format-check
```

### Type Checking

```bash
# Backend
cd backend && mypy src

# Frontend
cd frontend && npm run build  # Includes type check
```

---

## Troubleshooting

### Port already in use

If port 8000 or 5173 is busy:

```bash
# Backend: use different port
uvicorn oya.main:app --reload --port 8001

# Frontend: Vite picks next available port automatically
```

### Ollama connection issues (Docker)

When running Ọya in Docker with Ollama on your host:

```bash
# In .env
OLLAMA_ENDPOINT=http://host.docker.internal:11434
```

### File descriptor limit (macOS)

If tests fail with "too many open files":

```bash
ulimit -n 4096
```

### Clear generated data

To reset a repository's wiki:

```bash
rm -rf ~/.oya/wikis/{repo-name}/meta/wiki
```

To reset everything:

```bash
rm -rf ~/.oya
```

---

## Next Steps

1. Open http://localhost:5173
2. Add a repository (local path or git URL)
3. Click "Generate" to create documentation
4. Use the Q&A feature to ask questions about the code
