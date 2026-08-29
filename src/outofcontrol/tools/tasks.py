from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from outofcontrol.tools.base import ToolRegistry, ToolResult, ToolSpec


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("tasks", [])


def _save(path: Path, tasks: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")


def register_task_tools(registry: ToolRegistry, *, tasks_path: Path) -> None:
    def task_list(status: str | None = None, assignee: str | None = None) -> ToolResult:
        tasks = _load(tasks_path)
        if status:
            tasks = [t for t in tasks if t.get("status") == status]
        if assignee:
            tasks = [t for t in tasks if t.get("assignee") == assignee]
        return ToolResult(ok=True, output=json.dumps(tasks, ensure_ascii=False, indent=2))

    def task_add(
        title: str,
        notes: str = "",
        assignee: str = "",
        due: str = "",
        source: str = "",
    ) -> ToolResult:
        tasks = _load(tasks_path)
        now = datetime.now(timezone.utc).isoformat()
        task = {
            "id": str(uuid.uuid4()),
            "title": title,
            "notes": notes,
            "assignee": assignee or None,
            "due": due or None,
            "status": "open",
            "source": source or None,
            "created_at": now,
            "updated_at": now,
        }
        tasks.append(task)
        _save(tasks_path, tasks)
        return ToolResult(ok=True, output=json.dumps(task, ensure_ascii=False, indent=2))

    def task_update(
        task_id: str,
        status: str | None = None,
        title: str | None = None,
        notes: str | None = None,
        assignee: str | None = None,
    ) -> ToolResult:
        tasks = _load(tasks_path)
        for t in tasks:
            if t.get("id") == task_id or t.get("id", "").startswith(task_id):
                if status is not None:
                    t["status"] = status
                if title is not None:
                    t["title"] = title
                if notes is not None:
                    t["notes"] = notes
                if assignee is not None:
                    t["assignee"] = assignee
                t["updated_at"] = datetime.now(timezone.utc).isoformat()
                _save(tasks_path, tasks)
                return ToolResult(ok=True, output=json.dumps(t, ensure_ascii=False, indent=2))
        return ToolResult(ok=False, output=f"Task not found: {task_id}")

    def task_delete(task_id: str) -> ToolResult:
        tasks = _load(tasks_path)
        new_tasks = [t for t in tasks if t.get("id") != task_id and not t.get("id", "").startswith(task_id)]
        # if prefix match unique
        if len(new_tasks) == len(tasks):
            matches = [t for t in tasks if t.get("id", "").startswith(task_id)]
            if len(matches) == 1:
                new_tasks = [t for t in tasks if t.get("id") != matches[0]["id"]]
            else:
                return ToolResult(ok=False, output=f"Task not found: {task_id}")
        _save(tasks_path, new_tasks)
        return ToolResult(ok=True, output=f"Deleted task {task_id}")

    registry.register(
        ToolSpec(
            name="task_list",
            description="List local tasks/todos, optionally filtered by status or assignee.",
            parameters={
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "open|done|cancelled"},
                    "assignee": {"type": "string"},
                },
            },
            handler=task_list,
        )
    )
    registry.register(
        ToolSpec(
            name="task_add",
            description="Create a local task/todo item.",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "notes": {"type": "string"},
                    "assignee": {"type": "string"},
                    "due": {"type": "string"},
                    "source": {"type": "string", "description": "e.g. meeting notes title"},
                },
                "required": ["title"],
            },
            handler=task_add,
        )
    )
    registry.register(
        ToolSpec(
            name="task_update",
            description="Update a local task by id (prefix allowed if unique).",
            parameters={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "status": {"type": "string"},
                    "title": {"type": "string"},
                    "notes": {"type": "string"},
                    "assignee": {"type": "string"},
                },
                "required": ["task_id"],
            },
            handler=task_update,
        )
    )
    registry.register(
        ToolSpec(
            name="task_delete",
            description="Delete a local task by id.",
            parameters={
                "type": "object",
                "properties": {"task_id": {"type": "string"}},
                "required": ["task_id"],
            },
            handler=task_delete,
        )
    )
