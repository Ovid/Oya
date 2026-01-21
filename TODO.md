# TODO

* Q&A
    * The text input should be a text area.
    * Users should be able to use standard `@` functionality to provide exact
      context. This implies we actually have a checkout. Should this use RLM?
* Investigate RLM (Recursive Language Models for "unlimited" context)
    * https://arxiv.org/abs/2512.24601
    * https://www.youtube.com/watch?v=huszaaJPjU8
* CLI? "oya ask 'How does X work?'"
* Need to start a proper ChangeLog.
* We're using ChromaDB's default embeddings. That's OK for prototyping, but
  for prod, we need users to be able to specify the embedding model they want.
* "Ask" should be disabled while generating wiki
* Review code to see if it's making language/framework/tool, etc. assumptions
  which violate the "generic analysis" rule.
* Test suite hitting openai (possibly). Validate and then have ways to skip
  those tests unless requested.
    * Remove provider from .env and see if tests pass
    * Look at LLM as a Judge for some tests.
* When I first generate, it has a spinner for the entire time of the analysis
  phase (I think).
    * It needs to load the interface, *then* start analysis and have a time.
    * Also, later phases need steps, too.
    * Should show "current file" and "current directory" while processing.
    * Should it also try to process files in dependency order like
      directories?
    * Mermaid diagrams should omit test files
* "Are there any architectural flaws in the frontend?" DeepWiki caught one. We
  missed it. Investigate it. Check the jsonl logs and feed it back.
* Have AI use the vector database and code to independently validate logic and
  behavior.
* b6d4122 - If we delete .oyawiki while server is running, it dies on
  rebuild due to bad db connection (16 hours ago) <Ovid>
* We no longer have incremental regeneration. Need a better strategy, while
  still allowing atomic regeneration.

* Interface:
    - Templates (done)
    - Need left and right search areas to be "widenable" so I can see more
      content (done)
    - Proper filenames on left side
    - lib/MooseX/Extended/Core.pm showing nothing
    - Prompt injections!
    - Notes: we should have a single note per file, directory, and it can be
      edited.
    - Auto-create .oyaignore with appropriate files (not done: too many
      programming languages, so not done yet. Do it for popular languages?)
* Allow optional web search? Might pull in more context. Might pull in a mess.
* Where to put .oyawiki if not using current repo? Currently puts the docs in
  that repo.
    * What if two repos share the same name?
    * Local Wiki metadata and remove ephemeral data so we can easily serve it?
* The wiki generation might overprioritize docs over code. I'm not sure. Check
  if this is the case.
* Config files for removing hard-coded data.
* Templates for doc creation? Not sure if they're used, but would standardize
* some output. Not sure if they're appropriate.
* Fix the LLM chat
* WHEN I REFRESH PAGE, REGENERATION STOPS!

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

* .oyaignore is now in .oyawiki/.oyaignore
* To save token costs and time, we don't need to regenerate a particular file or
  directory if:
    - Files: file hasn't changed (unless a new note is applied)
    - Directories: directory contents haven't changed (same number of files and all files in it unchanged)
* Where's my dark mode?
* Before generating:
    - Preview directories and files so you can see what will be indexed and
      what should be in .oyaignore
    - Offer explanation of codebase, if needed, to help guide AI
* Constants into config file (not .env)
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
    * There will always be a button availabe in modal to regenerate wiki.
      Generation does not start until that button is clicked, but now there's
      going to be a confirmation dialog. Reuse confirmation logic already in
      system.
    * While regenerating, the "Ask" Q&A functionality must be disabled.
* Need to make chat more useful
    * Have chat persist, even when navigating.
    * Allow follow-up questions
* faa427b - (HEAD -> ovid/fix-missing-spec-issues) Move .oyaignore back to
  root directory (15 hours ago) <Ovid>
