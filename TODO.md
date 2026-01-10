# TODO

* Interface:
    - Templates
    - Need left and right search areas to be "widenable" so I can see more
      content
    - Proper filenames on left side
    - lib/MooseX/Extended/Core.pm showing nothing
    - Prompt injections!
    * Auto-create .oyaignore with appropriate files (not done: too many
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

# Done

* .oyaignore is now in .oyawiki/.oyaignore
* To save token costs and time, we don't need to regenerate a particular file or
  directory if:
    - Files: file hasn't changed (unless a new note is applied)
    - Directories: directory contents haven't changed (same number of files and all files in it unchanged)
* Where's my dark mode?
