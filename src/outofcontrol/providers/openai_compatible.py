from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from outofcontrol.providers.base import Completion, Message, ToolCall


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        item: dict[str, Any] = {"role": m.role}
        if m.content is not None:
            item["content"] = m.content
        if m.tool_calls:
            item["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in m.tool_calls
            ]
        if m.tool_call_id:
            item["tool_call_id"] = m.tool_call_id
        if m.name:
            item["name"] = m.name
        out.append(item)
    return out


def _from_openai_message(msg: Any) -> Message:
    tool_calls: list[ToolCall] = []
    if getattr(msg, "tool_calls", None):
        for tc in msg.tool_calls:
            tool_calls.append(
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments or "{}",
                )
            )
    return Message(role="assistant", content=msg.content, tool_calls=tool_calls)


class OpenAICompatibleProvider:
    """Works with OpenAI and OpenAI-compatible APIs (including Ollama /v1)."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {}
        if api_key is not None:
            kwargs["api_key"] = api_key
        if base_url is not None:
            kwargs["base_url"] = base_url
        # Ollama often ignores/doesn't need a real key
        if "api_key" not in kwargs and base_url:
            kwargs["api_key"] = api_key or "ollama"
        self.model = model
        self.client = OpenAI(**kwargs)

    def complete(
        self,
        messages: list[Message],
        tools: list[dict[str, Any]] | None = None,
    ) -> Completion:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": _to_openai_messages(messages),
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = self.client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        return Completion(
            message=_from_openai_message(choice.message),
            finish_reason=choice.finish_reason,
            raw=resp,
        )


def dump_tool_args(arguments: str) -> dict[str, Any]:
    try:
        data = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return {"_raw": arguments}
    return data if isinstance(data, dict) else {"_value": data}
