---
name: repo-edit
description: Use when changing code in the workspace — searching, reading, surgical edits, and running checks.
---

# Repo edit

1. Orient with `glob_files` / `grep` / `list_dir` before editing.
2. `read_file` the target, then prefer `edit_file` for surgical changes.
3. Use `write_file` only for new files or full rewrites.
4. `delete_file` requires confirmation — explain why first.
5. Run tests/linters via `run_shell` when relevant.
6. For git commits/pushes, load skill `git-workflow`.
7. Summarize what changed and how to verify.
