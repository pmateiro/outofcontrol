---
name: git-workflow
description: Use for git status, diff, commit, branch, and push workflows. Prefer small commits; treat push/reset --hard as sensitive.
---

# Git workflow

1. Start with `run_shell` for `git status` and `git diff` (and `git log -5 --oneline` if useful).
2. Never commit secrets (`.env`, keys, tokens).
3. Stage intentionally (`git add` specific paths), then commit with a clear message.
4. `git push` and `git reset --hard` require confirmation — warn the user and use the confirmation flow.
5. Prefer creating/switching feature branches over committing straight to main when the repo is shared.
6. After committing, summarize changed files and the commit subject.
7. If hooks fail, fix the issue; do not `--no-verify` unless the user explicitly asks.
