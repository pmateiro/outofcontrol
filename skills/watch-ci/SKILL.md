---
name: watch-ci
description: Use when the user wants to check or wait on GitHub Actions / CI for a branch or PR.
---

# Watch CI

1. `github_ci_list` for recent runs (filter mentally by branch/PR).
2. `github_ci_view` on the relevant run_id for details.
3. Use `github_ci_watch` only if the user wants a blocking wait.
4. Summarize conclusion (success/failure) and failing job names if any.
5. On failure, suggest next debug steps (logs, re-run, local repro).
