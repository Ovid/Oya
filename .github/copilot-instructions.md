# Copilot instructions (Oya)

Trust this file as the source of truth; only search the repo when details are missing here or need verification.

## Repo summary
- Oya is a local-first, editable wiki generator for codebases with a FastAPI backend and React/Vite frontend.
- Data stored under `~/.oya` (override with `OYA_DATA_DIR`), including repo registry and generated wiki artifacts.

## High-level info
- Languages: Python (backend), TypeScript/React (frontend), Docker, Makefile.
- Frameworks/tooling: FastAPI, Uvicorn, ChromaDB, LiteLLM, Tree-sitter; React 19, Vite 7, Vitest, Tailwind.
- Runtimes: Python 3.11+ (repo requirement), Node.js 20+ (frontend).
- Repo size: ~358 tracked files; working dir ~1.2G (includes node_modules, venv).

## Layout & architecture
- Backend entry: `/home/runner/work/Oya/Oya/backend/src/oya/main.py` (FastAPI app + routers).
- Backend config: `/home/runner/work/Oya/Oya/backend/src/oya/config.py` (CONFIG_SCHEMA, defaults).
- Backend routers: `/home/runner/work/Oya/Oya/backend/src/oya/api/routers/`.
- Generation pipeline: `/home/runner/work/Oya/Oya/backend/src/oya/generation/`.
- Repo management: `/home/runner/work/Oya/Oya/backend/src/oya/repo/`.
- Frontend app: `/home/runner/work/Oya/Oya/frontend/src/` (React components, Zustand stores).
- Frontend entry: `/home/runner/work/Oya/Oya/frontend/src/main.tsx`.
- Config files: `/home/runner/work/Oya/Oya/config.ini.example`, `/home/runner/work/Oya/Oya/.env.example`.
- Docs: `/home/runner/work/Oya/Oya/README.md`, `/home/runner/work/Oya/Oya/SETUP.md`, `/home/runner/work/Oya/Oya/CONTRIBUTING.md`, `/home/runner/work/Oya/Oya/docs/`.
- Docker: `/home/runner/work/Oya/Oya/docker-compose.yml`, `/home/runner/work/Oya/Oya/backend/Dockerfile`, `/home/runner/work/Oya/Oya/frontend/Dockerfile`.

## Root files & key directories
- Root files: `README.md`, `SETUP.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `LICENSE`, `Makefile`, `docker-compose.yml`, `.env.example`, `config.ini.example`, `.pre-commit-config.yaml`, `CLAUDE.md`, `TODO.md`
- Key dirs: `backend/`, `frontend/`, `docs/`, `images/`, `prds/`

## Dependencies
- Backend deps: `/home/runner/work/Oya/Oya/backend/pyproject.toml` (FastAPI, ChromaDB, LiteLLM, Tree-sitter, etc.).
- Frontend deps: `/home/runner/work/Oya/Oya/frontend/package.json` (React, Vite, Vitest, Tailwind, ESLint).

## Build/test/run/lint (validated commands run here)

### Versions (observed)
- Python 3.12.3 (`python3 --version`); `python3.11` not installed in this env.
- Node v20.20.0, npm 10.8.2.

### Backend (Python)
- Bootstrap venv + deps + checks:
  - `cd /home/runner/work/Oya/Oya/backend && python3 -m venv .venv`
  - `cd /home/runner/work/Oya/Oya/backend && source .venv/bin/activate && pip install -e ".[dev]"`
  - `cd /home/runner/work/Oya/Oya/backend && source .venv/bin/activate && ruff check src/ tests/`
  - `cd /home/runner/work/Oya/Oya/backend && source .venv/bin/activate && ruff format --check src/ tests/`
  - `cd /home/runner/work/Oya/Oya/backend && source .venv/bin/activate && mypy src/oya`
  - `cd /home/runner/work/Oya/Oya/backend && source .venv/bin/activate && ulimit -n 4096 && pytest tests/`
- Observed failure: `pytest` fails in this environment because ChromaDB tries to download ONNX embeddings (no network). Tests failing include `tests/test_indexing.py`, `tests/test_issues_store.py`, `tests/test_rag_integration.py`, `tests/test_vectorstore.py` with `httpx.ConnectError` during embedding download.

### Frontend (TypeScript)
- Install/build/lint/test:
  - `cd /home/runner/work/Oya/Oya/frontend && npm install`
  - `cd /home/runner/work/Oya/Oya/frontend && npm run build`
  - `cd /home/runner/work/Oya/Oya/frontend && npm run lint`
  - `cd /home/runner/work/Oya/Oya/frontend && npm run test`

### Run dev servers (validated)
- Backend: `cd /home/runner/work/Oya/Oya/backend && source .venv/bin/activate && uvicorn oya.main:app --port 8000` (health check: `curl -s http://127.0.0.1:8000/health`).
- Frontend: `cd /home/runner/work/Oya/Oya/frontend && npm run dev -- --host 127.0.0.1 --port 5173` (HTTP 200 from `http://127.0.0.1:5173/`).

### Docker
- `cd /home/runner/work/Oya/Oya && docker-compose up` (per `/home/runner/work/Oya/Oya/SETUP.md`).

### Makefile shortcuts (not run here)
- `cd /home/runner/work/Oya/Oya && make install`, `make dev`, `make test`, `make lint`, `make format`, `make format-check`, `make typecheck`, `make all`, `make ci`.

## CI / Workflows
- No `.github/workflows` directory in this repo snapshot.
- GitHub Actions runs observed via MCP are Copilot workflows. Latest run (ID `21331879756`, workflow "Running Copilot coding agent") is in progress. Attempt to fetch job logs for job `61397856873` returned 404; logs unavailable.

## Workarounds / errors observed
- Backend tests fail offline when ChromaDB tries to download embeddings (HTTPX ConnectError). Run tests with network access or pre-cache embeddings.
- Initial backend setup failed until `.venv` was created; the repo docs expect `python3.11` but this env only has `python3` (3.12.3).

## Notes for copilots
- Follow `SETUP.md` for full bootstrap and environment variables.
- Respect config rules in `CONTRIBUTING.md` (no hardcoded config; add to CONFIG_SCHEMA and `config.ini.example`).
