# TODO

## Q&A / Chat

* Q&A should allow follow-up questions, not just one-shot
* Q&A should have an "arrow up" history
* Q&A: Not scrolling down for successive answers
* The text input should be a text area
* "Ask" should be disabled while generating wiki
* We should be able to use `@` syntax for specifying files or directories for
  additional context. Would be nice if it could auto-complete for current wiki
  (optional).

## Wiki Generation

* When generating, if I refresh the page, all counters reset to 0s.
* Generated wiki, hit refresh, and it started regenerating. Files dropdown
  said 47, but there were only 7 files shown.
* When generation is done, it must direct back to the overview page.
* WHEN I REFRESH PAGE, REGENERATION STOPS!
* When I first generate, it has a spinner for the entire time of the analysis
  phase (I think).
    * It needs to load the interface, *then* start analysis and have a timer.
    * Also, later phases need steps, too.
    * Should show "current file" and "current directory" while processing.
    * Should it also try to process files in dependency order like directories?
* Load code in reverse dependency order, if feasible. That lets us load
  "top-level" modules and have context for lower-level modules.
* We no longer have incremental regeneration. Need a better strategy, while
  still allowing atomic regeneration.
* The wiki generation might overprioritize docs over code. I'm not sure. Check
  if this is the case.
* Mermaid diagrams should omit test files
* When regenerating and showing what can be excluded, it shouldn't show any
  files if a directory above it is already excluded. Makes the lists much shorter.

## UI / Interface

* When I restart the server, I go to "Add your first repository" page, even when
  the page is valid, such as
  http://localhost:5173/directories/backend-src-oya-data. Refreshing the page
  gets me to the correct wiki page.
* lib/MooseX/Extended/Core.pm showing nothing
* Prompt injections!
* Fix the LLM chat
* Allow optional web search? Might pull in more context. Might pull in a mess.

## Data / Storage

* code_index UNIQUE(file_path, symbol_name) loses data when a file has duplicate
  symbol names in different scopes (e.g. two classes each with `__init__` or
  `process`). INSERT OR REPLACE silently overwrites the first entry. Consider
  including scope/class qualification in symbol_name or adding line_start to
  the unique constraint.
* No need for .dotfiles and .dotdirs inside of the ~/.oya directory:
    ./wikis/github.com/Ovid/Oya/meta/.oyaignore
    ./wikis/github.com/Ovid/Oya/meta/.oyawiki
    ./wikis/github.com/Ovid/Oya/meta/.oya-logs
* b6d4122 - If we delete .oyawiki while server is running, it dies on
  rebuild due to bad db connection
* Where to put .oyawiki if not using current repo? Currently puts the docs in
  that repo.
    * What if two repos share the same name?
    * Local Wiki metadata and remove ephemeral data so we can easily serve it?

## Repository Management

* Need to be able to delete a repo from Oya

## Deep Research / CGRAG

* backend/src/oya/qa/cgrag.py def \_read_source_for_nodes(
    * This could blow our context window
* CGRAG should also be able to read files now. However, we need to be
  concerned about blowing context
* Extend CGRAG:
    * "Thorough" shouldn't mention additional files
    * "Deep Research" will
* Can't do it properly if I don't have the files
    * Need "wikis" directory
        * Handle github (including private repos)
        * Handle local directories
        * How to enforce distinction when repo names are the same?
* Investigate RLM (Recursive Language Models for "unlimited" context)
    * https://arxiv.org/abs/2512.24601
    * https://www.youtube.com/watch?v=huszaaJPjU8

## Code Quality / Architecture

* What other uses do we have for synthesis map? Can we use it to generate
  interesting reports? Find potential dead code?
* Check for any other places in the code where:
    * Errors are silently discarded
    * try/catch isn't robust or has a "pass"
* It's happy to duplicate code. It should search for similar functionality
  to what it's building and reuse when it can.
* GOD OBJECTS!
* Review code to see if it's making language/framework/tool assumptions
  which violate the "generic analysis" rule.
* "Are there any architectural flaws in the frontend?" DeepWiki caught one. We
  missed it. Investigate it. Check the jsonl logs and feed it back.
* Have AI use the vector database and code to independently validate logic and
  behavior.

## Testing

* Hit minimum code coverage standards and then enforce them.
* Test suite hitting openai (possibly). Validate and then have ways to skip
  those tests unless requested.
    * Remove provider from .env and see if tests pass
    * Look at LLM as a Judge for some tests.

## Configuration / Settings

* Even though the interface for Q&A shows temperature at .3, wiki generation
  shows 0.7. Perhaps they should be separate, but we really need some kind of
  "Settings" dialog to let people choose them.
* Config files for removing hard-coded data.
* We're using ChromaDB's default embeddings. That's OK for prototyping, but
  for prod, we need users to be able to specify the embedding model they want.
* Templates for doc creation? Not sure if they're used, but would standardize
  some output. Not sure if they're appropriate.

## Infrastructure / DevOps

* The logs can get quite long. Need something like logrotate.
* Need to add Windows support (paths)
* Fix this issue which slows us down and eats tokens when we start a worktree:

      ⏺ Bash(cd /Users/poecurt/projects/oya/.worktrees/collapse-excluded-dirs/backend &&
        python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]" -q 2>&…)
        ⎿  ERROR: Cannot install oya because these package versions have conflicting dependencies.
           ERROR: ResolutionImpossible...

  Worktrees share the git repo but not non-tracked files like .venv.

## Other / Misc

* Why wasn't my code quality reviewer chosen?
  > Review the code quality of the implementation for Task 1: Add
  > app\_settings table to repo\_registry.py
* CLI? "oya ask 'How does X work?'"
* Need to start a proper ChangeLog.

---

# Future Enhancements (Suggested by CLAUDE)

The following ideas were identified during Phase 6 overview improvements but deferred for future consideration:

## Advanced Code Metrics
- **Test coverage integration**: Detect and display coverage percentages when coverage tools (coverage.py, istanbul, etc.) have generated reports
- **Cyclomatic complexity**: Compute and surface complexity hotspots
- **Code quality scores**: Integration with linters/analyzers if configured

## Historical Context
- **Git history analysis**: Show project maturity, recent activity areas, contributor patterns
- **Change frequency**: Identify frequently-modified files (potential complexity indicators)

## README Intelligence
- **Section parsing**: Parse README into structured sections (Features, Installation, Usage) to better detect conflicts/redundancy with code-derived information
- **Staleness detection**: Compare README claims against actual code to flag potential outdated sections

---

# Done

## Q&A / Chat
* Need to make chat more useful
    * Have chat persist, even when navigating.
    * Allow follow-up questions

## Wiki Generation
* To save token costs and time, we don't need to regenerate a particular file or
  directory if:
    - Files: file hasn't changed (unless a new note is applied)
    - Directories: directory contents haven't changed (same number of files and all files in it unchanged)
* Mermaid diagrams should pass through a parser until they render correctly
* For each file we analyze, we should also look for common design flaws or
  possible bugs and put them in another part of the response. In other
  words, try to offload some of the hard work to the remote LLM.
* Generate Wiki
    * Remove "Preview" button in top bar.
    * Show modal with preview on Generate, but now all files/directories are
      checked and "included." Unchecking one will exclude it. Also make it
      clear which files are excluded via rules (those cannot be included) and
      via .oyaignore (we should be able to include those, and make it clear
      that .oyaignore will be rewritten).
    * There will always be a button available in modal to regenerate wiki.
      Generation does not start until that button is clicked, but now there's
      going to be a confirmation dialog. Reuse confirmation logic already in
      system.
    * While regenerating, the "Ask" Q&A functionality must be disabled.
* docs/plans/2026-01-28-call-site-synopses-design.md
* Code synopsis for files

## UI / Interface
* Templates (done)
* Need left and right search areas to be "widenable" so I can see more content
* Proper filenames on left side
* Notes: we should have a single note per file, directory, and it can be edited.
* Where's my dark mode?
* Before generating:
    - Preview directories and files so you can see what will be indexed and
      what should be in .oyaignore
    - Offer explanation of codebase, if needed, to help guide AI

## Data / Storage
* .oyaignore is now in .oyawiki/.oyaignore
* faa427b - Move .oyaignore back to root directory

## Configuration
* Constants into config file (not .env)
