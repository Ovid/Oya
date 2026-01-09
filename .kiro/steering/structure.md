# Project Structure

## Repository Layout

```
oya/
├── backend/                 # Python FastAPI backend
│   ├── src/oya/            # Source code
│   ├── tests/              # Test files
│   ├── pyproject.toml      # Python dependencies and config
│   └── Dockerfile          # Backend container
├── frontend/               # React TypeScript frontend
│   ├── src/                # Source code
│   ├── public/             # Static assets
│   ├── package.json        # Node dependencies
│   └── Dockerfile          # Frontend container
├── .oyawiki/             # Generated artifacts (committable)
├── docs/                   # Project documentation
├── prds/                   # Product requirements
├── docker-compose.yml      # Service orchestration
├── .env.example           # Environment template
└── .oyaignore             # Files to ignore during processing
```

## Backend Structure (`backend/src/oya/`)

```
oya/
├── __init__.py
├── main.py                 # FastAPI app entry point
├── config.py              # Configuration management
├── api/                   # REST API layer
│   ├── deps.py            # Dependency injection
│   ├── schemas.py         # Pydantic models
│   └── routers/           # API route handlers
│       ├── repos.py       # Repository management
│       ├── wiki.py        # Wiki content endpoints
│       ├── jobs.py        # Background job status
│       ├── search.py      # Search functionality
│       ├── qa.py          # Q&A system
│       └── notes.py       # Correction notes
├── db/                    # Database layer
│   ├── connection.py      # Database setup
│   └── migrations.py      # Schema migrations
├── generation/            # Wiki generation engine
│   ├── orchestrator.py    # Generation coordination
│   ├── architecture.py    # Architecture analysis
│   ├── overview.py        # Overview generation
│   ├── workflows.py       # Workflow detection
│   ├── directory.py       # Directory summaries
│   ├── file.py           # File analysis
│   ├── chunking.py       # Content chunking
│   └── prompts.py        # LLM prompts
├── llm/                   # LLM integration
│   └── client.py         # Multi-provider LLM client
├── notes/                 # Correction system
│   ├── schemas.py        # Note data models
│   └── service.py        # Note management
├── parsing/               # Code parsing
│   ├── base.py           # Parser interface
│   ├── models.py         # Parsing data models
│   ├── registry.py       # Parser registration
│   ├── python_parser.py  # Python code parser
│   ├── typescript_parser.py # TypeScript parser
│   ├── java_parser.py    # Java parser
│   └── fallback_parser.py # Generic parser
├── qa/                    # Q&A system
│   ├── schemas.py        # Q&A data models
│   └── service.py        # Question answering
├── repo/                  # Repository handling
│   ├── git_repo.py       # Git operations
│   └── file_filter.py    # File filtering logic
└── vectorstore/           # Vector database
    └── store.py          # ChromaDB integration
```

## Frontend Structure (`frontend/src/`)

```
src/
├── App.tsx                # Main application component
├── main.tsx              # React entry point
├── index.css             # Global styles
├── vite-env.d.ts         # Vite type definitions
├── api/                  # API client layer
│   └── client.ts         # Backend API client
├── components/           # React components
│   ├── index.ts          # Component exports
│   ├── Layout.tsx        # Main layout wrapper
│   ├── TopBar.tsx        # Fixed top navigation
│   ├── Sidebar.tsx       # Left navigation sidebar
│   ├── RightSidebar.tsx  # Right content sidebar
│   ├── WikiContent.tsx   # Wiki page renderer
│   ├── QADock.tsx        # Q&A interface
│   ├── NoteEditor.tsx    # Correction editor
│   ├── PageLoader.tsx    # Loading states
│   ├── GenerationProgress.tsx # Progress indicator
│   └── pages/            # Page components
│       ├── index.ts      # Page exports
│       ├── OverviewPage.tsx     # Repository overview
│       ├── ArchitecturePage.tsx # Architecture documentation
│       ├── WorkflowPage.tsx     # Workflow pages
│       ├── DirectoryPage.tsx    # Directory summaries
│       └── FilePage.tsx         # File documentation
├── context/              # React context
│   └── AppContext.tsx    # Global application state
└── types/                # TypeScript definitions
    └── index.ts          # Shared type definitions
```

## Generated Artifacts (`.oyawiki/`)

```
.oyawiki/
├── .gitignore            # Ignore ephemeral files
├── wiki/                 # Generated wiki content (committable)
│   ├── overview.md
│   ├── architecture.md
│   ├── directories/
│   └── files/
├── notes/                # Human corrections (committable)
├── meta/                 # Generation metadata (committable)
├── config/               # Settings
│   ├── settings.json     # Non-secret config (committable)
│   └── secrets.*         # API keys (gitignored)
├── index/                # Search indexes (ephemeral)
└── cache/                # Temporary data (ephemeral)
```

## Naming Conventions

- **Python**: snake_case for files, functions, variables
- **TypeScript**: PascalCase for components, camelCase for functions/variables
- **Files**: kebab-case for non-component files, PascalCase for React components
- **API Routes**: RESTful conventions (`/api/resource` or `/api/resource/{id}`)
- **Database**: snake_case for tables and columns

## Import Patterns

- **Backend**: Relative imports within modules, absolute from `oya.*`
- **Frontend**: Relative imports for local files, absolute for external packages
- **Components**: Export from index files for clean imports