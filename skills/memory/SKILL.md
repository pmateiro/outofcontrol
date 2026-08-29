---
name: memory
description: Use when the user asks to remember preferences, facts, or lasting context across sessions.
---

# Memory

1. When asked to remember something durable, call `memory_set` with a short `key` and clear `content`.
2. Before answering preference/history questions, try `memory_get` or `memory_list`.
3. Update existing keys instead of duplicating near-identical notes.
4. Do not store secrets (API keys, passwords) in memory.
5. Confirm briefly what was saved.
