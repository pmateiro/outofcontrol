---
name: triage-issue
description: Use when triaging a bug report or error — search similar GitHub issues, summarize, and optionally create or comment.
---

# Triage issue

1. Clarify the symptom (error text, repro, expected vs actual).
2. `github_issue_list` with a search query for duplicates / related issues.
3. `github_issue_view` on promising matches.
4. If duplicate: point to the existing issue and suggest next steps.
5. If new: draft a clear title/body and `github_issue_create` (ask before creating if unsure).
6. Prefer facts over speculation; include environment clues when available.
