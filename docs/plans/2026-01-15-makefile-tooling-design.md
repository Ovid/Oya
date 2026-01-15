# Makefile Development Tooling Design

## Overview

Add a unified Makefile for running quality checks, tests, coverage, and development servers across the Oya monorepo (Python backend + React/TypeScript frontend).

## Target Structure

### Combined Targets (run both services)

| Target | Description |
|--------|-------------|
| `make test` | Run all tests |
| `make lint` | Check for linting issues |
| `make format` | Auto-fix formatting (modifies files) |
| `make format-check` | Verify formatting without changes |
| `make typecheck` | Run type checkers (mypy + tsc) |
| `make cover` | Run tests with coverage reports |
| `make all` | lint + format-check + typecheck + test |
| `make ci` | all + cover (for CI pipelines) |
| `make dev` | Start backend and frontend dev servers |
| `make install` | Install all dependencies |
| `make clean` | Remove generated files |
| `make help` | Show available targets and workflows |

### Per-Service Targets

Append `-backend` or `-frontend` for granular control:

- `test-backend`, `test-frontend`
- `lint-backend`, `lint-frontend`
- `format-backend`, `format-frontend`
- `format-check-backend`, `format-check-frontend`
- `typecheck-backend`, `typecheck-frontend`
- `cover-backend`, `cover-frontend`
- `install-backend`, `install-frontend`
- `dev-backend`, `dev-frontend`

Combined targets depend on both per-service targets.

## Dependency Changes

### Backend (pyproject.toml)

Add to dev dependencies:
- `mypy` - Python type checker
- `pytest-cov` - Coverage for pytest

### Frontend (package.json)

Add to devDependencies:
- `@vitest/coverage-v8` - Vitest coverage provider
- `prettier` - Code formatter

Add npm scripts:
- `format` - Run prettier to fix files
- `format:check` - Run prettier in check mode

## Tool Configuration

### Backend

**mypy** (in pyproject.toml):
- `strict_optional = true`
- `ignore_missing_imports = true` (for third-party libs without stubs)
- Target Python 3.11

**pytest-cov**:
- HTML output to `backend/htmlcov/`
- Terminal summary on test runs

### Frontend

**Prettier** (.prettierrc):
- Single quotes (match existing code style)
- Trailing commas
- 2-space indent

**Prettier ignore** (.prettierignore):
- `dist/`
- `node_modules/`
- `coverage/`

**Vitest coverage** (vite.config.ts):
- HTML output to `frontend/coverage/`
- Provider: v8

### Makefile Conventions

- All targets are `.PHONY` (none produce files)
- Backend commands: run from `backend/` with venv activated
- Frontend commands: run from `frontend/` with npx
- Combined targets fail fast on first error

## Files to Create

1. `Makefile` (~120 lines)
2. `frontend/.prettierrc`
3. `frontend/.prettierignore`

## Files to Modify

1. `backend/pyproject.toml` - add deps, mypy config, coverage config
2. `frontend/package.json` - add deps, format scripts
3. `frontend/vite.config.ts` - add coverage config
4. `.gitignore` - add coverage dirs, .mypy_cache

## Help Output

```
Oya Development Commands
========================

Quality Checks:
  make test              Run all tests
  make lint              Check for linting issues
  make format            Auto-fix formatting (modifies files)
  make format-check      Verify formatting without changes
  make typecheck         Run type checkers (mypy + tsc)
  make cover             Run tests with coverage reports

Combined:
  make all               Run lint + format-check + typecheck + test
  make ci                Run all + cover (for CI pipelines)

Development:
  make dev               Start backend and frontend dev servers
  make install           Install all dependencies
  make clean             Remove generated files (coverage, cache)

Per-Service (append -backend or -frontend):
  make test-backend      make test-frontend
  make lint-backend      make lint-frontend
  make format-backend    make format-frontend
  make cover-backend     make cover-frontend
  ...

Workflows:
  make install && make all    First-time setup and verify
  make format && make all     Fix formatting then verify
  make cover-backend          Check coverage for just backend
  make dev-frontend           Work on frontend only
```
