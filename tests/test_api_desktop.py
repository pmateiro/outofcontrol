from __future__ import annotations

from outofcontrol.api import create_app
from outofcontrol.config import Settings
from outofcontrol.providers.base import Completion, Message


class FakeProvider:
    def complete(self, messages, tools=None):
        last = messages[-1].content if messages else ""
        return Completion(message=Message(role="assistant", content=f"echo:{last}"))


def test_chat_reset_and_context(monkeypatch, tmp_path):
    import outofcontrol.factory as factory

    settings = Settings(
        provider="openai",
        openai_api_key="test",
        workspace=tmp_path,
        skills_dir=tmp_path / "skills",
        calendar_path=tmp_path / "cal.json",
        memory_path=tmp_path / "mem.json",
        tasks_path=tmp_path / "tasks.json",
        knowledge_dir=tmp_path / "docs",
    )
    (tmp_path / "skills").mkdir()

    def fake_create_agent(settings=None, confirm=None, pending_shell=None, on_event=None):
        from outofcontrol.agent.loop import Agent
        from outofcontrol.skills_loader import SkillLoader
        from outofcontrol.tools import build_registry

        skills = SkillLoader(tmp_path / "skills")
        registry, pending = build_registry(
            workspace=tmp_path,
            skills=skills,
            calendar_path=tmp_path / "cal.json",
            memory_path=tmp_path / "mem.json",
            tasks_path=tmp_path / "tasks.json",
            knowledge_dir=tmp_path / "docs",
            sensitive_patterns=[],
            confirm_sensitive=False,
            confirm=confirm,
            pending_shell=pending_shell,
        )
        agent = Agent(
            provider=FakeProvider(),
            registry=registry,
            skills=skills,
            workspace=str(tmp_path),
        )
        return agent, pending, settings

    monkeypatch.setattr(factory, "create_agent", fake_create_agent)
    # create_app imports create_agent from factory at call time via get_session
    monkeypatch.setattr("outofcontrol.api.create_agent", fake_create_agent)

    app = create_app(settings)
    from fastapi.testclient import TestClient

    client = TestClient(app)
    assert client.get("/health").json()["status"] == "ok"

    reset = client.post("/v1/chat", json={"reset": True, "session_id": "gnome"})
    assert reset.status_code == 200
    assert reset.json()["reply"] == "Session reset."

    chat = client.post(
        "/v1/chat",
        json={
            "message": "summarize",
            "session_id": "gnome",
            "context": "selected text HERE",
        },
    )
    assert chat.status_code == 200
    body = chat.json()["reply"]
    assert "Desktop context" in body or "selected text HERE" in body
    assert "summarize" in body
