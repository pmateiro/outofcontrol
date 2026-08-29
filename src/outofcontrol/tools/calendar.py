from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from dateutil import parser as date_parser

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec

DEFAULT_REMIND_MINUTES = [60, 15]


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_events(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


def register_calendar_tools(
    registry: ToolRegistry,
    *,
    calendar_path: Path,
    default_remind_minutes: list[int] | None = None,
) -> None:
    defaults = list(default_remind_minutes or DEFAULT_REMIND_MINUTES)

    def calendar_list(from_iso: str | None = None, to_iso: str | None = None) -> ToolResult:
        events = load_events(calendar_path)
        start = date_parser.isoparse(from_iso) if from_iso else None
        end = date_parser.isoparse(to_iso) if to_iso else None
        filtered = []
        for ev in events:
            when = date_parser.isoparse(ev["start"])
            if start and when < start:
                continue
            if end and when > end:
                continue
            filtered.append(ev)
        filtered.sort(key=lambda e: e["start"])
        return ToolResult(ok=True, output=json.dumps(filtered, ensure_ascii=False, indent=2))

    def calendar_add(
        title: str,
        start: str,
        end: str | None = None,
        notes: str = "",
        remind_minutes_before: list[int] | None = None,
    ) -> ToolResult:
        start_dt = date_parser.parse(start)
        end_dt = date_parser.parse(end) if end else None
        reminders = (
            list(remind_minutes_before)
            if remind_minutes_before is not None
            else list(defaults)
        )
        reminders = sorted({int(m) for m in reminders if int(m) >= 0}, reverse=True)
        events = load_events(calendar_path)
        event = {
            "id": str(uuid.uuid4()),
            "title": title,
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat() if end_dt else None,
            "notes": notes,
            "remind_minutes_before": reminders,
            "reminders_sent": [],
            "created_at": datetime.now().astimezone().isoformat(),
        }
        events.append(event)
        save_events(calendar_path, events)
        return ToolResult(ok=True, output=json.dumps(event, ensure_ascii=False, indent=2))

    def calendar_delete(event_id: str) -> ToolResult:
        events = load_events(calendar_path)
        new_events = [e for e in events if e.get("id") != event_id]
        if len(new_events) == len(events):
            return ToolResult(ok=False, output=f"Event not found: {event_id}")
        save_events(calendar_path, new_events)
        return ToolResult(ok=True, output=f"Deleted event {event_id}")

    registry.register(
        ToolSpec(
            name="calendar_list",
            description="List local calendar events, optionally filtered by ISO date range.",
            parameters={
                "type": "object",
                "properties": {
                    "from_iso": {"type": "string"},
                    "to_iso": {"type": "string"},
                },
            },
            handler=calendar_list,
        )
    )
    registry.register(
        ToolSpec(
            name="calendar_add",
            description=(
                "Add an event to the local calendar store. "
                "Optional remind_minutes_before (e.g. [60, 15]) controls desktop/watch alerts."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "start": {
                        "type": "string",
                        "description": "Start datetime (ISO or natural language parseable)",
                    },
                    "end": {"type": "string"},
                    "notes": {"type": "string"},
                    "remind_minutes_before": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Minutes before start to notify (default [60, 15])",
                    },
                },
                "required": ["title", "start"],
            },
            handler=calendar_add,
        )
    )
    registry.register(
        ToolSpec(
            name="calendar_delete",
            description="Delete a calendar event by id.",
            parameters={
                "type": "object",
                "properties": {"event_id": {"type": "string"}},
                "required": ["event_id"],
            },
            handler=calendar_delete,
        )
    )
