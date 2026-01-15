# Makefile Development Tooling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a unified Makefile for quality checks, tests, coverage, and dev servers across the Oya monorepo.

**Architecture:** Root Makefile orchestrates backend (Python/ruff/mypy/pytest) and frontend (TypeScript/ESLint/Prettier/Vitest). Combined targets delegate to per-service targets. All quality tools already exist except mypy, pytest-cov, prettier, and vitest coverage.

**Tech Stack:** Make, ruff, mypy, pytest, pytest-cov, ESLint, Prettier, Vitest, @vitest/coverage-v8

---

### Task 1: Add Backend Dependencies

**Files:**
- Modify: `backend/pyproject.toml:20-27`

**Step 1: Add mypy and pytest-cov to dev dependencies**

Edit `backend/pyproject.toml`, change the `[project.optional-dependencies]` section:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.26.0",
    "ruff>=0.1.0",
    "hypothesis>=6.100.0",
    "mypy>=1.8.0",
    "pytest-cov>=4.1.0",
]
```

**Step 2: Add mypy configuration**

Append to `backend/pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_ignores = true
ignore_missing_imports = true
```

**Step 3: Add coverage configuration**

Append to `backend/pyproject.toml`:

```toml
[tool.coverage.run]
source = ["src/oya"]
omit = ["*/tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
]

[tool.coverage.html]
directory = "htmlcov"
```

**Step 4: Install updated dependencies**

Run:
```bash
cd backend && source .venv/bin/activate && pip install -e ".[dev]"
```

Expected: Successfully installs mypy and pytest-cov

**Step 5: Verify mypy works**

Run:
```bash
cd backend && source .venv/bin/activate && mypy src/oya --ignore-missing-imports
```

Expected: Runs without crashing (may show type errors - that's fine for now)

**Step 6: Verify pytest-cov works**

Run:
```bash
cd backend && source .venv/bin/activate && pytest --cov=src/oya --cov-report=term-missing tests/ -x -q 2>/dev/null | head -20
```

Expected: Shows coverage percentages for oya modules

**Step 7: Commit**

```bash
git add backend/pyproject.toml
git commit -m "feat(backend): add mypy and pytest-cov dev dependencies"
```

---

### Task 2: Add Frontend Dependencies

**Files:**
- Modify: `frontend/package.json:5-13` (scripts section)
- Modify: `frontend/package.json:23-47` (devDependencies)

**Step 1: Add prettier and coverage dependencies**

Edit `frontend/package.json` devDependencies to add:

```json
"@vitest/coverage-v8": "^4.0.0",
"prettier": "^3.2.0",
```

**Step 2: Add format scripts**

Edit `frontend/package.json` scripts section to become:

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "lint:fix": "eslint . --fix",
  "format": "prettier --write \"src/**/*.{ts,tsx,css}\"",
  "format:check": "prettier --check \"src/**/*.{ts,tsx,css}\"",
  "preview": "vite preview",
  "test": "vitest run",
  "test:watch": "vitest",
  "test:coverage": "vitest run --coverage"
},
```

**Step 3: Install dependencies**

Run:
```bash
cd frontend && npm install
```

Expected: Successfully installs prettier and @vitest/coverage-v8

**Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add prettier and vitest coverage dependencies"
```

---

### Task 3: Configure Prettier

**Files:**
- Create: `frontend/.prettierrc`
- Create: `frontend/.prettierignore`

**Step 1: Create Prettier config**

Create `frontend/.prettierrc`:

```json
{
  "semi": false,
  "singleQuote": true,
  "trailingComma": "es5",
  "tabWidth": 2,
  "printWidth": 100
}
```

**Step 2: Create Prettier ignore file**

Create `frontend/.prettierignore`:

```
dist/
node_modules/
coverage/
*.md
```

**Step 3: Verify prettier works**

Run:
```bash
cd frontend && npm run format:check
```

Expected: Either passes or shows files needing formatting (both are valid)

**Step 4: Commit**

```bash
git add frontend/.prettierrc frontend/.prettierignore
git commit -m "feat(frontend): add prettier configuration"
```

---

### Task 4: Configure Vitest Coverage

**Files:**
- Modify: `frontend/vite.config.ts`

**Step 1: Add coverage configuration**

Replace `frontend/vite.config.ts` with:

```typescript
/// <reference types="vitest" />
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/test/**', 'src/**/*.d.ts'],
    },
  },
})
```

**Step 2: Verify coverage works**

Run:
```bash
cd frontend && npm run test:coverage 2>&1 | head -30
```

Expected: Shows coverage table with percentages

**Step 3: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "feat(frontend): configure vitest coverage"
```

---

### Task 5: Update .gitignore

**Files:**
- Modify: `.gitignore`

**Step 1: Add coverage and cache directories**

Edit `.gitignore`, add after the `# Testing` section:

```gitignore
# Testing
.pytest_cache/
.coverage
htmlcov/
.hypothesis/
.mypy_cache/

# Frontend coverage
frontend/coverage/
```

Note: `htmlcov/` already exists but is generic. The backend writes to `backend/htmlcov/` which is already covered by the pattern.

**Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: add mypy cache and frontend coverage to gitignore"
```

---

### Task 6: Create Makefile

**Files:**
- Create: `Makefile`

**Step 1: Create the Makefile**

Create `Makefile` in the project root:

```makefile
.PHONY: help test test-backend test-frontend lint lint-backend lint-frontend \
        format format-backend format-frontend format-check format-check-backend format-check-frontend \
        typecheck typecheck-backend typecheck-frontend cover cover-backend cover-frontend \
        all ci install install-backend install-frontend dev dev-backend dev-frontend clean

# Default target
help:
	@echo "Oya Development Commands"
	@echo "========================"
	@echo ""
	@echo "Quality Checks:"
	@echo "  make test              Run all tests"
	@echo "  make lint              Check for linting issues"
	@echo "  make format            Auto-fix formatting (modifies files)"
	@echo "  make format-check      Verify formatting without changes"
	@echo "  make typecheck         Run type checkers (mypy + tsc)"
	@echo "  make cover             Run tests with coverage reports"
	@echo ""
	@echo "Combined:"
	@echo "  make all               Run lint + format-check + typecheck + test"
	@echo "  make ci                Run all + cover (for CI pipelines)"
	@echo ""
	@echo "Development:"
	@echo "  make dev               Start backend and frontend dev servers"
	@echo "  make install           Install all dependencies"
	@echo "  make clean             Remove generated files (coverage, cache)"
	@echo ""
	@echo "Per-Service (append -backend or -frontend):"
	@echo "  make test-backend      make test-frontend"
	@echo "  make lint-backend      make lint-frontend"
	@echo "  make format-backend    make format-frontend"
	@echo "  make cover-backend     make cover-frontend"
	@echo "  make typecheck-backend make typecheck-frontend"
	@echo ""
	@echo "Workflows:"
	@echo "  make install && make all    First-time setup and verify"
	@echo "  make format && make all     Fix formatting then verify"
	@echo "  make cover-backend          Check coverage for just backend"
	@echo "  make dev-frontend           Work on frontend only"

# =============================================================================
# Combined Targets
# =============================================================================

test: test-backend test-frontend

lint: lint-backend lint-frontend

format: format-backend format-frontend

format-check: format-check-backend format-check-frontend

typecheck: typecheck-backend typecheck-frontend

cover: cover-backend cover-frontend

all: lint format-check typecheck test

ci: all cover

install: install-backend install-frontend

dev:
	@echo "Starting dev servers (backend on :8000, frontend on :5173)..."
	@echo "Press Ctrl+C to stop"
	@trap 'kill 0' INT; \
		$(MAKE) dev-backend & \
		$(MAKE) dev-frontend & \
		wait

clean:
	rm -rf backend/.mypy_cache
	rm -rf backend/htmlcov
	rm -rf backend/.pytest_cache
	rm -rf backend/.coverage
	rm -rf frontend/coverage
	rm -rf frontend/node_modules/.vite
	@echo "Cleaned generated files"

# =============================================================================
# Backend Targets
# =============================================================================

test-backend:
	cd backend && source .venv/bin/activate && pytest tests/

lint-backend:
	cd backend && source .venv/bin/activate && ruff check src/ tests/

format-backend:
	cd backend && source .venv/bin/activate && ruff format src/ tests/

format-check-backend:
	cd backend && source .venv/bin/activate && ruff format --check src/ tests/

typecheck-backend:
	cd backend && source .venv/bin/activate && mypy src/oya

cover-backend:
	cd backend && source .venv/bin/activate && pytest --cov=src/oya --cov-report=term-missing --cov-report=html tests/
	@echo "Coverage report: backend/htmlcov/index.html"

install-backend:
	cd backend && source .venv/bin/activate && pip install -e ".[dev]"

dev-backend:
	cd backend && source .venv/bin/activate && WORKSPACE_PATH=.. uvicorn oya.main:app --reload --port 8000

# =============================================================================
# Frontend Targets
# =============================================================================

test-frontend:
	cd frontend && npm run test

lint-frontend:
	cd frontend && npm run lint

format-frontend:
	cd frontend && npm run format

format-check-frontend:
	cd frontend && npm run format:check

typecheck-frontend:
	cd frontend && npx tsc --noEmit

cover-frontend:
	cd frontend && npm run test:coverage
	@echo "Coverage report: frontend/coverage/index.html"

install-frontend:
	cd frontend && npm install

dev-frontend:
	cd frontend && npm run dev
```

**Step 2: Verify help works**

Run:
```bash
make help
```

Expected: Shows the full help output with all targets and workflows

**Step 3: Commit**

```bash
git add Makefile
git commit -m "feat: add Makefile for unified development commands"
```

---

### Task 7: Verify All Targets Work

**Step 1: Test install targets**

Run:
```bash
make install
```

Expected: Installs both backend and frontend dependencies

**Step 2: Test lint targets**

Run:
```bash
make lint
```

Expected: Runs ruff and eslint, may show warnings (that's okay)

**Step 3: Test format-check targets**

Run:
```bash
make format-check
```

Expected: Checks formatting for both services

**Step 4: Test typecheck targets**

Run:
```bash
make typecheck
```

Expected: Runs mypy and tsc, may show type errors (that's okay for now)

**Step 5: Test test targets**

Run:
```bash
make test
```

Expected: Runs pytest and vitest, tests should pass

**Step 6: Test cover targets**

Run:
```bash
make cover
```

Expected: Runs tests with coverage, generates HTML reports

**Step 7: Test all target**

Run:
```bash
make all
```

Expected: Runs lint + format-check + typecheck + test in sequence

**Step 8: Test clean target**

Run:
```bash
make clean
```

Expected: Removes generated files, prints confirmation

**Step 9: Final commit if any fixes were needed**

If any fixes were made during verification:
```bash
git add -A
git commit -m "fix: makefile target adjustments from testing"
```

---

## Summary

After completing all tasks, you will have:

1. Backend with mypy and pytest-cov configured
2. Frontend with Prettier and Vitest coverage configured
3. Root Makefile with all targets working
4. Updated .gitignore for new generated files

Run `make help` to see all available commands.
