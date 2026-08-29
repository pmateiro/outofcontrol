from __future__ import annotations

from pathlib import Path

from outofcontrol.skills_loader import SkillLoader
from outofcontrol.tools import build_registry
from outofcontrol.tools.shell import _is_sensitive


def _registry(tmp_path: Path, *, confirm=None, confirm_sensitive: bool = True):
    skills = SkillLoader(tmp_path / "skills")
    (tmp_path / "skills").mkdir(exist_ok=True)
    return build_registry(
        workspace=tmp_path,
        skills=skills,
        calendar_path=tmp_path / "cal.json",
        memory_path=tmp_path / "mem.json",
        sensitive_patterns=[r"\brm\b", r"\bsudo\b", r"\bgit\s+push\b"],
        confirm_sensitive=confirm_sensitive,
        confirm=confirm,
    )


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
    registry, _ = _registry(tmp_path, confirm=None)
    result = registry.call("run_shell", {"command": "rm -rf nowhere"})
    assert result.needs_confirmation
    assert result.confirmation_token
    denied = registry.call(
        "confirm_action",
        {"confirmation_token": result.confirmation_token, "approve": False},
    )
    assert not denied.ok


def test_edit_grep_glob_delete(tmp_path: Path):
    registry, _ = _registry(tmp_path, confirm=lambda *_: True)
    assert registry.call("write_file", {"path": "a.py", "content": "x = 1\ny = 2\n"}).ok
    edited = registry.call(
        "edit_file",
        {"path": "a.py", "old_string": "x = 1", "new_string": "x = 10"},
    )
    assert edited.ok
    assert "x = 10" in registry.call("read_file", {"path": "a.py"}).output
    grepped = registry.call("grep", {"pattern": r"x\s*=\s*10", "glob": "*.py"})
    assert "a.py" in grepped.output
    globbed = registry.call("glob_files", {"pattern": "*.py"})
    assert "a.py" in globbed.output
    deleted = registry.call("delete_file", {"path": "a.py"})
    assert deleted.ok
    assert not (tmp_path / "a.py").exists()


def test_delete_requires_token_without_callback(tmp_path: Path):
    registry, _ = _registry(tmp_path, confirm=None)
    registry.call("write_file", {"path": "t.txt", "content": "bye"})
    result = registry.call("delete_file", {"path": "t.txt"})
    assert result.needs_confirmation
    token = result.confirmation_token
    assert (tmp_path / "t.txt").exists()
    done = registry.call("confirm_action", {"confirmation_token": token, "approve": True})
    assert done.ok
    assert not (tmp_path / "t.txt").exists()


def test_memory_and_calendar(tmp_path: Path):
    registry, _ = _registry(tmp_path, confirm=lambda *_: True)
    assert registry.call("memory_set", {"key": "tz", "content": "America/Sao_Paulo"}).ok
    assert "Sao_Paulo" in registry.call("memory_get", {"key": "tz"}).output
    assert "tz" in registry.call("memory_list", {}).output
    add = registry.call("calendar_add", {"title": "Standup", "start": "2026-08-30 09:00"})
    assert add.ok
    assert "Standup" in registry.call("calendar_list", {}).output


def test_repo_skills_present():
    root = Path(__file__).resolve().parents[1]
    loader = SkillLoader(root / "skills")
    names = {s.name for s in loader.all()}
    assert {"repo-edit", "web-research", "daily-planning", "git-workflow", "memory"} <= names
