from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from outofcontrol.providers.base import LLMProvider, Message
from outofcontrol.providers.openai_compatible import dump_tool_args
from outofcontrol.skills_loader import SkillLoader
from outofcontrol.tools.base import ToolRegistry, ToolResult


OnEvent = Callable[[str, dict[str, Any]], None]


SYSTEM_TEMPLATE = """You are OutOfControl, a general-purpose assistant similar in spirit to Cursor's agent.
You help with coding, shell tasks, web research, calendar/scheduling, memory, and other practical work.

Workspace: {workspace}
You have tools. Prefer tools over guessing. Use load_skill when a listed skill matches the task.

Available skills (summaries only — use load_skill for full instructions):
{skills}

Guidelines:
- Be concise and direct.
- Prefer edit_file for surgical code changes; write_file for new files.
- Use grep / glob_files to navigate codebases before editing.
- Sensitive shell commands and delete_file may require confirm_action.
- Persist durable user facts with memory_set / memory_get when asked to remember.
- For calendar, use the local calendar tools (not a third-party account unless configured later).
- When done, give a clear final answer without unnecessary tool calls.
{extra}
"""


@dataclass
class AgentTurnResult:
    reply: str
    messages: list[Message] = field(default_factory=list)
    pending_confirmations: list[dict[str, Any]] = field(default_factory=list)
    tool_trace: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        registry: ToolRegistry,
        skills: SkillLoader,
        workspace: str,
        max_tool_rounds: int = 20,
        system_prompt_extra: str = "",
        on_event: OnEvent | None = None,
    ) -> None:
        self.provider = provider
        self.registry = registry
        self.skills = skills
        self.workspace = workspace
        self.max_tool_rounds = max_tool_rounds
        self.system_prompt_extra = system_prompt_extra
        self.on_event = on_event
        self.history: list[Message] = []

    def _emit(self, kind: str, **payload: Any) -> None:
        if self.on_event:
            self.on_event(kind, payload)

    def _system_message(self) -> Message:
        text = SYSTEM_TEMPLATE.format(
            workspace=self.workspace,
            skills=self.skills.inventory_text(),
            extra=self.system_prompt_extra.strip(),
        )
        return Message(role="system", content=text)

    def reset(self) -> None:
        self.history.clear()

    def run(self, user_text: str) -> AgentTurnResult:
        self.history.append(Message(role="user", content=user_text))
        messages = [self._system_message(), *self.history]
        pending_confirmations: list[dict[str, Any]] = []
        tool_trace: list[dict[str, Any]] = []

        for _ in range(self.max_tool_rounds):
            self._emit("model_start")
            completion = self.provider.complete(messages, tools=self.registry.schemas())
            assistant = completion.message
            messages.append(assistant)
            self.history.append(assistant)
            self._emit(
                "model_end",
                content=assistant.content,
                tool_calls=[tc.name for tc in assistant.tool_calls],
            )

            if not assistant.tool_calls:
                reply = assistant.content or ""
                return AgentTurnResult(
                    reply=reply,
                    messages=list(self.history),
                    pending_confirmations=pending_confirmations,
                    tool_trace=tool_trace,
                )

            for tc in assistant.tool_calls:
                args = dump_tool_args(tc.arguments)
                self._emit("tool_start", name=tc.name, arguments=args)
                result: ToolResult = self.registry.call(tc.name, args)
                trace_item = {
                    "name": tc.name,
                    "arguments": args,
                    "ok": result.ok,
                    "needs_confirmation": result.needs_confirmation,
                    "output_preview": result.output[:500],
                }
                tool_trace.append(trace_item)
                if result.needs_confirmation:
                    pending_confirmations.append(
                        {
                            "tool": tc.name,
                            "confirmation_token": result.confirmation_token,
                            "meta": result.meta or {},
                            "message": result.output,
                        }
                    )
                tool_msg = Message(
                    role="tool",
                    content=result.as_tool_message(),
                    tool_call_id=tc.id,
                    name=tc.name,
                )
                messages.append(tool_msg)
                self.history.append(tool_msg)
                self._emit(
                    "tool_end",
                    name=tc.name,
                    ok=result.ok,
                    needs_confirmation=result.needs_confirmation,
                )

            # If we stopped only because confirmation is needed, still let the model
            # explain next steps once more — continue loop unless max rounds hit.

        return AgentTurnResult(
            reply="Stopped: reached max tool rounds without a final answer.",
            messages=list(self.history),
            pending_confirmations=pending_confirmations,
            tool_trace=tool_trace,
        )
