from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable


ConfirmCallback = Callable[[str, dict[str, Any]], bool]


@dataclass
class ToolResult:
    ok: bool
    output: str
    needs_confirmation: bool = False
    confirmation_token: str | None = None
    meta: dict[str, Any] | None = None

    def as_tool_message(self) -> str:
        payload: dict[str, Any] = {"ok": self.ok, "output": self.output}
        if self.needs_confirmation:
            payload["needs_confirmation"] = True
            payload["confirmation_token"] = self.confirmation_token
        if self.meta:
            payload["meta"] = self.meta
        return json.dumps(payload, ensure_ascii=False)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., ToolResult]
    sensitive: bool = False

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.openai_schema() for t in self._tools.values()]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        spec = self._tools.get(name)
        if not spec:
            return ToolResult(ok=False, output=f"Unknown tool: {name}")
        try:
            return spec.handler(**arguments)
        except TypeError as e:
            return ToolResult(ok=False, output=f"Invalid arguments for {name}: {e}")
        except Exception as e:  # noqa: BLE001 - surface tool errors to the model
            return ToolResult(ok=False, output=f"Tool error ({name}): {e}")
