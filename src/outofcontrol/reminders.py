from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

from dateutil import parser as date_parser

from outofcontrol.tools.calendar import (
    DEFAULT_REMIND_MINUTES,
    load_events,
    save_events,
)


NotifyFn = Callable[[str, str, dict[str, Any]], None]


@dataclass(frozen=True)
class DueReminder:
    event: dict[str, Any]
    minutes_before: int
    remind_at: datetime
    start: datetime


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def _event_reminders(event: dict[str, Any], defaults: list[int]) -> list[int]:
    raw = event.get("remind_minutes_before")
    if raw is None:
        return list(defaults)
    return sorted({int(m) for m in raw if int(m) >= 0}, reverse=True)


def find_due_reminders(
    events: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    defaults: list[int] | None = None,
    grace_after_start_minutes: int = 5,
) -> list[DueReminder]:
    """Return reminders that should fire now (and have not been sent yet)."""
    now = _aware(now or datetime.now().astimezone())
    defaults = list(defaults or DEFAULT_REMIND_MINUTES)
    grace = timedelta(minutes=grace_after_start_minutes)
    due: list[DueReminder] = []

    for event in events:
        try:
            start = _aware(date_parser.isoparse(event["start"]))
        except (KeyError, TypeError, ValueError):
            continue
        sent = {int(x) for x in event.get("reminders_sent") or []}
        for minutes in _event_reminders(event, defaults):
            if minutes in sent:
                continue
            remind_at = start - timedelta(minutes=minutes)
            # Fire once the remind time has passed, until shortly after the event starts.
            if remind_at <= now <= start + grace:
                due.append(
                    DueReminder(
                        event=event,
                        minutes_before=minutes,
                        remind_at=remind_at,
                        start=start,
                    )
                )
    due.sort(key=lambda d: (d.remind_at, d.event.get("id", ""), d.minutes_before))
    return due


def mark_reminder_sent(event: dict[str, Any], minutes_before: int) -> None:
    sent = [int(x) for x in event.get("reminders_sent") or []]
    if minutes_before not in sent:
        sent.append(minutes_before)
        event["reminders_sent"] = sorted(sent, reverse=True)


def format_reminder_body(item: DueReminder) -> str:
    when = item.start.strftime("%Y-%m-%d %H:%M")
    if item.minutes_before == 0:
        lead = "Começando agora"
    else:
        lead = f"Em {item.minutes_before} min"
    notes = (item.event.get("notes") or "").strip()
    lines = [f"{lead} — {when}"]
    if notes:
        lines.append(notes)
    return "\n".join(lines)


def notify_console(title: str, body: str, _event: dict[str, Any]) -> None:
    print(f"[reminder] {title}\n{body}\n", flush=True)


def notify_desktop(title: str, body: str, _event: dict[str, Any]) -> None:
    binary = shutil.which("notify-send")
    if not binary:
        return
    try:
        subprocess.run(
            [binary, "--app-name=OutOfControl", title, body],
            check=False,
            timeout=5,
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        return


def notify_webhook(webhook_url: str) -> NotifyFn:
    def _send(title: str, body: str, event: dict[str, Any]) -> None:
        payload = json.dumps(
            {
                "title": title,
                "body": body,
                "event": {
                    "id": event.get("id"),
                    "title": event.get("title"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "notes": event.get("notes"),
                },
            },
            ensure_ascii=False,
        ).encode("utf-8")
        req = request.Request(
            webhook_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=10) as resp:
                resp.read()
        except error.URLError:
            return

    return _send


def build_notifiers(
    *,
    desktop: bool = True,
    webhook_url: str | None = None,
) -> list[NotifyFn]:
    notifiers: list[NotifyFn] = [notify_console]
    if desktop:
        notifiers.append(notify_desktop)
    if webhook_url:
        notifiers.append(notify_webhook(webhook_url))
    return notifiers


def tick(
    calendar_path: Path,
    *,
    now: datetime | None = None,
    defaults: list[int] | None = None,
    notifiers: list[NotifyFn] | None = None,
) -> list[DueReminder]:
    """Check calendar once, notify due reminders, persist reminders_sent."""
    events = load_events(calendar_path)
    due = find_due_reminders(events, now=now, defaults=defaults)
    if not due:
        return []

    by_id = {e.get("id"): e for e in events}
    channels = notifiers or build_notifiers()
    fired: list[DueReminder] = []

    for item in due:
        event = by_id.get(item.event.get("id"))
        if event is None:
            continue
        # Re-check in case of duplicate due rows for same event/minutes
        sent = {int(x) for x in event.get("reminders_sent") or []}
        if item.minutes_before in sent:
            continue
        title = str(event.get("title") or "Compromisso")
        body = format_reminder_body(item)
        for notify in channels:
            notify(title, body, event)
        mark_reminder_sent(event, item.minutes_before)
        fired.append(item)

    if fired:
        save_events(calendar_path, events)
    return fired


def run_loop(
    calendar_path: Path,
    *,
    interval_seconds: float = 60.0,
    defaults: list[int] | None = None,
    notifiers: list[NotifyFn] | None = None,
    once: bool = False,
    sleep_fn: Callable[[float], None] | None = None,
) -> None:
    import time

    sleeper = sleep_fn or time.sleep
    while True:
        tick(calendar_path, defaults=defaults, notifiers=notifiers)
        if once:
            return
        sleeper(interval_seconds)
