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
