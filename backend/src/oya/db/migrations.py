"""Database migrations and schema management for Oya."""

from oya.db.connection import Database

# Schema version for tracking migrations
SCHEMA_VERSION = 6

SCHEMA_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Generation job tracking
-- Tracks wiki generation jobs: status, progress, timing, and which commit was indexed
CREATE TABLE IF NOT EXISTS generations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- 'full', 'incremental', 'page'
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'running', 'completed', 'failed'
    started_at TEXT,
    completed_at TEXT,
    commit_hash TEXT,  -- Git commit that was indexed
    current_phase TEXT,  -- For progress tracking
    total_phases INTEGER,
    current_step INTEGER,  -- Step within current phase (e.g., file 3 of 20)
    total_steps INTEGER,  -- Total steps in current phase
    error_message TEXT,
    metadata TEXT,  -- JSON for additional data
    changes_made INTEGER  -- Boolean: whether any content was regenerated
);

-- Wiki page metadata
-- Stores metadata about each generated wiki page
CREATE TABLE IF NOT EXISTS wiki_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,  -- File path relative to .oyawiki/wiki/
    type TEXT NOT NULL,  -- 'overview', 'architecture', 'workflow', 'directory', 'file'
    target TEXT,  -- Target path for file/directory pages
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    generation_id TEXT REFERENCES generations(id),
    commit_hash TEXT,  -- Commit when page was generated
    word_count INTEGER,
    status TEXT NOT NULL DEFAULT 'complete',  -- 'complete', 'incomplete', 'error'
    metadata TEXT  -- JSON for additional data
);

-- Notes registry (human corrections)
-- One note per (scope, target) pair - upsert semantics
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,  -- 'file', 'directory', 'workflow', 'general'
    target TEXT NOT NULL,  -- Target path or identifier (empty string for general)
    filepath TEXT NOT NULL,  -- Path relative to .oyawiki/notes/
    content TEXT NOT NULL,  -- Note content (markdown)
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    author TEXT,
    UNIQUE(scope, target)
);

-- Citations mapping wiki content to source code
-- Links generated content back to specific code locations
CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wiki_page_id INTEGER NOT NULL REFERENCES wiki_pages(id) ON DELETE CASCADE,
    source_file TEXT NOT NULL,  -- Path to source file
    start_line INTEGER,
    end_line INTEGER,
    commit_hash TEXT,  -- Commit when citation was created
    citation_type TEXT NOT NULL DEFAULT 'code',  -- 'code', 'comment', 'doc', 'note'
    snippet TEXT,  -- Cached snippet of cited content
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Full-text search index using FTS5
-- Enables fast keyword search across wiki pages and notes
-- Supports chunk-level indexing for RAG with section headers and chunk metadata
CREATE VIRTUAL TABLE IF NOT EXISTS fts_content USING fts5(
    content,  -- The searchable text content
    title,    -- Page or note title
    path UNINDEXED,     -- Path for linking back (not indexed, just stored)
    type UNINDEXED,     -- 'wiki' or 'note' (not indexed, just stored)
    section_header,     -- Section header for searching by section name
    chunk_id UNINDEXED,    -- Unique identifier for RRF merging with vector search
    chunk_index UNINDEXED, -- Position in document for context reconstruction
    content_rowid UNINDEXED  -- Reference to wiki_pages.id or notes.id
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_wiki_pages_type ON wiki_pages(type);
CREATE INDEX IF NOT EXISTS idx_wiki_pages_target ON wiki_pages(target);
CREATE INDEX IF NOT EXISTS idx_notes_scope_target ON notes(scope, target);
CREATE INDEX IF NOT EXISTS idx_citations_wiki_page ON citations(wiki_page_id);
CREATE INDEX IF NOT EXISTS idx_citations_source_file ON citations(source_file);
CREATE INDEX IF NOT EXISTS idx_generations_status ON generations(status);
"""


def run_migrations(db: Database) -> None:
    """Run database migrations to set up or upgrade schema.

    Args:
        db: Database connection to run migrations on.
    """
    # Check current schema version
    try:
        result = db.execute(
            "SELECT version FROM schema_version ORDER BY version DESC LIMIT 1"
        ).fetchone()
        current_version = result[0] if result else 0
    except Exception:
        # Table doesn't exist yet
        current_version = 0

    if current_version < SCHEMA_VERSION:
        # Version 4 migration: Recreate FTS table with chunk columns
        # FTS5 CREATE VIRTUAL TABLE IF NOT EXISTS won't update existing table schema,
        # so we need to drop first, then recreate via SCHEMA_SQL below
        if current_version >= 1 and current_version < 4:
            try:
                db.execute("DROP TABLE IF EXISTS fts_content")
                db.commit()
            except Exception:
                pass

        # Version 6 migration: Recreate notes table with new schema
        # Must drop before executescript since CREATE TABLE IF NOT EXISTS won't update
        if current_version >= 1 and current_version < 6:
            try:
                db.execute("DROP TABLE IF EXISTS notes")
                db.commit()
            except Exception:
                pass

        # Apply schema using executescript which handles multiple statements
        # Note: executescript auto-commits, so we handle the version insert separately
        db.executescript(SCHEMA_SQL)

        # Version 3 migration: Add step tracking columns to generations table
        if current_version >= 1 and current_version < 3:
            try:
                db.execute("ALTER TABLE generations ADD COLUMN current_step INTEGER")
                db.execute("ALTER TABLE generations ADD COLUMN total_steps INTEGER")
                db.commit()
            except Exception:
                # Columns may already exist if schema was recreated
                pass

        # Version 5 migration: Add changes_made column to generations table
        if current_version >= 1 and current_version < 5:
            try:
                db.execute("ALTER TABLE generations ADD COLUMN changes_made INTEGER")
                db.commit()
            except Exception:
                # Column may already exist if schema was recreated
                pass

        # Record schema version
        db.execute(
            "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        db.commit()
