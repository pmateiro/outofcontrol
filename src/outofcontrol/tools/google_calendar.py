from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import httpx

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec


def _token() -> str | None:
    return os.environ.get("GOOGLE_CALENDAR_ACCESS_TOKEN") or os.environ.get(
        "OOC_GOOGLE_CALENDAR_ACCESS_TOKEN"
    )


def _calendar_id() -> str:
    return os.environ.get("GOOGLE_CALENDAR_ID", "primary")


def register_google_calendar_tools(registry: ToolRegistry) -> None:
    def gcal_status() -> ToolResult:
        tok = _token()
        if not tok:
            return ToolResult(
                ok=False,
                output=(
                    "Google Calendar not configured. Set GOOGLE_CALENDAR_ACCESS_TOKEN "
                    "(OAuth access token with calendar scope). Optional GOOGLE_CALENDAR_ID "
                    "(default: primary). Local calendar_* tools still work without this."
                ),
            )
        return _api("GET", f"/calendars/{quote(_calendar_id(), safe='')}", tok)

    def gcal_list(time_min: str | None = None, time_max: str | None = None, max_results: int = 20) -> ToolResult:
        tok = _token()
        if not tok:
            return gcal_status()
        now = datetime.now(timezone.utc)
        params = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": str(max_results),
            "timeMin": time_min or now.isoformat().replace("+00:00", "Z"),
            "timeMax": time_max
            or (now + timedelta(days=14)).isoformat().replace("+00:00", "Z"),
        }
        cal = quote(_calendar_id(), safe="")
        return _api("GET", f"/calendars/{cal}/events", tok, params=params)

    def gcal_add(
        summary: str,
        start: str,
        end: str | None = None,
        description: str = "",
    ) -> ToolResult:
        tok = _token()
        if not tok:
            return gcal_status()
        # Accept date or datetime; date-only → all-day
        body: dict[str, Any] = {"summary": summary, "description": description}
        if "T" in start:
            body["start"] = {"dateTime": start}
            body["end"] = {"dateTime": end or start}
        else:
            body["start"] = {"date": start}
            body["end"] = {"date": end or start}
        cal = quote(_calendar_id(), safe="")
        return _api("POST", f"/calendars/{cal}/events", tok, json_body=body)

    def gcal_delete(event_id: str) -> ToolResult:
        tok = _token()
        if not tok:
            return gcal_status()
        cal = quote(_calendar_id(), safe="")
        return _api("DELETE", f"/calendars/{cal}/events/{quote(event_id, safe='')}", tok)

    for name, desc, params, handler in [
        (
            "gcal_status",
            "Check Google Calendar configuration / access.",
            {"type": "object", "properties": {}},
            gcal_status,
        ),
        (
            "gcal_list",
            "List Google Calendar events (requires GOOGLE_CALENDAR_ACCESS_TOKEN).",
            {
                "type": "object",
                "properties": {
                    "time_min": {"type": "string"},
                    "time_max": {"type": "string"},
                    "max_results": {"type": "integer", "default": 20},
                },
            },
            gcal_list,
        ),
        (
            "gcal_add",
            "Create a Google Calendar event.",
            {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "start": {"type": "string", "description": "ISO date or dateTime"},
                    "end": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["summary", "start"],
            },
            gcal_add,
        ),
        (
            "gcal_delete",
            "Delete a Google Calendar event by id.",
            {
                "type": "object",
                "properties": {"event_id": {"type": "string"}},
                "required": ["event_id"],
            },
            gcal_delete,
        ),
    ]:
        registry.register(ToolSpec(name=name, description=desc, parameters=params, handler=handler))


def _api(
    method: str,
    path: str,
    token: str,
    *,
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> ToolResult:
    url = f"https://www.googleapis.com/calendar/v3{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.request(method, url, headers=headers, params=params, json=json_body)
            if method == "DELETE" and r.status_code in (200, 204):
                return ToolResult(ok=True, output="Deleted")
            text = r.text or "(empty)"
            if len(text) > 30_000:
                text = text[:30_000] + "\n...[truncated]"
            if r.status_code >= 400:
                return ToolResult(ok=False, output=f"Google Calendar API {r.status_code}: {text}")
            # pretty if json
            try:
                text = json.dumps(r.json(), ensure_ascii=False, indent=2)
            except Exception:  # noqa: BLE001
                pass
            return ToolResult(ok=True, output=text)
    except Exception as e:  # noqa: BLE001
        return ToolResult(ok=False, output=f"Google Calendar error: {e}")
