# TODO

* Auto-create .oyaignore with appropriate files.
* Templates for doc creation? Not sure if they're used, but would standardize
* some output. Not sure if they're appropriate.
* .oyaignore should be in .oyawiki
* Fix the LLM chat
* Where's my dark mode?
* Local Wiki metadata and remove ephemeral data so we can easily serve it?
* WHEN I REFRESH PAGE, REGENERATION STOPS!

# Done

To save token costs and time, we don't need to regenerate a particular file or
directory if:
    - Files: file hasn't changed (unless a new note is applied)
    - Directories: directory contents haven't changed (same number of files and all files in it unchanged)

