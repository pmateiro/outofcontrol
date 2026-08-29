from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from outofcontrol.config import Settings
from outofcontrol.factory import create_agent
from outofcontrol.tools import PendingConfirmations


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    reset: bool = False
    session_id: str = "default"


class ConfirmRequest(BaseModel):
    confirmation_token: str
    approve: bool = True
    session_id: str = "default"
    follow_up: str | None = Field(
        default=None,
        description="Optional message to the agent after confirming (e.g. 'continue')",
    )


class ChatResponse(BaseModel):
    reply: str
    pending_confirmations: list[dict[str, Any]]
    tool_trace: list[dict[str, Any]]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.load()
    app = FastAPI(title="OutOfControl Agent", version="0.1.0")

    sessions: dict[str, Any] = {}

    def get_session(session_id: str):
        if session_id not in sessions:
            pending = PendingConfirmations()
            agent, pending, _ = create_agent(settings, confirm=None, pending_shell=pending)
            sessions[session_id] = {"agent": agent, "pending": pending}
        return sessions[session_id]

    @app.get("/health")
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "provider": settings.provider,
            "model": settings.model,
        }

    @app.post("/v1/chat", response_model=ChatResponse)
    def chat(req: ChatRequest) -> ChatResponse:
        try:
            sess = get_session(req.session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        agent = sess["agent"]
        if req.reset:
            agent.reset()
        try:
            result = agent.run(req.message)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e
        return ChatResponse(
            reply=result.reply,
            pending_confirmations=result.pending_confirmations,
            tool_trace=result.tool_trace,
        )

    @app.post("/v1/confirm", response_model=ChatResponse)
    def confirm(req: ConfirmRequest) -> ChatResponse:
        sess = get_session(req.session_id)
        agent = sess["agent"]
        from outofcontrol.tools.base import ToolResult

        result: ToolResult = agent.registry.call(
            "confirm_action",
            {"confirmation_token": req.confirmation_token, "approve": req.approve},
        )
        follow = req.follow_up or (
            "The user approved the sensitive action. Continue with the task."
            if req.approve
            else "The user denied the sensitive action. Acknowledge and suggest an alternative."
        )
        turn = agent.run(f"{follow}\n\nConfirmation result: {result.as_tool_message()}")
        return ChatResponse(
            reply=turn.reply,
            pending_confirmations=turn.pending_confirmations,
            tool_trace=[
                {
                    "name": "confirm_action",
                    "ok": result.ok,
                    "output_preview": result.output[:500],
                },
                *turn.tool_trace,
            ],
        )

    return app
