# **Product Requirements Document**

## **Metadata**

* **Initiative:** Oya – Local, Editable DeepWiki Clone
* **Epic:** Oya v1
* **Status:** DRAFT
* **Product Manager:** \[Name\]

---

## **1\. Introduction**

### **Problem Statement**

Developers need a **local-first, Dockerized system** that explains a codebase in a DeepWiki-like way while remaining **editable, trustworthy, and version-controlled**. Existing AI-driven code explainers are read-only, opaque, and prone to hallucination, with no durable correction loop tied to git context.

### **Current Situation**

* AI-generated documentation is often incorrect or incomplete.
* Corrections are ad hoc and not fed back into the system.
* Users cannot easily see *why* an answer was given or *what it was based on*.
* Long-running generation feels opaque and unreliable.
* Most tools are SaaS-first, not repo-native.

### **Proposed Solution**

**Oya** is a **Python backend \+ React frontend** application that runs entirely via Docker and generates a browsable “wiki” for a git repository. Unlike DeepWiki, Oya is **editable** through in-UI corrections that are saved as markdown notes inside the repository (`.oyawiki/notes/`) and treated as higher-priority truth for future generations and Q\&A.

Oya provides:

* A DeepWiki-style navigation and UX
* Interactive Q\&A with mandatory disclaimers and citations
* A tight correction → regeneration → confirmation loop
* Repo-native, committable artifacts
* Full local execution with optional cloud LLMs or Ollama

---

## **2\. Goals and Non-Goals**

### **Goals**

* DeepWiki-like first impression and navigation
* Strong trust signals: disclaimers, citations, provenance
* Editable, corrective documentation with git history
* Clear progress and status visibility
* Minimal friction for developers

### **Non-Goals (v1)**

* Authentication / authorization
* Hosted SaaS or multi-tenant deployments
* Automatic code modification or PR creation
* Real-time collaborative editing

---

## **3\. Scope**

### **In Scope**

* Docker-only execution
* Repo ingestion via GitHub URL or local path
* Wiki generation (overview, architecture, workflows, directories, files)
* Persistent top bar with global context and controls
* Q\&A assistant with citations and disclaimers
* In-UI correction editor (markdown)
* Notes ingestion and precedence
* Mermaid diagrams with polished rendering and editing
* Progress indicators with timestamps
* Multi-provider LLM support \+ Ollama fallback
* Repo-native artifacts under `.oyawiki/`
* Open-source, permissively licensed dependencies only

### **Out of Scope**

* Login/authentication
* Multi-user permissions
* Enterprise compliance tooling
* IDE plugins

---

## **4\. User Experience & Navigation**

### **4.1 Global Layout**

**Fixed, immovable top bar (always visible)**

* Left: Oya logo/name, current repo name
* Center: global status pill (Idle / Indexing / Generating / Answering) \+ last event timestamp
* Right:
  * Active provider/model (read-only)
  * Dark mode toggle
  * Help / Instructions
  * Overflow menu (advanced actions)

**Main layout**

* **Left sidebar:** Hybrid navigation
  * Default: section-first (Overview, Architecture, Workflows, Key Directories, All Files, Notes)
  * Toggle: file-tree view

* **Center content:** Wiki page (markdown \+ Mermaid)
* **Right sidebar:** “On this page” TOC, quick actions (Add correction, View sources)
* **Bottom dock:** Persistent, collapsible Q\&A input bar

### **4.2 Primary Flows**

**Create a Wiki**

1. User selects repo (GitHub URL or local path).
2. Progress UI shows steps, timestamps, and running log.
3. On completion, user lands on **Overview**.

**Browse Wiki**

* Navigate via sections or file tree.
* View diagrams, summaries, and expandable details.
* See subtle badge if repo has changed since generation.

**Add a Correction**

* Click “Add correction” on any page or Q\&A answer.
* Markdown editor opens with guidance.
* Scope auto-selected (file, directory, workflow, architecture, general).
* On save:
  * Note is written to `.oyawiki/notes/`
  * Targeted regeneration occurs
  * User is asked: “Is this correct?” with a summary/diff

**Ask Questions**

* Ask from bottom dock while reading.
* Context automatically applied.
* Answers:
  * Always include a disclaimer (“AI-generated; may be wrong”)
  * Always include citations
* Evidence-gated by default, with optional “Loose” mode (guarded by warning modal).

---

## **5\. Functional Requirements**

| ID    | Feature                    | Description                                                                 |
| ----- | -------------------------- | --------------------------------------------------------------------------- |
| F1    | Docker-only execution      | Entire system runs via Docker Compose (backend \+ frontend).                |
| F2    | Backend                    | Python backend (FastAPI recommended).                                       |
| F3    | Frontend                   | React frontend (TypeScript recommended).                                    |
| F4    | Repo ingestion             | GitHub URL or local git repo path.                                          |
| F5    | Artifact isolation         | All artifacts stored under `.oyawiki/` where feasible.                    |
| F6    | Wiki generation            | Overview, Architecture, Workflows, Directories, Files.                      |
| F7    | Landing page               | Default landing page is **Overview**.                                       |
| F8    | Last updated               | Show generation datetime \+ HEAD commit hash and commit time.               |
| F9    | Progress visibility        | Step-based progress, timestamped running log, live updates.                 |
| F10   | Event streaming            | SSE or WebSocket with job ID and timestamps.                                |
| F11   | Q\&A assistant             | Ask questions with follow-ups and scoping.                                  |
| F12   | Mandatory disclaimer       | Every AI-generated wiki section and Q\&A answer must state it may be wrong. |
| F13   | Mandatory citations (Q\&A) | Every answer must cite code, notes, or artifacts.                           |
| F14   | Evidence gating            | Default Q\&A mode is evidence-gated; optional Loose mode with warning.      |
| F15   | Provenance viewer          | Click citations to view code snippets or notes with commit context.         |
| F16   | In-UI corrections          | Markdown editor; users never manage files manually.                         |
| F17   | Notes metadata             | Datetime, inferred author (git/OS), git context, scope, target.             |
| F18   | Notes precedence           | Notes override AI inference in wiki and Q\&A.                               |
| F19   | Post-note reconciliation   | Regenerate affected content and ask for confirmation.                       |
| F20   | Mermaid diagrams           | Polished theme; editable; saved as artifacts or notes.                      |
| F21   | Provider config            | OpenAI, Anthropic, Gemini keys; model selection.                            |
| F22   | Ollama fallback            | Local Ollama endpoint and model support.                                    |
| F23   | Secrets handling           | Secrets never committed; ignored by default.                                |
| F24   | Search                     | Search across wiki and notes.                                               |
| F25   | Failure handling           | Partial results retained and clearly labeled.                               |
| F26   | Licensing                  | Only permissive open-source dependencies; license report required.          |

---

## **6\. Information Architecture (Canonical)**

**Hierarchy**

1. Overview
2. Architecture (single canonical page)
3. Workflows (inferred, user-correctable)
4. Key Directories (purpose-driven pages)
5. Files (structured summaries)
6. Notes (human corrections)

---

## **7\. Data & Storage Model**

### **7.1 Directory Layout**

`.oyawiki/`  
  `.gitignore  (committable)`
  `wiki/        (committable)`  
  `notes/       (committable)`  
  `meta/        (committable)`  
  `config/`  
    `settings.json (committable, non-secret)`  
    `secrets.*     (gitignored)`  
  `index/       (ephemeral, gitignored)`  
  `cache/       (ephemeral, gitignored)`

### **7.2 Committable vs Ephemeral**

* Wiki pages, notes, and metadata are designed to be committed.
* Indexes, embeddings, and caches are ephemeral and rebuildable.
* UI must render from committed artifacts alone.

---

## **8\. Notes Format (Minimum)**

Markdown with frontmatter including:

* datetime (ISO 8601\)
* author (auto-detected from git config or OS)
* scope (file / directory / workflow / architecture / general)
* target (path or slug)
* git context (branch, commit hash, dirty flag)
* Oya version

---

## **9\. Non-Functional Requirements**

* **Performance:** incremental regeneration preferred

* **Reliability:** resumable jobs; heartbeat events

* **Security:** localhost binding; no secret logging

* **Accessibility:** keyboard navigation; responsive layout

* **Determinism:** citations pinned to commit hash

---

## **10\. RAID**

**Risks**

* Hallucinations → mitigated by evidence gating, notes precedence
* Git churn → mitigated by committable/ephemeral split
* Large repos → mitigated by scoping, defaults, progress UI

**Assumptions**

* Single-user, local usage
* Git is the source of truth

**Dependencies**

* Docker
* LLM providers or Ollama

---

## **11\. Glossary**

* **Wiki:** Generated documentation under `.oyawiki/wiki/`  
* **Notes:** Human corrections under `.oyawiki/notes/`  
* **Evidence-gated:** Answers only when sufficient sources exist  
* **Loose mode:** Best-effort answers with explicit warning  
* **Provenance viewer:** UI showing cited sources
