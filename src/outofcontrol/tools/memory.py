from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec


def _load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"notes": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"notes": []}
    data.setdefault("notes", [])
    return data


def _save(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def register_memory_tools(registry: ToolRegistry, *, memory_path: Path) -> None:
    def memory_list(query: str | None = None) -> ToolResult:
        notes = _load(memory_path)["notes"]
        if query:
            q = query.lower()
            notes = [
                n
                for n in notes
                if q in n.get("key", "").lower() or q in n.get("content", "").lower()
            ]
        # compact listing
        lines = [
            f"- [{n['id'][:8]}] {n.get('key')}: {n.get('content', '')[:120]}"
            for n in notes
        ]
        return ToolResult(ok=True, output="\n".join(lines) or "(no memories)")

    def memory_get(key: str) -> ToolResult:
        notes = _load(memory_path)["notes"]
        matches = [n for n in notes if n.get("key") == key]
        if not matches:
            return ToolResult(ok=False, output=f"No memory with key={key!r}")
        return ToolResult(ok=True, output=json.dumps(matches, ensure_ascii=False, indent=2))

    def memory_set(key: str, content: str) -> ToolResult:
        data = _load(memory_path)
        now = datetime.now(timezone.utc).isoformat()
        existing = next((n for n in data["notes"] if n.get("key") == key), None)
        if existing:
            existing["content"] = content
            existing["updated_at"] = now
            note = existing
        else:
            note = {
                "id": str(uuid.uuid4()),
                "key": key,
                "content": content,
                "created_at": now,
                "updated_at": now,
            }
            data["notes"].append(note)
        _save(memory_path, data)
        return ToolResult(ok=True, output=json.dumps(note, ensure_ascii=False, indent=2))

    def memory_delete(key: str) -> ToolResult:
        data = _load(memory_path)
        before = len(data["notes"])
        data["notes"] = [n for n in data["notes"] if n.get("key") != key]
        if len(data["notes"]) == before:
            return ToolResult(ok=False, output=f"No memory with key={key!r}")
        _save(memory_path, data)
        return ToolResult(ok=True, output=f"Deleted memory key={key!r}")

    registry.register(
        ToolSpec(
            name="memory_list",
            description="List persisted memories/notes (optional substring query).",
            parameters={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
            handler=memory_list,
        )
    )
    registry.register(
        ToolSpec(
            name="memory_get",
            description="Get memory note(s) by exact key.",
            parameters={
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
            handler=memory_get,
        )
    )
    registry.register(
        ToolSpec(
            name="memory_set",
            description="Create or update a memory note by key (persists across sessions).",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["key", "content"],
            },
            handler=memory_set,
        )
    )
    registry.register(
        ToolSpec(
            name="memory_delete",
            description="Delete a memory note by key.",
            parameters={
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
            handler=memory_delete,
        )
    )
