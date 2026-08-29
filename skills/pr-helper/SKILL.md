---
name: pr-helper
description: Use when creating, reviewing, or merging pull requests and checking CI status.
---

# PR helper

1. Ensure changes are committed (load `git-workflow` if needed).
2. `github_pr_create` with a clear title/body (draft by default).
3. `github_ci_list` / `github_ci_view` (or `github_pr_view`) to check status.
4. For long waits, `github_ci_watch` only when the user wants blocking wait.
5. `github_pr_merge` requires confirmation — summarize checks first.
6. Never force-push or merge with failing required checks unless the user explicitly insists.
