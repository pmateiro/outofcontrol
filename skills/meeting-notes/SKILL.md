---
name: meeting-notes
description: Use when extracting action items from meeting notes and creating local tasks (or GitHub issues when appropriate).
---

# Meeting notes → tasks

1. Read the notes (file or pasted text).
2. Extract concrete action items: owner, due date if any, verb+object.
3. Create each with `task_add` (set `assignee`, `due`, `source`).
4. If an item is clearly an engineering bug/feature for a repo, offer `github_issue_create` instead/in addition.
5. Return a bullet list of what was created (task ids / issue urls).
