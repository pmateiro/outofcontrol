---
name: daily-planning
description: Use when the user wants to plan their day, prioritize tasks, or schedule focus blocks on the calendar.
---

# Daily planning

1. Ask (or infer) the date and timezone if missing.
2. Call `calendar_list` for that day.
3. Propose 3–5 time blocks with clear titles.
4. On approval, create events with `calendar_add` (set `remind_minutes_before` when useful, e.g. `[60, 15]`).
5. Keep blocks realistic; include breaks.
6. Reminders fire via `outofcontrol watch` (background), not during chat.
