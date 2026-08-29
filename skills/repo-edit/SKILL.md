---
name: repo-edit
description: Use when changing code in the workspace — reading, searching, editing files, and running checks.
---

# Repo edit

1. `list_dir` / `search_files` / `read_file` before editing.
2. Prefer small, targeted `write_file` changes.
3. Run tests or linters via `run_shell` when relevant.
4. Summarize what changed and how to verify.
5. Treat destructive git/shell ops as sensitive (confirmation required).
