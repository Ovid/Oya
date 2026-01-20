# Contributing to Oya

Thank you for your interest in contributing to Oya! This document provides guidelines for contributing to the project.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a welcoming and inclusive environment.

## Development Setup

### Backend (Python)

```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Frontend (TypeScript/React)

```bash
cd frontend
npm install
```

### Running Tests

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

## Configuration Rules

**Never hardcode configurable values.** All tunable parameters must come from `config.ini` via the settings object.

### Do:
```python
from oya.config import load_settings
settings = load_settings()
max_size = settings.files.max_file_size_kb
```

### Don't:
```python
max_size = 500  # Hardcoded!
path = workspace / ".oyawiki"  # Hardcoded path!
```

### Adding New Config Values

1. Add to `CONFIG_SCHEMA` in `backend/src/oya/config.py`
2. Add to the appropriate section dataclass
3. Document in `config.ini.example`
4. Write tests verifying type and range

## Code Style

### Backend (Python)
- Python 3.11+
- Format with `ruff format`
- Lint with `ruff check`
- Line length: 100 characters
- Type hints required for public APIs

### Frontend (TypeScript)
- TypeScript strict mode
- ESLint for linting
- Tailwind CSS for styling

## Pull Request Process

1. Create a feature branch from `main`
2. Write tests for new functionality
3. Ensure all tests pass: `pytest` and `npm test`
4. Update documentation if needed
5. Submit PR with clear description of changes

## Testing Guidelines

- Write tests before implementation (TDD preferred)
- Tests should verify behavior, not implementation details
- Config tests verify types and ranges, not specific values
- Use property-based testing (hypothesis) for complex logic

## Questions?

Open an issue for questions about contributing.
