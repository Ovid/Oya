# Technology Stack

## Architecture
- **Backend**: Python 3.11+ with FastAPI
- **Frontend**: React 19+ with TypeScript and Vite
- **Database**: SQLite with ChromaDB for vector storage
- **Deployment**: Docker Compose only

## Backend Stack
- **Framework**: FastAPI with uvicorn server
- **Dependencies**: 
  - `pydantic` for data validation
  - `chromadb` for vector storage
  - `litellm` for multi-provider LLM support
  - `gitpython` for git integration
  - `tree-sitter` parsers for code analysis
- **Testing**: pytest with asyncio support
- **Linting**: ruff for code formatting and linting

## Frontend Stack
- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS with typography plugin
- **UI Components**: Headless UI for accessible components
- **Routing**: React Router DOM
- **Markdown**: react-markdown with remark-gfm
- **Diagrams**: Mermaid for rendering diagrams

## Development Commands

### Docker (Recommended)
```bash
# Start entire application
docker-compose up

# Rebuild services
docker-compose up --build
```

### Backend Development
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# Run development server
uvicorn oya.main:app --reload

# Run tests
pytest

# Lint and format
ruff check .
ruff format .
```

### Frontend Development
```bash
cd frontend
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Lint
npm run lint

# Preview production build
npm run preview
```

## Environment Configuration
- Use `.env` file for configuration (see `.env.example`)
- Optional: `OYA_DATA_DIR` to override default data directory (~/.oya)
- Optional: LLM provider API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.)
- Secrets are gitignored and never committed

## Port Configuration
- Backend: `8000` (API server)
- Frontend: `5173` (development) / `3000` (Docker)
- Frontend connects to backend via `VITE_API_URL`