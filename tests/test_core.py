from __future__ import annotations

from pathlib import Path

from outofcontrol.skills_loader import SkillLoader
from outofcontrol.tools.shell import PendingShell, _is_sensitive
from outofcontrol.tools import build_registry


def test_skill_loader_discovers_skills(tmp_path: Path):
    skill_dir = tmp_path / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\ndescription: A demo skill\n---\n\nDo the demo.\n",
        encoding="utf-8",
    )
    loader = SkillLoader(tmp_path / "skills")
    skills = loader.all()
    assert len(skills) == 1
    assert skills[0].name == "demo"
    assert "Do the demo" in loader.get("demo").body


def test_sensitive_shell_detection():
    patterns = [r"\brm\b", r"\bsudo\b", r"\bgit\s+push\b"]
    assert _is_sensitive("rm -rf /tmp/x", patterns)
    assert _is_sensitive("sudo apt install x", patterns)
    assert _is_sensitive("git push origin main", patterns)
    assert not _is_sensitive("ls -la", patterns)
    assert not _is_sensitive("echo hello", patterns)


def test_shell_confirmation_flow(tmp_path: Path):
    skills = SkillLoader(tmp_path / "skills")
    (tmp_path / "skills").mkdir(exist_ok=True)
    registry, pending = build_registry(
        workspace=tmp_path,
        skills=skills,
        calendar_path=tmp_path / "cal.json",
        sensitive_patterns=[r"\brm\b"],
        confirm_sensitive=True,
        confirm=None,
    )
    result = registry.call("run_shell", {"command": "rm -rf nowhere"})
    assert result.needs_confirmation
    assert result.confirmation_token
    denied = registry.call(
        "confirm_shell",
        {"confirmation_token": result.confirmation_token, "approve": False},
    )
    assert not denied.ok


def test_calendar_and_files(tmp_path: Path):
    skills = SkillLoader(tmp_path / "skills")
    (tmp_path / "skills").mkdir(exist_ok=True)
    registry, _ = build_registry(
        workspace=tmp_path,
        skills=skills,
        calendar_path=tmp_path / "cal.json",
        sensitive_patterns=[],
        confirm_sensitive=False,
        confirm=lambda *_: True,
    )
    w = registry.call("write_file", {"path": "hello.txt", "content": "hi"})
    assert w.ok
    r = registry.call("read_file", {"path": "hello.txt"})
    assert r.output == "hi"
    add = registry.call(
        "calendar_add",
        {"title": "Standup", "start": "2026-08-30 09:00"},
    )
    assert add.ok
    listed = registry.call("calendar_list", {})
    assert "Standup" in listed.output
