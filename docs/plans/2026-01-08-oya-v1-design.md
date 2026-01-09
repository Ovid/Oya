# Oya v1 Design Document

**Date:** 2026-01-08
**Status:** Approved
**Based on:** [prds/oya-v1.md](../../prds/oya-v1.md)

---

## 1. System Architecture Overview

Oya is a **Python (FastAPI) backend + React (Vite) frontend** system running via Docker Compose with two services:

### Backend Service (`oya-backend`)
- FastAPI application (Python 3.11+)
- Embedded ChromaDB for vector storage
- SQLite (`.oyawiki/meta/oya.db`) for metadata, job tracking, and FTS5 search
- GitPython for repository operations
- LiteLLM for multi-provider LLM access
- Language-specific parsers (Python `ast`, TypeScript compiler API, Java parser, Node/JS parser) with Tree-sitter fallback
- Exposes REST API + SSE endpoints for progress streaming

### Frontend Service (`oya-frontend`)
- React 18+ with TypeScript
- Vite for development and production builds
- Tailwind CSS + Headless UI for components
- React Context + useReducer for state management
- react-markdown with Mermaid support for rendering
- CodeMirror for the correction editor
- Communicates with backend via REST + EventSource (SSE)

### Data Flow
1. User mounts local repo as Docker volume → `/workspace`
2. Backend indexes repo → creates embeddings (ChromaDB) + metadata (SQLite)
3. Backend generates wiki hierarchically → saves to `.oyawiki/wiki/`
4. Frontend requests wiki pages via API → renders with citations
5. User adds corrections → saved as notes in `.oyawiki/notes/` → triggers targeted regeneration
6. Q&A queries → semantic search (ChromaDB) + full-text (SQLite FTS5) → LLM with evidence gating

---

## 2. Directory Structure & Data Model

### Repository Layout (after initialization)

```
<user-repo>/
├── .oyawiki/
│   ├── .gitignore              # Ignores ephemeral data
│   ├── meta/
│   │   └── oya.db             # SQLite: metadata, jobs, search index
│   ├── wiki/                   # Generated documentation (committable)
│   │   ├── overview.md
│   │   ├── architecture.md
│   │   ├── workflows/
│   │   │   └── {workflow-slug}.md
│   │   ├── directories/
│   │   │   └── {path-slug}.md
│   │   └── files/
│   │       └── {file-path-slug}.md
│   ├── notes/                  # Human corrections (committable)
│   │   └── {timestamp}-{scope}-{slug}.md  # With frontmatter
│   ├── config/
│   │   ├── settings.json      # Non-secret config (committable)
│   │   └── secrets.env        # LLM API keys (gitignored)
│   ├── index/                  # ChromaDB vector store (gitignored)
│   └── cache/                  # Temporary parsing cache (gitignored)
├── .oyaignore                  # Optional: custom file exclusions
└── <rest of user's codebase>
```

### SQLite Schema (key tables)
- `generations` - Job tracking: id, type, status, started_at, completed_at, commit_hash
- `wiki_pages` - Page metadata: path, type, generated_at, commit_hash, word_count
- `notes` - Note registry: id, filepath, scope, target, created_at, author, git_context
- `citations` - Maps wiki content to source files/lines/commits
- `fts_content` - FTS5 virtual table for full-text search across wiki + notes

### Note Format (frontmatter + markdown)
```yaml
---
datetime: 2026-01-08T10:30:00Z
author: Curtis Poe
scope: file  # or: directory, workflow, architecture, general
target: src/auth/login.py
git_branch: main
git_commit: abc123def
git_dirty: false
oya_version: 1.0.0
---

The login function actually uses OAuth2, not JWT as the AI suggested...
```

---

## 3. Backend API Design

### Core REST Endpoints

#### Repository Management
- `POST /api/repos/init` - Initialize repo (local path or GitHub URL)
  - Body: `{path: string}` or `{github_url: string}`
  - Returns: `{job_id: string}`
  - Starts background job to clone (if needed) and index

- `GET /api/repos/status` - Current repo info
  - Returns: repo path, HEAD commit, generation status, last updated

#### Wiki Pages
- `GET /api/wiki/{page_type}/{slug}` - Fetch wiki page
  - Types: overview, architecture, workflows, directories, files
  - Returns: markdown content, metadata, citations, last generated

- `GET /api/wiki/tree` - Full wiki structure for navigation
  - Returns: hierarchical tree of all pages with metadata

#### Q&A
- `POST /api/qa/ask` - Ask question
  - Body: `{question: string, context?: {page_type, slug}, mode: 'gated' | 'loose'}`
  - Returns: `{answer: string, citations: [...], evidence_sufficient: boolean, disclaimer: string}`
  - Uses hybrid search → evidence evaluation → LLM generation

#### Notes/Corrections
- `POST /api/notes` - Create correction
  - Body: `{scope, target, content: markdown, context: {current_page}}`
  - Saves note with auto-generated metadata
  - Returns: `{note_id, regeneration_job_id}`

- `GET /api/notes?target={path}` - List notes for a target
  - Returns: array of notes affecting this file/directory/workflow

#### Jobs & Progress
- `GET /api/jobs/{job_id}` - Job status
  - Returns: `{status, progress, started_at, completed_at, error?}`

- `GET /api/jobs/{job_id}/stream` - **SSE endpoint** for live progress
  - Streams: `{type: 'progress' | 'log' | 'complete', data: {...}, timestamp}`

#### Search
- `GET /api/search?q={query}&type=hybrid|semantic|fulltext`
  - Hybrid: combines FTS5 + ChromaDB results
  - Returns: ranked results with snippets and page links

---

## 4. Wiki Generation Process

### Hierarchical Generation Pipeline (runs as background job)

#### Phase 1: Repository Analysis
1. Parse `.oyaignore` + apply default exclusions (node_modules, .git, build artifacts, etc.)
2. Scan repository file tree → build file inventory
3. Parse files with language-specific parsers (Python, TypeScript, Java, JavaScript) or Tree-sitter fallback
4. Extract symbols: functions, classes, imports, exports, API routes, CLI commands
5. Store parsed data in cache + index in ChromaDB (file chunks with embeddings)

#### Phase 2: Overview & Architecture (global context)
6. Generate **Overview** page
   - LLM prompt with: repo structure, README, package files, entry points
   - Output: purpose, tech stack, getting started, key concepts
7. Generate **Architecture** page
   - LLM prompt with: file structure, dependencies, parsed symbols across repo
   - Output: system design, component relationships, data flow, Mermaid diagrams
   - Save diagrams as artifacts

#### Phase 3: Workflow Discovery
8. Identify entry points from parsed code (CLI parsers, route handlers, main functions, test suites)
9. Trace execution paths through imports and call graphs
10. LLM clusters related code paths into workflows
11. Generate **Workflow** pages for each identified workflow
    - Include: purpose, entry points, key files involved, sequence diagrams

#### Phase 4: Directory Summaries
12. Group files by directory
13. Generate **Directory** pages (aggregating file-level understanding)
    - LLM prompt with: files in directory, their parsed symbols, role in architecture
    - Output: directory purpose, what lives here, how it fits in the system

#### Phase 5: File Documentation
14. Generate **File** pages in parallel (with architecture context loaded)
    - LLM prompt with: file content, parsed AST, architecture context, related files
    - Output: purpose, key exports, how it's used, important functions/classes

#### Progress Tracking
- Each phase emits SSE events: `{phase, step, total_steps, message, timestamp}`
- Status stored in SQLite `generations` table
- Resumable: if job fails, can restart from last completed phase

---

## 5. Notes & Correction System

### Creating a Correction

1. **User triggers correction** from any of these contexts:
   - Wiki page: "Add correction" button (scope/target auto-filled from current page)
   - Q&A answer: "Correct this answer" button (scope inferred from question context)
   - Manual: "New note" from navigation

2. **Slide-over panel opens** with:
   - **Scope selector** (pre-filled): file / directory / workflow / architecture / general
   - **Target field** (pre-filled): path or slug based on current context
   - **Markdown editor** (CodeMirror with live preview)
   - Guidance text: "Explain what's incorrect and provide the correct information..."
   - **Save** button

3. **On save:**
   - Generate note filename: `{ISO-timestamp}-{scope}-{slug}.md`
   - Add frontmatter with metadata (datetime, author from git config, git context, scope, target)
   - Write to `.oyawiki/notes/`
   - Create SQLite entry linking note to target

4. **Trigger targeted regeneration:**
   - File-scoped → regenerate file page only
   - Directory-scoped → regenerate directory page
   - Workflow-scoped → regenerate workflow page
   - Architecture-scoped → regenerate architecture page
   - General → regenerate overview
   - Background job starts with job_id returned to frontend

5. **Regeneration with notes precedence:**
   - Load all notes affecting the target
   - Include notes in LLM prompt as "ground truth corrections from developer"
   - Instruct LLM: "Human notes override any inference; integrate corrections naturally"
   - Generate new version

6. **Confirmation flow:**
   - Frontend polls job status
   - When complete, show **inline diff view** on the affected page
   - Highlight changes with diff styling (red/green)
   - Buttons: "Approve" (dismiss diff) or "Refine correction" (reopens editor with note pre-loaded)
   - User can navigate away; badge shows "pending review" until approved

---

## 6. Q&A System with Evidence Gating

### Query Flow

1. **User enters question** in bottom dock Q&A input
   - Optional context: current page being viewed
   - Mode toggle: "Evidence-gated" (default) vs "Loose mode"

2. **Hybrid search for relevant content:**
   - **Semantic search** (ChromaDB): embedding similarity on question → top K chunks
   - **Full-text search** (SQLite FTS5): keyword matching → top N results
   - **Merge and rank** results by relevance
   - **Prioritize notes** over generated wiki over raw code
   - Retrieve with commit hash context for each chunk

3. **Evidence evaluation (if gated mode):**
   - LLM evaluates: "Given these sources, can you answer this question completely and accurately?"
   - Prompt includes: question + retrieved chunks + source types (note/wiki/code)
   - LLM responds: `{can_answer: boolean, reasoning: string, missing_info?: string}`
   - If `can_answer: false`:
     - Return message: "Not enough information found. Try: [suggestions based on missing_info]. Or switch to Loose mode."
     - No answer generated
   - If `can_answer: true`: proceed

4. **Generate answer with citations:**
   - LLM prompt with: question + ranked sources + instruction to cite
   - Output format: markdown answer with inline citation markers `[1]`, `[2]`, etc.
   - Extract citations mapping: `[1] → {file: path, lines: range, commit: hash}`

5. **Response format:**
   - **Disclaimer banner** (always): "⚠️ AI-generated answer - may contain errors. Verify against sources."
   - **Answer content** (markdown with citation markers)
   - **Citations section** (expandable):
     - Each citation shows: file path, relevant lines, commit hash
     - Click citation → opens provenance viewer (modal or slide-over)
   - **"Correct this answer"** button (opens correction editor)

6. **Loose mode differences:**
   - Skip evidence evaluation (always generate answer)
   - **Warning banner**: "🔓 Loose mode - answer may be speculative with limited evidence"
   - Still includes citations (but may cite fewer sources)
   - Disclaimer is more prominent

### Provenance Viewer
- Shows code snippet with syntax highlighting
- File path + line numbers
- Commit hash with timestamp
- Link: "View in repo at this commit"

---

## 7. Frontend UI Components & Layout

### Global Layout

#### Top Bar (fixed, always visible)
```
┌──────────────────────────────────────────────────────────┐
│ [Oya Logo] MyRepo                    [●] Generating...   │
│                                      Last: 2m ago        │
│                                                          │
│                     [OpenAI GPT-4] [🌙] [?] [⋮]          │
└──────────────────────────────────────────────────────────┘
```
- Left: Logo + repo name
- Center: Status pill (Idle/Indexing/Generating/Answering) + timestamp
- Right: Active model (read-only), dark mode toggle, help, overflow menu

#### Main Layout
```
┌────────┬───────────────────────────┬──────────┐
│        │                           │          │
│ Nav    │     Wiki Content          │ TOC      │
│ Sidebar│   (markdown + diagrams)   │ + Actions│
│        │                           │          │
│        │                           │          │
└────────┴───────────────────────────┴──────────┘
         └─ Q&A Dock (collapsible) ────────┘
```

#### Left Sidebar (250px, toggleable)
- **Default view**: Section-based navigation
  - Overview
  - Architecture
  - Workflows ▾
    - User Authentication
    - Data Processing
  - Key Directories ▾
  - All Files ▾ (collapsed by default)
  - Notes ▾
- **Toggle**: File tree view (hierarchical folder structure)
- Search input at top filters navigation

#### Center Content Area
- Rendered markdown wiki page
- Mermaid diagrams with "Edit diagram" button on hover
- Code blocks with syntax highlighting
- Citation markers `[1]` are clickable links
- Diff view overlay when reviewing regenerated content

#### Right Sidebar (200px, collapsible)
- "On this page" TOC (auto-generated from headers)
- Quick actions:
  - "Add correction" button
  - "View sources" (shows all citations for this page)
  - "Regenerate page" button
- Repo status badge if dirty or behind

#### Bottom Q&A Dock (collapsible, 60px collapsed / 300px expanded)
- Collapsed: input bar with placeholder "Ask about this codebase..."
- Expanded:
  - Question history (chat-like interface)
  - Answer with citations
  - Mode toggle: [Evidence-gated ●] [ Loose ]
  - "Clear history" button

### Key Interactive Components

1. **Correction Editor** (Slide-over from right, 600px wide)
   - Header: scope chips + target path
   - CodeMirror editor (markdown mode)
   - Live preview toggle
   - Save/Cancel buttons

2. **Diff Viewer** (Overlay on wiki content)
   - Side-by-side or unified diff
   - Old content (red) vs new content (green)
   - Sticky header: "Review changes" + Approve/Refine buttons

3. **Provenance Viewer** (Modal, centered)
   - Code snippet with context
   - File metadata + commit info
   - "Open in editor" link

4. **Progress Modal** (during generation, non-dismissible)
   - Current phase/step indicator
   - Scrolling log output
   - Timestamp for each event
   - "Running in background" button to dismiss (job continues)

---

## 8. Configuration, Error Handling & Deployment

### Configuration System

#### `.oyawiki/config/settings.json` (committable)
```json
{
  "repo": {
    "default_branch": "main",
    "exclude_patterns": ["node_modules/**", "dist/**", "build/**"]
  },
  "generation": {
    "max_file_size_kb": 500,
    "parallel_file_limit": 10,
    "enable_mermaid": true
  },
  "qa": {
    "default_mode": "gated",
    "max_search_results": 20,
    "chunk_size": 1000
  },
  "ui": {
    "theme": "dark",
    "default_view": "sections"
  }
}
```

#### `.oyawiki/config/secrets.env` (gitignored)
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
OLLAMA_ENDPOINT=http://localhost:11434
ACTIVE_PROVIDER=openai  # or anthropic, google, ollama
ACTIVE_MODEL=gpt-4o
```

### LiteLLM Integration
- Single unified client initialized with active provider/model from secrets
- Automatic fallback to Ollama if no API keys configured
- Model dropdown in UI (read-only) shows active configuration
- To change providers: edit secrets.env and restart backend

### Error Handling

#### Generation Failures
- If phase fails (e.g., LLM timeout, rate limit):
  - Save partial results with "incomplete" status
  - Mark affected pages with warning badge
  - Log error to SQLite with stack trace
  - Allow manual retry from last successful phase

#### Q&A Failures
- Search errors → fallback to full-text only
- LLM errors → show user-friendly message with retry button
- Network timeouts → retry with exponential backoff

#### Note/Correction Failures
- Note saves even if regeneration fails
- User notified: "Note saved, but regeneration failed: [reason]. Retry?"
- Failed regeneration jobs are resumable

#### Graceful Degradation
- If ChromaDB fails → disable semantic search, use FTS5 only
- If parser fails for a file → fall back to raw text + Tree-sitter
- If Mermaid rendering fails → show source code in `<pre>` block

### Docker Deployment

#### docker-compose.yml
```yaml
version: '3.9'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ${REPO_PATH}:/workspace
      - ./.oyawiki:/workspace/.oyawiki
    environment:
      - WORKSPACE_PATH=/workspace
    env_file:
      - .oyawiki/config/secrets.env

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - VITE_API_URL=http://localhost:8000
```

#### User workflow
1. Clone Oya repo
2. Create `.env` with `REPO_PATH=/path/to/their/repo`
3. Add LLM keys to `.oyawiki/config/secrets.env`
4. Run `docker-compose up`
5. Open `http://localhost:3000`
6. Initialize repo from UI

### Security Considerations
- Backend binds to `localhost` only (no external access)
- Secrets never logged or exposed in API responses
- `.oyawiki/config/secrets.env` is gitignored by default
- No authentication needed (local single-user)

---

## 9. Testing Strategy

### Backend Testing

#### Unit Tests (pytest)
- Parser modules (language-specific + Tree-sitter fallback)
  - Test: correctly extracts functions, classes, imports from sample files
  - Test: handles malformed code gracefully
- Note system
  - Test: frontmatter generation, scope/target resolution
  - Test: note precedence in prompts
- Evidence gating logic
  - Test: correctly evaluates sufficiency with various chunk combinations
  - Test: note sources prioritized over code sources
- Search (hybrid)
  - Test: FTS5 exact matches
  - Test: semantic search returns relevant results
  - Test: ranking combines both sources properly

#### Integration Tests
- Full generation pipeline on small test repo
  - Test: all phases complete successfully
  - Test: wiki pages generated with expected structure
  - Test: job progress events emitted correctly
- Correction → regeneration flow
  - Test: note saved with correct metadata
  - Test: regeneration scoped correctly
  - Test: regenerated content incorporates note
- Q&A with real LLM (Ollama in CI)
  - Test: gated mode rejects insufficient evidence
  - Test: citations extracted correctly
  - Test: loose mode answers without evidence

#### API Tests
- FastAPI TestClient for all endpoints
- SSE streaming tested with async client
- Error responses for invalid inputs

### Frontend Testing

#### Component Tests (React Testing Library + Vitest)
- WikiPage component renders markdown + Mermaid
- CorrectionEditor validates and saves notes
- DiffViewer displays changes correctly
- QADock handles question/answer flow
- Navigation switches between section/tree views

#### E2E Tests (Playwright)
- Full user flow: init repo → browse wiki → add correction → review diff
- Q&A flow: ask question → receive answer with citations → open provenance viewer
- Search flow: search term → results → navigate to page

### LLM Prompt Testing
- Collect prompt/response pairs during development
- Version prompts with test fixtures
- Regression testing: ensure prompt changes don't break expected outputs

### Development Process Note
- **All implementation must follow the RED/GREEN TDD workflow** using the `superpowers:test-driven-development` skill
- Write failing tests first (RED)
- Implement minimal code to pass (GREEN)
- Refactor with tests passing
- This applies to both backend (pytest) and frontend (Vitest) development

---

## 10. Licensing, Performance & Future Considerations

### Open Source Licensing (F26)

#### Project License
- Oya itself: **MIT or Apache 2.0** (permissive, user's choice)
- Clear LICENSE file in repo root

#### Dependency Audit
- All dependencies must be permissively licensed (MIT, Apache, BSD, ISC)
- **Forbidden licenses:** GPL, AGPL, or any copyleft (incompatible with commercial use)
- Automated license checker in CI pipeline
- Generate `LICENSES.md` listing all dependencies with their licenses
- Key dependencies verified:
  - FastAPI (MIT), React (MIT), Vite (MIT)
  - ChromaDB (Apache 2.0), SQLite (public domain)
  - LiteLLM (MIT), GitPython (BSD)
  - Tailwind (MIT), Headless UI (MIT)

### Performance Optimizations

#### Backend
- **Incremental regeneration:** Only regenerate affected pages, not entire wiki
- **Parallel file processing:** Process multiple files concurrently in Phase 5
- **Caching:** Cache parsed ASTs to avoid re-parsing unchanged files
- **Chunking strategy:** Optimal chunk size (1000 tokens) balances context vs search precision
- **Connection pooling:** Reuse LLM client connections

#### Frontend
- **Code splitting:** Lazy load heavy components (CodeMirror, Mermaid renderer)
- **Virtual scrolling:** For long file lists and search results
- **Memoization:** React.memo for expensive wiki page renders
- **Debounced search:** Avoid excessive API calls while typing

#### Large Repository Handling
- Default max file size: 500KB (configurable)
- Skip binary files automatically
- Progressive loading: Load overview first, other pages on demand
- Show file/directory counts during generation for user awareness
- Allow user to scope generation to specific directories

### Mermaid Diagram Polish
- Custom Mermaid theme matching Oya UI (dark/light mode aware)
- Automatic layout optimization for readability
- Export diagrams as SVG or PNG
- Diagram editing with live preview and syntax validation

### Future Enhancements (v2 ideas - out of scope for v1)

- **Multi-repo support:** Compare/link across multiple repositories
- **IDE plugins:** VS Code extension for inline Oya integration
- **Notification system:** Alert when wiki is stale after N commits
- **Collaborative features:** Shared notes, comments on wiki pages
- **Advanced workflows:** Custom workflow definitions, step-by-step debugging flows
- **API documentation generation:** Automatic OpenAPI/GraphQL schema docs
- **Diff-aware regeneration:** Regenerate based on actual code changes, not entire pages
- **Export formats:** PDF, Confluence, Notion export

---

## Summary

This design provides a comprehensive blueprint for Oya v1, a local-first, editable DeepWiki clone that prioritizes trust, correctness, and developer experience. The system combines modern web technologies (FastAPI, React, ChromaDB) with careful attention to the correction feedback loop, evidence-based Q&A, and git-native artifacts.

Key differentiators:
- **Editable by design:** Notes system with regeneration and confirmation loop
- **Trust signals:** Disclaimers, citations, provenance, evidence-gating
- **Developer-friendly:** DeepWiki UX, familiar patterns, Docker-based
- **Repo-native:** All artifacts committable, version-controlled alongside code

Implementation will follow TDD practices using the RED/GREEN workflow to ensure code quality and maintainability throughout development.
