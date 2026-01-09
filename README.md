# Ọya

A local-first, editable wiki generator for codebases. Ọya creates comprehensive documentation from your code and lets you correct it when the AI gets things wrong.

# ALPHA CODE!

This is not suitable for production.

# Who is Ọya?

Ọya (Yorùbá: Ọya, also known as Oyá, Oiá, Yànsàn-án, Yansã, Iyámsá, or Iansã)
is one of the principal female deities of the Yoruba pantheon. She is the
orisha of winds, lightning, and storms, and is the only orisha capable
of controlling the Eégún (spirits of the dead), a power given to her by Babalú
Ayé. [Per Wikipedia](https://en.wikipedia.org/wiki/%E1%BB%8Cya)

## Features

- **Automatic Wiki Generation** - Generates overview, architecture, workflow, directory, and file documentation from your codebase
- **Evidence-Gated Q&A** - Ask questions about your code with answers backed by citations
- **Human Corrections** - Add notes to fix AI mistakes; corrections are treated as ground truth in regeneration
- **Local-First** - All data stays in your repo under `.oyawiki/`
- **Multi-Provider LLM Support** - Works with OpenAI, Anthropic, Google, or local Ollama

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Node.js 18+ (for frontend development)
- Python 3.11+ (for backend development)


### Running with Docker

```bash
# Clone the repository
git clone https://github.com/your-org/oya.git
cd oya

# Set LLM providers and repo to generate docs for
# Yes, this is terrible. We'll fix it later after
# core features are stable.
- Copy `.env.example` to `.env` and edit.

# Start the services
docker-compose up

# Open http://localhost:5173 in your browser
```

### Development Setup

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Set required environment variable
export WORKSPACE_PATH=/path/to/your/repo

# Run the API server
uvicorn oya.main:app --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

## Configuration

Ọya uses environment variables for configuration:

| Variable | Description | Default |
|----------|-------------|---------|
| `WORKSPACE_PATH` | Path to the repository to document | *Required* |
| `ACTIVE_PROVIDER` | LLM provider (`openai`, `anthropic`, `google`, `ollama`) | Auto-detected |
| `ACTIVE_MODEL` | Model name | Provider default |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `GOOGLE_API_KEY` | Google AI API key | - |
| `OLLAMA_ENDPOINT` | Ollama server URL | `http://localhost:11434` |

## Project Structure

```
oya/
├── backend/                 # FastAPI backend
│   ├── src/oya/
│   │   ├── api/            # REST API endpoints
│   │   ├── db/             # SQLite database
│   │   ├── generation/     # Wiki generation
│   │   ├── llm/            # LLM client
│   │   ├── notes/          # Correction system
│   │   ├── parsing/        # Code parsers
│   │   ├── qa/             # Q&A system
│   │   ├── repo/           # Git integration
│   │   └── vectorstore/    # ChromaDB
│   └── tests/
├── frontend/               # React frontend
│   └── src/
│       ├── api/            # API client
│       ├── components/     # UI components
│       ├── context/        # React context
│       └── types/          # TypeScript types
└── docker-compose.yml
```

## API Endpoints

### Repository
- `GET /api/repos/status` - Get repository status
- `POST /api/repos/init` - Start wiki generation

### Wiki
- `GET /api/wiki/tree` - Get wiki structure
- `GET /api/wiki/overview` - Get overview page
- `GET /api/wiki/architecture` - Get architecture page
- `GET /api/wiki/workflows/{slug}` - Get workflow page
- `GET /api/wiki/directories/{slug}` - Get directory page
- `GET /api/wiki/files/{slug}` - Get file page

### Q&A
- `POST /api/qa/ask` - Ask a question about the codebase

### Notes
- `POST /api/notes` - Create a correction note
- `GET /api/notes` - List notes
- `GET /api/notes/{id}` - Get a note
- `DELETE /api/notes/{id}` - Delete a note

### Search
- `GET /api/search?q={query}` - Search wiki and notes

### Jobs
- `GET /api/jobs` - List generation jobs
- `GET /api/jobs/{id}` - Get job status
- `GET /api/jobs/{id}/stream` - SSE progress stream

## Q&A Modes

Ọya supports two Q&A modes:

- **Evidence-Gated (default)** - Only answers when sufficient evidence exists in the codebase. Refuses to answer speculative questions.
- **Loose Mode** - Always attempts to answer, but includes a warning that the response may be speculative.

## Correction System

When the AI generates incorrect documentation:

1. Click "Add Correction" on any wiki page
2. Select the scope (file, directory, workflow, or general)
3. Write your correction in Markdown
4. Save - the note is stored in `.oyawiki/notes/`

Notes are treated as ground truth during regeneration. The LLM is instructed to integrate corrections naturally into the documentation.

## Running Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please read our contributing guidelines before submitting a PR.
